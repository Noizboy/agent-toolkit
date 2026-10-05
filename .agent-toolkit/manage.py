#!/usr/bin/env python3
"""Portable project agent toolkit. Python 3.11+, Git; Node/npm for stdio MCPs."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from configuration import (agent_metadata, configure_mcp, install_mcp_runtime, mcp_configs,
                           resolve_npm, sync_agents, toml_data)
from sources import (atomic_text, checkout, install_skill, read_json, safe_path,
                     save_json, skill_payloads, tree_hash, validate_tool)

HERE = Path(__file__).resolve().parent
ROOT = Path.cwd() if getattr(sys, "frozen", False) else HERE.parent


class ExportConflict(ValueError):
    """A controlled, actionable preflight conflict safe to show during setup."""


class Toolkit:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.home = safe_path(self.root, ".agent-toolkit")
        self.registry = read_json(self.home / "registry.json", {})
        self.state = read_json(safe_path(self.home, "tools.lock.json"), {"schema_version": 1, "tools": {}})
        self.tools = self.registry["tools"]
        if self.registry.get("schema_version") != 1:
            raise ValueError("Unsupported registry version")
        names = set()
        for tool in self.tools:
            validate_tool(tool)
            if tool["id"] in names:
                raise ValueError("Duplicate tool id")
            names.add(tool["id"])

    def save(self):
        save_json(safe_path(self.home, "tools.lock.json"), self.state)

    def bootstrap(self, update=False, only=None) -> list[str]:
        errors = []
        if only and only not in {t["id"] for t in self.tools}:
            raise ValueError("Unknown tool id")
        for tool in self.tools:
            if tool.get("enabled", True) is False or (only and tool["id"] != only):
                continue
            name = tool["id"]
            previous = self.state["tools"].get(name, {})
            record = dict(previous)
            try:
                with tempfile.TemporaryDirectory(prefix="agent-payload-") as directory:
                    staging = Path(directory)
                    payloads = []
                    if tool.get("repo"):
                        print(f"Preparing {name}...", flush=True)
                        source, commit = checkout(tool, safe_path(self.home, "vendor"), previous, update)
                        record.update(source=f"{tool['repo']}@{tool.get('ref', 'HEAD')}", commit=commit,
                                      source_path=source.relative_to(self.root).as_posix())
                        payloads += skill_payloads(tool, source, staging)
                    if tool.get("adapter"):
                        adapter = safe_path(self.home, "adapters/" + tool["adapter"])
                        tree_hash(adapter)
                        target = safe_path(staging, tool["adapter"])
                        shutil.copytree(adapter, target)
                        payloads.append(target)
                    installed = dict(previous.get("skills", {}))
                    record["skills"] = installed
                    for payload in payloads:
                        installed[payload.name] = install_skill(payload, safe_path(self.root, ".agents/skills"),
                                                                installed.get(payload.name, {}))
                        if installed[payload.name]["status"].startswith("conflict"):
                            errors.append(name + ": skill has local changes: " + payload.name)
                    record["skills"] = installed
                if tool.get("mcp", {}).get("transport") == "stdio":
                    pinned = resolve_npm(tool["mcp"], previous.get("npm", {}), update)
                    record["npm"] = install_mcp_runtime(tool, self.root, pinned)
                record.pop("error", None)
            except (OSError, RuntimeError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
                # Errors contain our own bounded messages, not subprocess output or credentials.
                record["error"] = type(error).__name__ + ": " + str(error)
                errors.append(name + ": " + record["error"])
            self.state["tools"][name] = record
            self.save()
        # Ignore only managed downloaded skills; never blanket-ignore future user-authored skills.
        ignored = safe_path(self.root, ".agents/skills/.gitignore")
        original = ignored.read_text(encoding="utf-8-sig") if ignored.exists() else ""
        for record in self.state["tools"].values():
            for name, skill in record.get("skills", {}).items():
                if skill.get("hash") and f"/{name}/" not in original.splitlines():
                    original = original.rstrip() + f"\n/{name}/\n"
        atomic_text(ignored, original)
        self.save()
        project = read_json(safe_path(self.home, "project.json"), {})
        if project.get("provider"):
            from providers import configure_provider
            errors += configure_provider(self.root, project["provider"], project)
            self.state = read_json(safe_path(self.home, "tools.lock.json"), self.state)
        self.inventory()
        return errors

    def inventory(self) -> dict:
        rows = []
        for tool in self.tools:
            record = self.state["tools"].get(tool["id"], {})
            skills = []
            for name, item in record.get("skills", {}).items():
                folder = safe_path(self.root, ".agents/skills/" + name)
                status = item["status"]
                if not (folder / "SKILL.md").is_file():
                    status = "missing"
                elif item.get("hash") and tree_hash(folder) != item["hash"]:
                    status = "local-changes"
                skills.append({"name": name, "status": status})
            credentials = tool.get("credential_envs", [])[:]
            if tool.get("mcp", {}).get("credential_env"):
                credentials.append(tool["mcp"]["credential_env"])
            command = tool.get("command")
            runtime = "not-applicable"
            if command:
                runtime = "command-found; execution-not-verified" if shutil.which(command) else "runtime-not-installed"
                from tool_runtime import RECIPES, runtime_status
                if tool['id'] in RECIPES:
                    managed = runtime_status(self.root, tool['id'])
                    if managed.get('status') == 'installed':
                        runtime = 'project-runtime-installed; integrity-checked; execution-not-verified'
                    elif managed.get('status') not in {'not-installed', 'command-detected', 'runtime-not-installed'}:
                        runtime += '; managed-' + managed['status']
            if tool['id'] == 'strix':
                from setup_support import strix_settings
                settings = strix_settings(self.root)
                if settings['auth_mode'] == 'chatgpt':
                    credentials = []
                elif settings['model']:
                    credentials = [name for name in credentials if name != 'STRIX_LLM']
            if tool.get("mcp", {}).get("transport") == "stdio":
                entry = record.get("npm", {}).get("entrypoint")
                runtime = "installed; protocol-not-probed" if entry and safe_path(self.root, entry).is_file() else "runtime-not-installed"
            rows.append({"id": tool["id"], "type": tool["type"], "enabled": tool.get("enabled", True),
                         "source": "downloaded" if record.get("source_path") and safe_path(self.root, record["source_path"]).is_dir() else "not-downloaded" if tool.get("repo") else "not-required",
                         "commit": record.get("commit"), "skills": skills, "runtime": runtime,
                         "credentials": {name: bool(os.environ.get(name)) for name in credentials},
                         "requirements": {name: bool(shutil.which(name)) for name in tool.get("requirements", [])},
                         "error": record.get("error"), "notes": tool.get("notes", ""), "docs": tool.get("docs", "")})
        project_skills = self.skill_inventory(safe_path(self.root, ".agents/skills"), "project")
        project = read_json(safe_path(self.home, "project.json"), {})
        provider = project.get("provider")
        user_skills = self.skill_inventory(Path.home() / ".agents/skills", "user-agents")
        user_homes = {"codex": Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")),
                      "claude": Path.home() / ".claude",
                      "opencode": Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "opencode"}
        if provider in user_homes:
            user_skills += self.skill_inventory(user_homes[provider] / "skills", "user-" + provider)
        agents = []
        from providers import _models
        models = _models(provider, project) if provider else {}
        for card in sorted(safe_path(self.root, ".agent-toolkit/agents").glob("*.md")):
            safe_path(self.root, card.relative_to(self.root).as_posix())
            meta = agent_metadata(card)
            if meta.get("model_tier"):
                native = (".codex/agents/" + card.stem + ".toml" if provider == "codex" else
                          f".{provider}/agents/{card.stem.lower()}.md" if provider else None)
                agents.append({"name": meta["name"], "model_tier": meta["model_tier"],
                               "model": models.get(meta["model_tier"] + "_model", "select a provider"),
                               "effort": meta.get("reasoning_effort", "medium"),
                               "native_config": bool(native and safe_path(self.root, native).is_file())})
        report = {"schema_version": 1, "provider": provider or "not-selected", "tools": rows, "agents": agents,
                  "skills": project_skills + user_skills, "mcp": mcp_configs(self.root)}
        probes = read_json(safe_path(self.home, "mcp-probes.json"), {})
        for tool in rows:
            if tool["id"] in probes.get("results", {}):
                tool["last_mcp_probe"] = probes["results"][tool["id"]]
                tool["runtime"] = tool["runtime"].replace("protocol-not-probed", "last protocol probe: " + tool["last_mcp_probe"]["status"])
        for mcp in report["mcp"]:
            if mcp["scope"] == "project" and mcp["id"] in probes.get("results", {}):
                mcp["last_probe"] = probes["results"][mcp["id"]]
                mcp["runtime"] = f"last probe: {mcp['last_probe']['status']} ({probes.get('checked_at', 'time not recorded')}); current session loading not verified"
        save_json(safe_path(self.home, "inventory.json"), report)
        self.write_inventory(report)
        return report

    @staticmethod
    def skill_inventory(folder: Path, scope: str) -> list[dict]:
        if not folder.is_dir():
            return []
        result = []
        for skill in sorted(folder.iterdir()):
            try:
                safe_path(folder, skill.name)
            except ValueError:
                continue
            if (skill / "SKILL.md").is_file():
                result.append({"name": skill.name, "scope": scope, "status": "installed; usage-not-verified"})
        return result

    def write_inventory(self, report):
        def cell(value):
            return str(value).replace("|", "\\|").replace("\n", " ")
        lines = ["# Agent toolkit inventory", "", "Generated by `python .agent-toolkit/manage.py list`. Credentials are presence checks only.",
                 "No file/configuration check establishes live MCP availability. Call its tools or use `doctor --probe-mcp`.", "",
                 "Selected client: " + report["provider"] + ".", "",
                 "## Agents", "", "| Agent | Selected model | Reasoning | Native config |", "|---|---|---|---|"]
        for agent in report["agents"]:
            lines.append(f"| {agent['name']} | {agent['model']} | {agent['effort']} | {agent['native_config']} |")
        lines += ["", "## Registered tools", "", "| Tool | Type | Source | Skills | Runtime | Credentials |", "|---|---|---|---|---|---|"]
        for tool in report["tools"]:
            skills = ", ".join(s["name"] + ": " + s["status"] for s in tool["skills"]) or "none"
            creds = ", ".join(key + ": " + ("present" if value else "missing") for key, value in tool["credentials"].items()) or "none"
            lines.append("| " + " | ".join(cell(v) for v in [tool["id"], tool["type"], tool["source"], skills, tool["runtime"], creds]) + " |")
            if tool["error"]:
                lines.append(f"\nIssue for {tool['id']}: {cell(tool['error'])}\n")
        lines += ["", "## All discovered skills", "", "| Skill | Scope | Status |", "|---|---|---|"]
        for skill in report["skills"]:
            lines.append(f"| {cell(skill['name'])} | {skill['scope']} | {skill['status']} |")
        lines += ["", "## All configured MCP servers", "", "| Server | Scope | Enabled | Credential presence | Protocol |", "|---|---|---|---|---|"]
        for mcp in report["mcp"]:
            creds = ", ".join(key + ": " + ("present" if value else "missing") for key, value in mcp["credential_presence"].items()) or "not-checked"
            lines.append(f"| {cell(mcp['id'])} | {mcp['scope']} | {mcp['enabled']} | {cell(creds)} | {mcp['runtime']} |")
        lines += ["", "## Limits", "", "Plugin-injected MCPs and bundled plugin skills may be visible only inside the selected client session; they are not filesystem installations.",
                  "CLI source downloads do not install CLI runtimes. Consult each upstream source for platform-specific prerequisites.",
                  "Locally modified or unmanaged skills/config are preserved. Review conflicts before updates.", ""]
        atomic_text(safe_path(self.home, "INVENTORY.md"), "\n".join(lines))

    def doctor(self, probe=False) -> int:
        report = self.inventory()
        issues = []
        for tool in report["tools"]:
            if not tool["enabled"]:
                continue
            if tool["error"]:
                issues.append(tool["id"] + ": recorded bootstrap error")
            if tool["source"] == "not-downloaded":
                issues.append(tool["id"] + ": source missing; run bootstrap")
            for skill in tool["skills"]:
                if skill["status"] in {"missing", "local-changes", "conflict-local-changes"}:
                    issues.append(tool["id"] + ": skill " + skill["status"])
            for env_name, present in tool["credentials"].items():
                if not present:
                    issues.append(tool["id"] + ": missing " + env_name)
            if tool["runtime"] == "runtime-not-installed":
                issues.append(tool["id"] + ": CLI/MCP runtime not installed (source/skills can still be used)")
            if '; managed-conflict' in tool['runtime']:
                issues.append(tool['id'] + ': managed runtime modified or incomplete; preserve and review it')
            if tool['id'] == 'strix':
                from setup_support import strix_settings
                from tool_runtime import strix_auth_status
                settings = strix_settings(self.root)
                if settings['auth_mode'] == 'chatgpt':
                    status = strix_auth_status(self.root)
                    print('strix: ' + status['status'] + '; model execution not verified')
                    if status['status'] != 'session-detected':
                        issues.append('strix: configure/check ChatGPT sign-in with manage.py setup')
            for dependency, present in tool["requirements"].items():
                if not present:
                    issues.append(tool["id"] + ": command missing: " + dependency)
        if probe:
            from datetime import datetime, timezone
            from probe import probe_mcps
            results = probe_mcps(self.root, self.tools, self.state)
            save_json(safe_path(self.home, "mcp-probes.json"), {"checked_at": datetime.now(timezone.utc).isoformat(), "results": results})
            self.inventory()
            for name, result in results.items():
                print(f"{name}: {result['status']}")
                if result["status"] != "verified":
                    issues.append(name + ": MCP probe did not verify runtime")
        for issue in issues:
            print("- " + issue)
        if not issues:
            print("Filesystem/configuration checks passed. Runtime verification is separate.")
        return 1 if issues else 0

    def add(self, args):
        if any(t["id"] == args.id for t in self.tools):
            raise ValueError("Tool already exists; edit registry.json to change its settings")
        item = {"id": args.id, "type": "skill" if args.repo else "mcp", "docs": args.docs or ""}
        if args.repo:
            if not args.skill:
                raise ValueError("GitHub skill sources require --skill PATH")
            item.update(repo=args.repo, ref=args.ref, skills=args.skill)
        elif args.mcp_url:
            item["mcp"] = {"transport": "http", "url": args.mcp_url}
        elif args.mcp_package:
            item["mcp"] = {"transport": "stdio", "package": args.mcp_package}
            if args.version:
                item["mcp"]["version"] = args.version
        else:
            raise ValueError("Choose --repo, --mcp-url or --mcp-package")
        if args.env:
            item["mcp"]["credential_env"] = args.env
            if args.server_env:
                item["mcp"]["server_env"] = args.server_env
        validate_tool(item)
        self.tools.append(item)
        save_json(self.home / "registry.json", self.registry)
        print("Registered " + args.id + "; run bootstrap to install/configure it.")

    def export(self, destination: Path, *, settings=None):
        destination = destination.resolve()
        if destination == self.root or destination.is_relative_to(self.home):
            raise ValueError("Choose another project directory")
        destination.mkdir(parents=True, exist_ok=True)
        files = []
        for folder, directories, filenames in os.walk(self.home, followlinks=False):
            directories[:] = [name for name in directories if name not in
                              {"vendor", "runtime", "__pycache__", ".build-venv", "installer-build", "installer-dist"}]
            for filename in filenames:
                if filename in {"tools.lock.json", "inventory.json", "INVENTORY.md", "mcp-probes.json",
                                "project.json", "provider-state.json", "installation.json"}:
                    continue
                file = Path(folder) / filename
                relative = file.relative_to(self.home)
                safe_path(self.home, relative.as_posix())
                files.append((file, ".agent-toolkit/" + relative.as_posix()))
        files.append((self.root / ".agents/skills/agent-toolkit/SKILL.md", ".agents/skills/agent-toolkit/SKILL.md"))
        # Preflight all paths before writing any toolkit files to another project.
        for source, relative in files:
            target = safe_path(destination, relative)
            if target.exists() and target.read_bytes() != source.read_bytes():
                raise ExportConflict("Existing toolkit file differs: " + relative +
                                     ". Preserve a backup and merge this file with the downloaded toolkit before retrying.")
        # Share source/artifact pins, not the original project's customization or absolute paths.
        lock = {"schema_version": 1, "tools": {}}
        for name, record in self.state["tools"].items():
            lock["tools"][name] = {k: v for k, v in record.items() if k in {"commit", "source"}}
            if record.get("npm"):
                lock["tools"][name]["npm"] = {k: v for k, v in record["npm"].items() if k in {"package", "version", "integrity"}}
        lock_path = safe_path(destination, ".agent-toolkit/tools.lock.json")
        if lock_path.exists():
            lock = read_json(lock_path, lock)
        if lock.get("schema_version") != 1:
            raise ExportConflict("Existing .agent-toolkit/tools.lock.json has an incompatible format. Preserve it and migrate the lock before retrying.")
        append_plans = []
        for relative, template in [("AGENTS.md", "AGENTS.template.md"), (".gitignore", "gitignore.template")]:
            target = safe_path(destination, relative)
            original = target.read_text(encoding="utf-8-sig") if target.exists() else ""
            block = (self.home / template).read_text(encoding="utf-8")
            try:
                content = appended_content(original, block)
            except ValueError:
                raise ExportConflict("Existing toolkit routing block differs in " + relative +
                                     ". Preserve project instructions and merge only the marked toolkit block before retrying.") from None
            append_plans.append((target, content))
        for source, relative in files:
            target = safe_path(destination, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        save_json(lock_path, lock)
        for target, content in append_plans:
            atomic_text(target, content)
        if settings:
            save_json(safe_path(destination, ".agent-toolkit/project.json"), settings)
        return Toolkit(destination).bootstrap()


def append_once(root: Path, relative: str, block: str):
    target = safe_path(root, relative)
    original = target.read_text(encoding="utf-8-sig") if target.exists() else ""
    atomic_text(target, appended_content(original, block))


def appended_content(original: str, block: str) -> str:
    if block.strip() in original:
        return original
    if "BEGIN generic-agent-toolkit" in original:
        raise ValueError("Existing toolkit routing block differs; preserve it and merge manually")
    return original.rstrip() + "\n\n" + block.strip() + "\n"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=ROOT, help="Target project for all commands")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("bootstrap", help="Restore pinned tools and download missing skills")
    update = sub.add_parser("update", help="Explicitly advance upstream commits/npm versions")
    update.add_argument("--tool")
    listing = sub.add_parser("list", help="Write/print sanitized project/user inventory")
    listing.add_argument("--json", action="store_true")
    doctor = sub.add_parser("doctor", help="Check prerequisites without running scans")
    doctor.add_argument("--probe-mcp", action="store_true", help="Initialize MCP and list tools; never run tests/scans")
    sub.add_parser("sync-agents", help="Refresh native definitions for the selected client")
    sub.add_parser('setup', help='Open guided optional runtime/authentication/MCP setup')
    from tool_runtime import RECIPES
    runtime = sub.add_parser('install-runtime', help='Install one reviewed project-local optional CLI; no scans')
    runtime.add_argument('tool', choices=list(RECIPES))
    run = sub.add_parser('run-tool', help='Explicitly run one integrity-checked project-local optional CLI')
    run.add_argument('tool', choices=list(RECIPES))
    run.add_argument('args', nargs=argparse.REMAINDER)
    export = sub.add_parser("export", help="Install this toolkit in another project")
    export.add_argument("--project", dest="destination", type=Path, required=True)
    add = sub.add_parser("add", help="Extend the registry without modifying installer code")
    add.add_argument("--id", required=True)
    source = add.add_mutually_exclusive_group(required=True)
    source.add_argument("--repo")
    source.add_argument("--mcp-url")
    source.add_argument("--mcp-package")
    add.add_argument("--skill", action="append")
    add.add_argument("--ref", default="HEAD")
    add.add_argument("--version")
    add.add_argument("--env")
    add.add_argument("--server-env")
    add.add_argument("--docs")
    args = parser.parse_args()
    toolkit = Toolkit(args.project)
    if args.command in {"bootstrap", "update", "export"}:
        errors = toolkit.export(args.destination) if args.command == "export" else toolkit.bootstrap(
            update=args.command == "update", only=getattr(args, "tool", None))
        for error in errors:
            print("Issue: " + error)
        print("Inventory: .agent-toolkit/INVENTORY.md")
        return 1 if errors else 0
    if args.command == "list":
        report = toolkit.inventory()
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            for tool in report["tools"]:
                print(f"{tool['id']}: {tool['source']}; {len(tool['skills'])} skill(s); {tool['runtime']}")
            print(f"Total: {len(report['agents'])} agents, {len(report['skills'])} discovered skills, {len(report['mcp'])} configured MCP entries")
            print("Full list: .agent-toolkit/INVENTORY.md")
    elif args.command == "doctor":
        return toolkit.doctor(args.probe_mcp)
    elif args.command == 'setup':
        from setup_wizard import open_setup
        open_setup(toolkit.root)
    elif args.command == 'install-runtime':
        from tool_runtime import install_runtime
        result = install_runtime(toolkit.root, args.tool)
        print(json.dumps(result))
        toolkit.inventory()
        return 0 if result['status'] == 'installed' else 1
    elif args.command == 'run-tool':
        from tool_runtime import run_tool
        return run_tool(toolkit.root, args.tool, args.args[1:] if args.args[:1] == ['--'] else args.args)
    elif args.command == "sync-agents":
        project = read_json(safe_path(toolkit.home, "project.json"), {})
        if project.get("provider"):
            from providers import configure_provider
            issues = configure_provider(toolkit.root, project["provider"], project)
            for issue in issues:
                print("Issue: " + issue)
            if issues:
                return 1
        else:
            print("No provider selected. Run the setup wizard to choose a coding environment.")
            return 1
    elif args.command == "add":
        toolkit.add(args)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print("Toolkit: " + str(error), file=sys.stderr)
        sys.exit(1)
