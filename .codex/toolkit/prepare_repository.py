"""Copy only the reusable toolkit into an empty standalone repository directory."""
from pathlib import Path
import argparse
import os
import shutil

from sources import read_json, safe_path, save_json


def prepare(source: Path, destination: Path):
    destination = destination.absolute()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("The standalone repository destination must be empty.")
    destination.mkdir(parents=True, exist_ok=True)
    excluded = {"vendor", "runtime", "__pycache__", ".build-venv", "installer-build", "installer-dist"}
    private = {"tools.lock.json", "inventory.json", "INVENTORY.md", "mcp-probes.json",
               "project.json", "provider-state.json", "installation.json"}
    toolkit = source / ".codex/toolkit"
    for folder, directories, filenames in os.walk(toolkit, followlinks=False):
        directories[:] = [name for name in directories if name not in excluded]
        for filename in filenames:
            if filename in private:
                continue
            file = Path(folder) / filename
            relative = file.relative_to(source).as_posix()
            safe_path(source, relative)
            target = safe_path(destination, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)
    for file in (source / ".codex/agents").iterdir():
        if file.suffix not in {".md", ".toml"}:
            continue
        target = safe_path(destination, ".codex/agents/" + file.name)
        safe_path(source, file.relative_to(source).as_posix())
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, target)
    target = destination / ".agents/skills/agent-toolkit/SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / ".agents/skills/agent-toolkit/SKILL.md", target)
    state = read_json(toolkit / "tools.lock.json", {"tools": {}})
    portable = {"schema_version": 1, "tools": {}}
    for name, record in state["tools"].items():
        portable["tools"][name] = {key: record[key] for key in ["source", "commit"] if key in record}
        if record.get("npm"):
            portable["tools"][name]["npm"] = {key: record["npm"][key] for key in ["package", "version", "integrity"]}
    save_json(destination / ".codex/toolkit/tools.lock.json", portable)
    shutil.copy2(toolkit / "AGENTS.template.md", destination / "AGENTS.md")
    ignores = (toolkit / "gitignore.template").read_text(encoding="utf-8")
    ignores += "\n.codex/toolkit/.build-venv/\n.codex/toolkit/installer-build/\n.codex/toolkit/installer-dist/\n**/__pycache__/\n*.env\n.env\n"
    (destination / ".gitignore").write_text(ignores, encoding="utf-8")
    (destination / "README.md").write_text('''# Agent Toolkit

A reusable agent team, project-local skills/MCP manager and English Windows setup wizard.

Download **AgentToolkitSetup.exe** from the [latest release](https://github.com/Noizboy/agent-toolkit/releases/latest), then double-click it. Enter your project name, description, folder and provider/environment: ChatGPT/Codex, Anthropic/Claude Code or OpenCode.

Git, Python 3.11+ and Node.js/npm are required. For this private repository, authenticate with GitHub CLI using `gh auth login` before downloading/installing. The installer downloads a selected repository revision and restores pinned tool versions; credentials remain in your environment/keychain.

- [Setup and build instructions](.codex/toolkit/INSTALLER.md)
- [Agent roles and models](.codex/agents/README.md)
- [Reusable AGENTS.md template](.codex/toolkit/AGENTS.template.md)
- [Editable tool registry](.codex/toolkit/registry.json)
- [Security policy](.codex/agents/Security-Policy.md)

To install from a checkout:

```text
python .codex/toolkit/installer.py
```

After installation, run these inside the target project:

```text
python .codex/toolkit/manage.py list
python .codex/toolkit/manage.py update
```

There are 13 roles and 15 registered tool sources. Codex uses GPT-6.1 Sol/GPT-6 Luna with GPT-6 Astra escalation; Claude uses Sonnet/Haiku aliases with Opus escalation; OpenCode accepts configurable provider/model IDs. Client authentication and model availability are separate from configuration.

Existing project instructions and custom skills/configuration are preserved. Unresolved conflicts are reported. Optional audit CLIs have separate runtime prerequisites; setup does not execute audits, tests or pentests. Before security-sensitive implementation, agents must consult current official OWASP guidance and record controls and verification evidence.

All maintained toolkit instructions are in English. Third-party skills are fetched from their upstream repositories and retain upstream licenses and authorship. The executable is unsigned and does not request administrator privileges.
''', encoding="utf-8")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    print(prepare(Path(__file__).resolve().parents[2], args.destination))
