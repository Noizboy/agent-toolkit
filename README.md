# Agent Toolkit

A reusable, provider-neutral agent team, project-local skills/MCP manager and Windows setup wizard.

Download **AgentToolkitSetup.exe** from the [latest release](https://github.com/Noizboy/agent-toolkit/releases/latest), then double-click it. Enter the project name, description, target folder and the client/provider environment to use: ChatGPT/Codex, Anthropic/Claude Code or OpenCode. The installer records the initial provider and model mapping. Explicit model-selection requests can subsequently update supported project model settings through the reusable prompt and synchronization command.

Git, Python 3.11+ and Node.js/npm are required. This repository is public; downloading the release and default toolkit source does not require GitHub sign-in. Private alternate sources require GitHub CLI authentication with `gh auth login`. Credentials remain in the environment or keychain and are never copied into the toolkit.

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
- [Prompt for choosing agent models](.agent-toolkit/prompts/select-agent-models.md)

## Prompt to assign agent models

After installation, open the target project in your selected AI client and paste this prompt:

```text
Read .agent-toolkit/prompts/select-agent-models.md and apply the most suitable currently available models for this project's agents using the Balanced profile. Consult current official sources, verify model identifiers and availability for the selected client and underlying provider, and justify the assignments. Use the model tiers and configuration supported by this toolkit, preserve custom configuration, and keep the selected provider. Record the evidence and any availability limitations in AGENT-MODEL-SELECTION.md, apply supported settings, and synchronize the generated agents. Respond in the language I use in this conversation.
```

Replace `Balanced` with `Maximum Quality` or `Economy` to change the selection priorities. The AI reads the detailed instructions, researches available models and can update `.agent-toolkit/project.json` and supported tier mappings. The current adapter uses provider-wide strong, light and escalation settings; it does not support arbitrary model overrides for every role.

Review the resulting `AGENT-MODEL-SELECTION.md`, then reload the selected client if needed. This request authorizes supported configuration changes; it does not authorize paid evaluation calls or switch the active chat model. A documented model assignment alone does not prove account access or a successful inference.

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

The current release is **v0.2.1**, which includes the reusable model-selection prompt. Installed older toolkit revisions are preserved during source updates; review and merge source/routing collisions deliberately. The v0.1.0 layout additionally needs a project migration to the neutral shared directory.

There are 13 roles and 15 registered tool sources. Optional audit CLIs have separate runtime prerequisites; setup does not execute audits, tests, scans or pentests. Before security-sensitive implementation, agents consult current official OWASP guidance and record controls and verification evidence.

All maintained toolkit instructions are in English. Third-party skills retain upstream licenses and authorship. The executable is unsigned and does not request administrator privileges.
