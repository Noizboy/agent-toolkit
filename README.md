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

## Included skills and MCPs

Setup prepares **31 skills and 2 MCP configurations**, using **15 registered tool sources** and the built-in toolkit skill. The full project inventory is available through `manage.py list`.

### MCP servers

| Server | Setup | Credential variable |
| --- | --- | --- |
| [Context7](https://github.com/upstash/context7) | HTTP server for current documentation | `CONTEXT7_API_KEY` |
| [TestSprite](https://docs.testsprite.com/mcp/getting-started/installation) | Isolated npm runtime and stdio configuration for testing | `TESTSPRITE_API_KEY` |

Provide the credential variables in your environment and approve the MCPs in your selected client.

<details>
<summary>All 31 skills, grouped by source</summary>

| Source | Included skills |
| --- | --- |
| [Agent Toolkit](.agents/skills/agent-toolkit/SKILL.md) | `agent-toolkit` |
| [context7](https://github.com/upstash/context7) | `context7-mcp` |
| [cyber-neo](https://github.com/Hainrixz/cyber-neo) | `cyber-neo` |
| [thermo-nuclear-code-quality-review](https://www.skills.sh/cursor/plugins/thermo-nuclear-code-quality-review) | `thermo-nuclear-code-quality-review` |
| [ponytail](https://github.com/DietrichGebert/ponytail) | `ponytail`, `ponytail-audit`, `ponytail-debt`, `ponytail-gain`, `ponytail-help`, `ponytail-review` |
| [impeccable](https://github.com/pbakaus/impeccable) | `impeccable` |
| [ui-ux-pro-max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | `ui-ux-pro-max` |
| [graphify](https://github.com/Graphify-Labs/graphify) | `graphify` |
| [design-md](https://github.com/google-labs-code/design.md) | `design-md` |
| [strix](https://github.com/usestrix/strix) | `api-security-testing`, `application-security-testing`, `ci-security-scanning-with-strix`, `find-security-vulnerabilities-in-code`, `fix-security-vulnerabilities-with-strix`, `managed-pentesting-with-strix`, `owasp-top-10-testing`, `penetration-testing-with-strix`, `web-app-penetration-testing` |
| [taste-skill](https://github.com/Leonxlnx/taste-skill) | `taste-skill`, `gpt-tasteskill`, `redesign-skill` |
| [spec-kit](https://github.com/github/spec-kit) | `spec-kit` |
| [clawscan](https://github.com/openclaw/clawscan) | `clawscan-cli` |
| [lighthouse](https://github.com/GoogleChrome/lighthouse) | `lighthouse-verification`, `lighthouse` |
| [boneyard](https://github.com/0xGF/boneyard) | `boneyard` |

</details>

Skills and source adapters are prepared locally. Optional **graphify, Strix, Specify, ClawScan and Lighthouse CLI runtimes** require separate installation; Strix also requires Docker and model credentials. The optional `boneyard-js` application dependency is not added automatically. Setup does not run tests, scans or pentests.
