# Agent Toolkit

A reusable, provider-neutral agent team, project-local skills/MCP manager and Windows setup wizard.

Download **AgentToolkitSetup.exe** from the [latest release](https://github.com/Noizboy/agent-toolkit/releases/latest), then double-click it. Enter the project name, target folder and client/provider: ChatGPT/Codex, Anthropic/Claude Code or OpenCode. Setup automatically downloads the latest published stable toolkit release and records the initial provider and model mapping. Use the copyable prompt below to update supported model assignments later.

Git, Python 3.11+ and Node.js/npm are required. Downloading the installer and toolkit source requires no GitHub sign-in. Credentials remain in the environment or keychain and are never copied into the toolkit.

## Installation tutorial

### 1. Install the prerequisites

Install [Python for Windows](https://www.python.org/downloads/windows/) (3.11 or later), [Git](https://git-scm.com/downloads) and [Node.js](https://nodejs.org/en/download) with npm. Make sure they are available on PATH; when using the classic Python installer, enable **Add python.exe to PATH**. Reopen your terminal after installation and check:

```powershell
python --version
git --version
node --version
npm --version
```

The Windows executable includes its setup UI runtime, but Python is still required for the installed toolkit's maintenance commands. No Python package installation is needed to launch the source wizard.

### 2. Start setup

**Windows executable:** double-click **AgentToolkitSetup.exe** in the repository root. If you only need the executable, download it from the [latest release](https://github.com/Noizboy/agent-toolkit/releases/latest).

**Python installer:** if you already downloaded or cloned this repository, open a terminal in its extracted root folder and run:

```powershell
python installer.py
```

Both launch the same simplified wizard and download the latest published stable release from this repository. There is no repository, version or project-description input. Choose a target project folder outside the downloaded toolkit checkout.

### 3. Fill in the form

1. Enter the **Project name**.
2. Use **Browse...** to select the **Project folder**.
3. Select the **Provider / environment**: ChatGPT/Codex, Claude Code or OpenCode. OpenCode also shows editable model IDs for its underlying provider.
4. Click **Install toolkit** and wait for the result. Setup displays the downloaded release and reports missing prerequisites or conflicts.

### 4. Open your project

Open the target project in the selected AI client, sign in to that model provider and review/approve the project's MCP servers. Reload the client if it was already open. Add your project's purpose and conventions directly to its `AGENTS.md`; existing instructions and previously recorded descriptions are preserved.

Run these commands from the **target project folder** to see what was installed:

```powershell
python .agent-toolkit/manage.py list
python .agent-toolkit/manage.py doctor
```

The full skills/MCP inventory is `.agent-toolkit/INVENTORY.md`. Setup details, the selected release and exact source commit are in `.agent-toolkit/installation.json` and `.agent-toolkit/project.json`. Optional audit tools and missing credential variables are listed separately; setup does not start tests or security scans.

### 5. Select models and update tools

#### Prompt to assign agent models

After installation, open the target project in your selected AI client and paste this prompt:

```text
Read .agent-toolkit/prompts/select-agent-models.md and apply the most suitable currently available models for this project's agents using the Balanced profile. Consult current official sources, verify model identifiers and availability for the selected client and underlying provider, and justify the assignments. Use the model tiers and configuration supported by this toolkit, preserve custom configuration, and keep the selected provider. Record the evidence and any availability limitations in AGENT-MODEL-SELECTION.md, apply supported settings, and synchronize the generated agents. Respond in the language I use in this conversation.
```

Replace `Balanced` with `Maximum Quality` or `Economy` to change the selection priorities. The AI reads the detailed instructions, researches available models and can update `.agent-toolkit/project.json` and supported tier mappings. The current adapter uses provider-wide strong, light and escalation settings; it does not support arbitrary model overrides for every role.

Review the resulting `AGENT-MODEL-SELECTION.md`, then reload the selected client if needed. This request authorizes supported configuration changes; it does not authorize paid evaluation calls or switch the active chat model. A documented model assignment alone does not prove account access or a successful inference.

To update registered upstream skills/MCP tools later, run:

```powershell
python .agent-toolkit/manage.py update
```

Each new installer run checks the latest stable toolkit release. Existing customized files and older toolkit source are preserved; review reported merge conflicts when upgrading. If release discovery fails, setup stops instead of silently installing another revision.

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

## Install without the wizard

```text
python installer.py --install --project "C:/Projects/MyProject" --name "MyProject" --provider claude
```

Use `--provider codex`, `claude` or `opencode`. Scripted installation also downloads the latest stable release and requires no description, repository or version arguments.

`bootstrap` and `sync-agents` use the provider recorded in `.agent-toolkit/project.json`. They do not infer a default provider from the canonical cards. Model tiers are mapped to the selected provider's configured strong, light and escalation models; generated native files do not change the primary chat model automatically.

The current release is **v0.3.1**, with root-level Windows/Python installers and the model-selection prompt directly in tutorial step 5. The v0.1.0 layout additionally needs a project migration to the neutral shared directory.

There are 13 roles and 15 registered tool sources. Optional audit CLIs have separate runtime prerequisites; setup does not execute audits, tests, scans or pentests. Before security-sensitive implementation, agents consult current official OWASP guidance and record controls and verification evidence.

All maintained toolkit instructions are in English. Third-party skills retain upstream licenses and authorship. The executable is unsigned and does not request administrator privileges.
