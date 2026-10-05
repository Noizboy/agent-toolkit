"""Project-local client adapters. Plan every collision before changing any file.

Canonical cards and complete skills stay in .agent-toolkit/agents and .agents/skills.
The state records ownership, never credentials or runtime availability.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import shutil

from configuration import agent_metadata, configure_mcp, sync_agents
from sources import atomic_text, read_json, safe_path, save_json, tree_hash, validate_tool

PROVIDERS = ("codex", "claude", "opencode")
DEFAULT_MODELS = {
    "codex": ("gpt-6.1-sol", "gpt-6-luna", "gpt-6-astra"),
    "claude": ("sonnet", "haiku", "opus"),
    "opencode": ("openai/gpt-6.1-sol", "openai/gpt-6-luna", "openai/gpt-6-astra"),
}


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _value_hash(value) -> str:
    return _hash(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


def _models(provider: str, settings: dict) -> dict[str, str]:
    keys = ("strong_model", "light_model", "escalation_model")
    models = dict(zip(keys, DEFAULT_MODELS[provider]))
    for key in keys:
        value = settings.get(key, models[key])
        if not isinstance(value, str):
            raise ValueError(f"Invalid {provider} {key}")
        if provider == "claude":
            valid = value in {"sonnet", "haiku", "opus"} or re.fullmatch(r"claude-[a-z0-9-]+", value)
        elif provider == "opencode":
            valid = re.fullmatch(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_./:-]+", value)
        else:
            valid = value in {"gpt-6.1-sol", "gpt-6-sol", "gpt-6-luna", "gpt-6-astra"}
        if not valid:
            raise ValueError(f"Invalid {provider} {key}; use a documented client model identifier")
        models[key] = value
    return models


def _routing(provider: str, models: dict) -> str:
    label = {"codex": "ChatGPT / Codex", "claude": "Claude Code", "opencode": "OpenCode"}[provider]
    native = {"codex": ".codex/agents", "claude": ".claude/agents", "opencode": ".opencode/agents"}[provider]
    return (f"Selected client: {label}. Canonical role cards are provider-neutral and live in "
            ".agent-toolkit/agents. Keep their workflow, boundaries and escalation criteria.\n"
            f"Use {models['strong_model']} for strong roles, {models['light_model']} for light roles, "
            f"and {models['escalation_model']} only after repeated failures or unresolved high-risk design.\n"
            f"Use generated {native} definitions for native client execution. "
            "Installation configures only the selected client. Configuration does not establish runtime availability.")


class _Plan:
    """Deferred writes plus granular hashes for mixed user/toolkit configuration."""

    def __init__(self, root: Path, state: dict):
        self.root = root
        self.state = copy.deepcopy(state)
        for kind in ("files", "entries", "blocks", "skills"):
            self.state.setdefault(kind, {})
        self.writes: dict[Path, str] = {}
        self.copies: list[tuple[Path, Path]] = []
        self.conflicts: list[str] = []

    def conflict(self, relative: str):
        self.conflicts.append(f"conflict: preserved customized or unmanaged {relative}; provider configuration unchanged")

    def file(self, relative: str, text: str):
        path = safe_path(self.root, relative)
        previous = self.state["files"].get(relative)
        if path.exists():
            if not path.is_file():
                self.conflict(relative)
                return
            current = _hash(path.read_bytes())
            if previous != current:
                if previous or path.read_bytes() != text.encode():
                    self.conflict(relative)
                return
        self.writes[path] = text
        self.state["files"][relative] = _hash(text.encode())

    def block(self, relative: str, name: str, body: str):
        path = safe_path(self.root, relative)
        original = path.read_text(encoding="utf-8-sig") if path.exists() else ""
        start, end = f"<!-- BEGIN {name} -->", f"<!-- END {name} -->"
        key = relative + "#" + name
        pattern = re.compile(re.escape(start) + r"\n.*?" + re.escape(end) + r"\n?", re.S)
        matches = list(pattern.finditer(original))
        if len(matches) > 1 or original.count(start) != len(matches) or original.count(end) != len(matches):
            self.conflict(relative + " block " + name)
            return
        rendered = start + "\n" + body + "\n" + end + "\n"
        if matches:
            old = matches[0].group()
            if self.state["blocks"].get(key) != _hash(old.encode()):
                self.conflict(relative + " block " + name)
                return
            updated = pattern.sub(lambda _: rendered, original, count=1)
        else:
            updated = original.rstrip() + ("\n\n" if original else "") + rendered
        self.writes[path] = updated
        self.state["blocks"][key] = _hash(rendered.encode())

    def entry(self, relative: str, config: dict, keys: tuple[str, ...], value, default=False, additive=False):
        key = relative + "#" + "/".join(keys)
        container = config
        for name in keys[:-1]:
            container = container.setdefault(name, {})
            if not isinstance(container, dict):
                raise ValueError(f"Invalid configuration object in {relative}")
        name = keys[-1]
        previous = self.state["entries"].get(key)
        if name in container:
            current = _value_hash(container[name])
            if previous != current:
                if previous or (not default and not additive and container[name] != value):
                    self.conflict(key)
                if previous or not additive:
                    return
        container[name] = value
        self.state["entries"][key] = _value_hash(value)

    def skill(self, source: Path):
        relative = ".claude/skills/" + source.name
        target = safe_path(self.root, relative)
        source_hash = tree_hash(source)
        previous = self.state["skills"].get(relative)
        if target.exists():
            if not target.is_dir() or previous != tree_hash(target):
                self.conflict(relative)
                return
        # Validate every payload destination before copying, including nested resources.
        for item in source.rglob("*"):
            safe_path(target, item.relative_to(source).as_posix())
        if not target.exists() or tree_hash(target) != source_hash:
            self.copies.append((source, target))
        self.state["skills"][relative] = source_hash

    def json(self, relative: str, config: dict):
        self.writes[safe_path(self.root, relative)] = json.dumps(config, ensure_ascii=False, indent=2) + "\n"


def _mcp(root: Path, provider: str, tool: dict, lock: dict) -> dict:
    validate_tool(tool)
    mcp = tool["mcp"]
    credential = mcp.get("credential_env")
    placeholder = ("${" + credential + "}" if provider == "claude" else "{env:" + credential + "}") if credential else None
    if mcp["transport"] == "http":
        config = {"type": "http" if provider == "claude" else "remote", "url": mcp["url"]}
        if credential:
            # Context7 documents a named key header, rather than a bearer token.
            header = "CONTEXT7_API_KEY" if tool["id"] == "context7" else "Authorization"
            config["headers"] = {header: placeholder if header == "CONTEXT7_API_KEY" else "Bearer " + placeholder}
        if provider == "opencode":
            config.update(enabled=True, oauth=False)
        return config
    if mcp["transport"] != "stdio":
        raise ValueError("Unsupported MCP transport")
    runtime = lock.get("tools", {}).get(tool["id"], {}).get("npm", {})
    entry = runtime.get("entrypoint")
    if not entry or not runtime.get("version") or not safe_path(root, entry).is_file():
        raise ValueError(f"Pinned MCP runtime missing for {tool['id']}; run bootstrap first")
    validate_tool({"id": tool["id"], "mcp": {"version": runtime["version"]}})
    expected = f".agent-toolkit/runtime/{tool['id']}/{runtime['version']}/"
    if not entry.startswith(expected):
        raise ValueError(f"MCP entrypoint outside pinned runtime for {tool['id']}")
    command = shutil.which("node") or "node"
    arguments = [str(safe_path(root, entry))]
    env = {mcp.get("server_env", credential): placeholder} if credential else {}
    if provider == "claude":
        return {"type": "stdio", "command": command, "args": arguments, "env": env}
    return {"type": "local", "command": [command, *arguments], "cwd": str(root), "enabled": True, "environment": env}


def configure_provider(root: Path, provider: str, settings: dict, *, dry_run=False) -> list[str]:
    """Configure after Toolkit.bootstrap; [] means success, messages mean no writes.

    dry_run performs the same complete preflight without writes. It needs the
    canonical payload and pinned MCP runtime already present in root.
    """
    if provider not in PROVIDERS:
        return ["Unknown provider; choose codex, claude or opencode"]
    try:
        root = root.resolve()
        models = _models(provider, settings)
        state_path = safe_path(root, ".agent-toolkit/provider-state.json")
        state = read_json(state_path, {"schema_version": 1})
        if not isinstance(state, dict) or state.get("schema_version") != 1:
            raise ValueError("Unsupported provider state")
        if any(not isinstance(state.get(kind, {}), dict) for kind in ("files", "entries", "blocks", "skills")):
            raise ValueError("Invalid provider ownership state")
        plan = _Plan(root, state)
        cards = safe_path(root, ".agent-toolkit/agents")
        role_cards = [safe_path(cards, card.name) for card in sorted(cards.glob("*.md"))]
        if not any(agent_metadata(card).get("model_tier") for card in role_cards):
            raise ValueError("Canonical agent cards missing; run bootstrap first")
        routing = _routing(provider, models)
        plan.block("AGENTS.md", "agent-toolkit:provider-routing", routing)
        registry = read_json(safe_path(root, ".agent-toolkit/registry.json"), {})
        lock_path = safe_path(root, ".agent-toolkit/tools.lock.json")
        lock = read_json(lock_path, {})
        tools = [tool for tool in registry.get("tools", []) if tool.get("enabled", True)]
        if provider == "codex":
            preflight_state = copy.deepcopy(lock)
            statuses = sync_agents(root, preflight_state, models, dry_run=True)
            statuses += configure_mcp(root, tools, preflight_state, dry_run=True)
            for status in statuses:
                if "preserved" in status:
                    plan.conflict("Codex: " + status)
        if provider != "codex":
            folder = ".claude" if provider == "claude" else ".opencode"
            roles = []
            mapping = {"strong": models["strong_model"], "light": models["light_model"],
                       "escalation": models["escalation_model"]}
            for card in role_cards:
                meta = agent_metadata(card)
                if not meta.get("model_tier"):
                    continue
                name = re.sub(r"[^a-z0-9]+", "-", card.stem.lower()).strip("-")
                if not name or name in roles or meta["model_tier"] not in mapping:
                    raise ValueError("Invalid or duplicate canonical agent tier/name")
                roles.append(name)
                body = card.read_text(encoding="utf-8-sig").split("---", 2)[2].strip()
                body = body.replace("the selected provider's escalation model", models["escalation_model"])
                fields = {"description": meta["description"], "model": mapping[meta["model_tier"]]}
                if provider == "claude":
                    fields = {"name": name, **fields}
                else:
                    fields["mode"] = "primary" if card.stem == "Orchestrator" else "subagent"
                rendered = "---\n" + "\n".join(f"{key}: {json.dumps(value)}" for key, value in fields.items()) + "\n---\n\n"
                rendered += routing + "\n\nRead .agent-toolkit/agents/Agent-Contract.md before work.\n\n" + body + "\n"
                plan.file(folder + "/agents/" + name + ".md", rendered)
            if not roles:
                raise ValueError("Canonical agent cards missing; run bootstrap first")
            native_agents = safe_path(root, folder + "/agents")
            for existing in native_agents.rglob("*.md") if native_agents.is_dir() else []:
                safe_path(root, existing.relative_to(root).as_posix())
                name = agent_metadata(existing).get("name") if provider == "claude" else existing.stem
                if name in roles and existing != native_agents / (name + ".md"):
                    plan.conflict(existing.relative_to(root).as_posix() + " duplicate agent " + name)
            skills = safe_path(root, ".agents/skills")
            for source in sorted(skills.iterdir()) if skills.is_dir() else []:
                safe_path(skills, source.name)
                if source.is_dir() and (source / "SKILL.md").is_file():
                    tree_hash(source)
                    if provider == "claude":
                        plan.skill(source)
            relative = ".mcp.json" if provider == "claude" else "opencode.json"
            if provider == "opencode" and safe_path(root, "opencode.jsonc").exists():
                plan.conflict("opencode.jsonc (review and merge the existing JSONC configuration first)")
            config = read_json(safe_path(root, relative), {})
            if not isinstance(config, dict):
                raise ValueError(f"Invalid configuration object in {relative}")
            if provider == "opencode":
                configured_agents = config.get("agent", {})
                if not isinstance(configured_agents, dict):
                    raise ValueError("OpenCode agent must be an object")
                for name in roles:
                    if name in configured_agents:
                        plan.conflict(relative + "#agent/" + name)
            for tool in tools:
                if "mcp" in tool:
                    value = _mcp(root, provider, tool, lock)
                    plan.entry(relative, config, ("mcpServers" if provider == "claude" else "mcp", tool["id"]), value)
            if provider == "claude":
                plan.block("CLAUDE.md", "agent-toolkit:claude", "@AGENTS.md\n\n" + routing + "\n\n"
                           "Read .agent-toolkit/agents/Orchestrator.md and Agent-Contract.md. At session start, run "
                           "`python .agent-toolkit/manage.py bootstrap` once, then `python .agent-toolkit/manage.py list`. "
                           "Respect normal client permissions and preserve project changes.")
            else:
                defaults = {"$schema": "https://opencode.ai/config.json", "model": models["strong_model"],
                            "small_model": models["light_model"]}
                if "orchestrator" in roles:
                    defaults["default_agent"] = "orchestrator"
                for key, value in defaults.items():
                    plan.entry(relative, config, (key,), value, default=True)
                instructions = config.get("instructions", [])
                if not isinstance(instructions, list) or any(not isinstance(item, str) for item in instructions):
                    raise ValueError("OpenCode instructions must be an array of paths")
                plan.entry(relative, config, ("instructions",), list(dict.fromkeys([*instructions, "AGENTS.md"])), additive=True)
            plan.json(relative, config)
        ignored = safe_path(root, ".agent-toolkit/.gitignore")
        original = ignored.read_text(encoding="utf-8-sig") if ignored.exists() else ""
        if "/provider-state.json" not in original.splitlines():
            plan.writes[ignored] = original.rstrip() + ("\n" if original else "") + "/provider-state.json\n"
        if plan.conflicts:
            return plan.conflicts
        if dry_run:
            return []
        if provider == "codex":
            statuses = sync_agents(root, lock, models)
            statuses += configure_mcp(root, tools, lock)
            preserved = [status for status in statuses if "preserved" in status]
            if preserved:
                return ["Provider files changed since preflight; " + status for status in preserved]
            save_json(lock_path, lock)
        for source, target in plan.copies:
            # Targets were checked against root and all reparse points in preflight.
            safe_path(root, target.relative_to(root).as_posix())
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)
        for path, content in plan.writes.items():
            atomic_text(path, content)
        plan.state.update(provider=provider, settings=models)
        save_json(state_path, plan.state)
        return []
    except (OSError, ValueError, KeyError, TypeError) as error:
        # Bounded diagnostics do not dump config, credentials, or subprocess output.
        return ["Provider configuration failed: " + (str(error) if isinstance(error, ValueError) else type(error).__name__)]
