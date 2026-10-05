"""Pinned runtimes, inventory and the explicitly selected Codex adapter."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.request

from sources import atomic_text, read_json, safe_path, save_json, validate_tool


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def toml_data(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}


def agent_metadata(path: Path) -> dict:
    content = path.read_text(encoding="utf-8-sig")
    if not content.startswith("---\n"):
        return {}
    metadata = {}
    for line in content.split("---", 2)[1].strip().splitlines():
        key, _, value = line.partition(":")
        value = value.strip()
        metadata[key] = json.loads(value) if value.startswith('"') else value
    return metadata


def sync_agents(root: Path, state: dict, settings=None, *, dry_run=False) -> list[str]:
    agents = safe_path(root, ".agent-toolkit/agents")
    result = []
    writes = []
    generated = state.setdefault("agents", {})
    settings = settings or {}
    models = {"strong": settings.get("strong_model", "gpt-6.1-sol"),
              "light": settings.get("light_model", "gpt-6-luna"),
              "escalation": settings.get("escalation_model", "gpt-6-astra")}
    if any(value not in {"gpt-6-astra", "gpt-6.1-sol", "gpt-6-sol", "gpt-6-luna"} for value in models.values()):
        raise ValueError("Agent model is outside the approved ChatGPT catalogue")
    for card in sorted(agents.glob("*.md")):
        safe_path(agents, card.name)
        meta = agent_metadata(card)
        if "model_tier" not in meta:
            continue
        target = safe_path(root, ".codex/agents/" + card.stem + ".toml")
        if meta.get("name") != card.stem:
            raise ValueError("Agent name must match filename")
        if meta["model_tier"] not in models:
            raise ValueError("Invalid agent model tier")
        body = card.read_text(encoding="utf-8-sig").split("---", 2)[2].strip()
        instructions = ("Read .agent-toolkit/agents/Agent-Contract.md before work.\n"
                        f"Selected client: ChatGPT / Codex. Escalation model: {models['escalation']}.\n\n" + body)
        fields = {"name": meta["name"], "description": meta["description"], "model": models[meta["model_tier"]],
                  "model_reasoning_effort": meta.get("reasoning_effort", "medium"),
                  "developer_instructions": instructions}
        rendered = "# Generated from the matching .md card. Edit the card, then sync-agents.\n"
        rendered += "\n".join(f"{key} = {json.dumps(value, ensure_ascii=False)}" for key, value in fields.items()) + "\n"
        if target.exists():
            original = target.read_text(encoding="utf-8-sig")
            if original != rendered and generated.get(card.stem) != text_hash(original):
                result.append(f"{card.stem}: preserved customized TOML")
                continue
        writes.append((target, rendered))
        generated[card.stem] = text_hash(rendered)
        result.append(f"{card.stem}: configured")
    if not dry_run and not any("preserved" in note for note in result):
        for target, rendered in writes:
            atomic_text(target, rendered)
    return result


def resolve_npm(mcp: dict, previous: dict, update: bool) -> dict:
    package = mcp["package"]
    version = mcp.get("version")
    if previous.get("package") == package and not update and previous.get("version"):
        return previous
    endpoint = f"https://registry.npmjs.org/{package}/{version if version and not update else 'latest'}"
    with urllib.request.urlopen(endpoint, timeout=45) as response:
        data = json.load(response)
    if data.get("name") != package or not data.get("dist", {}).get("integrity"):
        raise ValueError("npm registry returned invalid metadata")
    validate_tool({"id": "npm-check", "mcp": {"package": package, "version": data["version"]}})
    return {"package": package, "version": data["version"], "integrity": data["dist"]["integrity"]}


def npm_command() -> list[str]:
    npm = shutil.which("npm")
    node = shutil.which("node")
    if not npm or not node:
        raise RuntimeError("Node.js and npm are required for stdio MCP runtimes")
    # Invoke npm's JavaScript entrypoint directly on Windows instead of a command shell.
    entry = Path(npm).parent / "node_modules/npm/bin/npm-cli.js"
    if entry.exists():
        return [node, str(entry)]
    if os.name == "nt":
        raise RuntimeError("Could not locate npm-cli.js beside npm; use a standard Node.js install")
    return [npm]


def install_mcp_runtime(tool: dict, root: Path, pinned: dict) -> dict:
    runtime = safe_path(root, f".agent-toolkit/runtime/{tool['id']}/{pinned['version']}")
    package_root = safe_path(runtime, "node_modules/" + pinned["package"])
    dependency_lock = safe_path(root, f".agent-toolkit/runtime-locks/{tool['id']}/{pinned['version']}.json")
    installed = read_json(package_root / "package.json", {})
    if installed.get("version") != pinned["version"]:
        runtime.mkdir(parents=True, exist_ok=True)
        save_json(runtime / "package.json", {"name": "agent-mcp-runtime", "private": True,
                                           "version": "1.0.0", "dependencies": {pinned["package"]: pinned["version"]}})
        if dependency_lock.exists():
            shutil.copy2(dependency_lock, runtime / "package-lock.json")
            action = ["ci"]
        else:
            action = ["install", pinned["package"] + "@" + pinned["version"]]
        command = [*npm_command(), *action, "--ignore-scripts", "--no-audit", "--no-fund", "--workspaces=false"]
        result = subprocess.run(command, cwd=runtime, capture_output=True, text=True, timeout=300)
        if result.returncode:
            raise RuntimeError("MCP npm runtime installation failed; lifecycle scripts were disabled")
        installed = read_json(package_root / "package.json", {})
    lock = read_json(runtime / "package-lock.json", {})
    artifact = lock.get("packages", {}).get("node_modules/" + pinned["package"], {})
    if artifact.get("integrity") != pinned["integrity"]:
        raise ValueError("MCP package integrity differs from the pinned npm artifact")
    if not dependency_lock.exists():
        save_json(dependency_lock, lock)
    elif read_json(dependency_lock, {}) != lock:
        raise ValueError("MCP dependency lock differs from the portable dependency lock")
    bins = installed.get("bin", {})
    if isinstance(bins, str):
        binary = bins
    else:
        name = tool["mcp"].get("bin_name")
        if name:
            binary = bins[name]
        elif len(bins) == 1:
            binary = next(iter(bins.values()))
        else:
            raise ValueError("MCP package requires an explicit bin_name")
    executable = safe_path(package_root, binary)
    if not executable.is_file():
        raise ValueError("MCP entrypoint was not installed")
    return {**pinned, "entrypoint": executable.relative_to(root).as_posix(), "runtime": "installed",
            "dependency_lock": dependency_lock.relative_to(root).as_posix()}


def configure_mcp(root: Path, tools: list[dict], state: dict, *, dry_run=False) -> list[str]:
    target = safe_path(root, ".codex/config.toml")
    original = target.read_text(encoding="utf-8-sig") if target.exists() else ""
    tomllib.loads(original)
    current = original
    managed = state.setdefault("config_blocks", {})
    notes = []
    for tool in tools:
        if "mcp" not in tool:
            continue
        name, mcp = tool["id"], tool["mcp"]
        start, end = f"# BEGIN agent-toolkit:{name}", f"# END agent-toolkit:{name}"
        pattern = re.compile(re.escape(start) + r"\n.*?" + re.escape(end) + r"\n?", re.S)
        match = pattern.search(current)
        data = tomllib.loads(current)
        if not match and name in data.get("mcp_servers", {}):
            notes.append(f"{name}: preserved existing MCP configuration")
            continue
        if match and managed.get(name) != text_hash(match.group(0)):
            notes.append(f"{name}: preserved customized MCP block")
            continue
        fields = {"enabled": tool.get("enabled", True)}
        if mcp["transport"] == "http":
            fields["url"] = mcp["url"]
            if mcp.get("credential_env"):
                fields["bearer_token_env_var"] = mcp["credential_env"]
        else:
            fields.update(command="python", args=[str(root / ".agent-toolkit/mcp_launch.py"), name],
                          cwd=str(root), startup_timeout_sec=60,
                          env_vars=[mcp["credential_env"]] if mcp.get("credential_env") else [])
        block = start + f"\n[mcp_servers.{name}]\n"
        for key, value in fields.items():
            block += key + " = " + (str(value).lower() if isinstance(value, bool) else json.dumps(value)) + "\n"
        block += end + "\n"
        current = pattern.sub(lambda _: block, current, count=1) if match else current.rstrip() + "\n\n" + block
        managed[name] = text_hash(block)
        notes.append(f"{name}: configured; reload Codex to load changes")
    if current != original and not dry_run and not any("preserved" in note for note in notes):
        tomllib.loads(current)
        atomic_text(target, current)
    return notes


def mcp_configs(root: Path) -> list[dict]:
    """Expose names and presence only, never credentials or raw configuration."""
    provider = read_json(safe_path(root, ".agent-toolkit/project.json"), {}).get("provider")
    result = []
    if provider == "codex":
        home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        entries = [("user", toml_data(home / "config.toml").get("mcp_servers", {})),
                   ("project", toml_data(safe_path(root, ".codex/config.toml")).get("mcp_servers", {}))]
    elif provider == "claude":
        entries = [("project", read_json(safe_path(root, ".mcp.json"), {}).get("mcpServers", {}))]
    elif provider == "opencode":
        entries = [("project", read_json(safe_path(root, "opencode.json"), {}).get("mcp", {}))]
    else:
        return []
    for scope, servers in entries:
        for name, config in servers.items():
            env_names = list(config.get("env_vars", []))
            env_names += list(config.get("env_http_headers", {}).values())
            if config.get("bearer_token_env_var"):
                env_names.append(config["bearer_token_env_var"])
            if provider != "codex":
                encoded = json.dumps(config)
                env_names += re.findall(r"\$\{([A-Z0-9_]+)\}|\{env:([A-Z0-9_]+)\}", encoded)
                env_names = [next(value for value in item if value) if isinstance(item, tuple) else item for item in env_names]
            result.append({"id": name, "scope": scope, "enabled": config.get("enabled", True),
                           "credential_presence": {key: bool(os.environ.get(key)) for key in env_names},
                           "runtime": "not-probed"})
    return result
