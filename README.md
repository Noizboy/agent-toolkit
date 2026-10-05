# Agent Toolkit

A reusable, provider-neutral agent team, project-local skills/MCP manager and Windows setup wizard.

Download **AgentToolkitSetup.exe** from the [latest release](https://github.com/Noizboy/agent-toolkit/releases/latest), then double-click it. Enter the project name, description, target folder and the client/provider environment to use: ChatGPT/Codex, Anthropic/Claude Code or OpenCode. The installer is the only place that selects the provider and its model settings.

Git, Python 3.11+ and Node.js/npm are required. For this private repository, authenticate with GitHub CLI using `gh auth login` before downloading/installing. Credentials remain in the environment or keychain and are never copied into the toolkit.

## Repository layout

The canonical, provider-neutral toolkit lives under `.agent-toolkit/`. The role cards use model tiers (`strong` and `light`) and contain no provider-specific model IDs. Native client files are generated only for the provider selected by the installer.

| Selected client | Generated native output | Skills location |
| --- | --- | --- |
| ChatGPT / Codex | `.codex/agents/`, `.codex/config.toml` | Canonical project skills remain under `.agents/skills/` when used by the client |
| Anthropic / Claude Code | `.claude/agents/`, `.claude/skills/`, `CLAUDE.md`, `.mcp.json` | `.claude/skills/` |
| OpenCode | `.opencode/agents/`, `opencode.json` | Shared `.agents/skills/` |

An uninstalled checkout has no provider-native `.codex/`, `.claude/` or `.opencode/` layout by default. The shared `.agents/skills/` directory is canonical project content. Existing project instructions and custom configuration are preserved; collisions are reported for deliberate migration.

## Documentation

- [Setup, migration and build instructions](.agent-toolkit/INSTALLER.md)
- [Agent roles, tiers and dispatch](.agent-toolkit/agents/README.md)
- [Reusable AGENTS.md template](.agent-toolkit/AGENTS.template.md)
- [Editable tool registry](.agent-toolkit/registry.json)
- [Security policy](.agent-toolkit/agents/Security-Policy.md)

## Install from a checkout

```text
python .agent-toolkit/installer.py
```

After installation, run these inside the target project:

```text
python .agent-toolkit/manage.py list
python .agent-toolkit/manage.py doctor
```

`bootstrap` and `sync-agents` use the provider recorded in `.agent-toolkit/project.json`. They do not infer a default provider from the canonical cards. Model tiers are mapped to the selected provider's configured strong, light and escalation models; generated native files do not change the primary chat model automatically.

The current release line is **v0.2.0**. A project installed from the older v0.1.0 layout is not automatically deleted or overwritten during source updates. Use a deliberate project migration after reviewing collisions and preserving custom files.

There are 13 roles and 15 registered tool sources. Optional audit CLIs have separate runtime prerequisites; setup does not execute audits, tests, scans or pentests. Before security-sensitive implementation, agents consult current official OWASP guidance and record controls and verification evidence.

All maintained toolkit instructions are in English. Third-party skills retain upstream licenses and authorship. The executable is unsigned and does not request administrator privileges.
