# Agent Toolkit

13 reusable agents, project-local skills and MCP configuration for **ChatGPT/Codex, Claude Code and OpenCode**. Setup downloads the latest stable release and configures only your selected client.

## Installation

### 1. Install the requirements

Install [Python 3.11+](https://www.python.org/downloads/windows/), [Git](https://git-scm.com/downloads) and [Node.js/npm](https://nodejs.org/en/download), with their commands available on PATH. These are required even when using the Windows executable.

### 2. Open the installer

Download or clone this repository and double-click **AgentToolkitSetup.exe** in the root folder. You can also download the executable from the [latest release](https://github.com/Noizboy/agent-toolkit/releases/latest).

To use Python instead, run from the repository root:

```powershell
python installer.py
```

### 3. Configure your project

Enter the **project name**, choose its **folder**, select your **client/provider**, then click **Install toolkit**. Choose a target folder outside this toolkit checkout. OpenCode also asks for provider/model IDs.

Existing instructions and custom settings are preserved; setup reports any conflicts.

### 4. Open your AI client

Open the target project, sign in to your model provider and approve its MCP servers. Reload the client if needed. Add your project's purpose and conventions to `AGENTS.md`.

### 5. Assign models to the agents

Paste this prompt into the AI inside your installed project:

```text
Read .agent-toolkit/prompts/select-agent-models.md and apply the Balanced profile to select and configure the best available models for each agent. Verify current official sources and actual client/provider availability, preserve custom settings and the selected provider, synchronize agents, and record the results in AGENT-MODEL-SELECTION.md. Respond in the language I use in this conversation.
```

Use `Maximum Quality` or `Economy` instead of `Balanced` if preferred. Review the report and reload your client to load configuration changes.

## Maintenance

Run from the target project folder:

```powershell
python .agent-toolkit/manage.py list
python .agent-toolkit/manage.py doctor
python .agent-toolkit/manage.py update
```

These list installed tools, check setup and update registered skills/MCP tools. The full inventory is `.agent-toolkit/INVENTORY.md`. Optional audit tools have additional requirements; installation does not start scans or tests.

## Documentation

- [Setup, upgrades and builds](.agent-toolkit/INSTALLER.md)
- [Agent roles](.agent-toolkit/agents/README.md) and [AGENTS.md template](.agent-toolkit/AGENTS.template.md)
- [Tool registry](.agent-toolkit/registry.json) and [model-selection instructions](.agent-toolkit/prompts/select-agent-models.md)
- [Security policy and current OWASP guidance](.agent-toolkit/agents/Security-Policy.md)
