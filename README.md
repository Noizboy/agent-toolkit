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

Keep **Guide optional tool setup after installation** enabled to continue with:

- Selected project-local Strix, Spec Kit/Specify, ClawScan, Lighthouse and Graphify runtimes.
- Strix access through its ChatGPT browser sign-in or an API provider/model.
- Masked Context7/TestSprite keys and managed MCP connection checks.

Docker stays a manual prerequisite: the guide checks its CLI and daemon and links the official installation instructions. Keys are session-only by default; optional Windows user environment storage is plaintext and requires explicit selection. No scans or model calls run during setup.

### 4. Open your AI client

Open the target project, sign in to your model provider and approve its MCP servers. Reload the client if needed. Add your project's purpose and conventions to `AGENTS.md`.

### 5. Assign models to the agents

Paste this prompt into the AI inside your installed project:

```text
Read .agent-toolkit/prompts/select-agent-models.md and apply the Balanced profile to select and configure the best available models for each agent. Verify current official sources and actual client/provider availability, preserve custom settings and the selected provider, synchronize agents, and record the results in AGENT-MODEL-SELECTION.md. Respond in the language I use in this conversation.
```

Use `Maximum Quality` or `Economy` instead of `Balanced` if preferred. Review the report and reload your client to load configuration changes.

## Maintenance

Run these commands from the target project folder:

| Command | Purpose |
| --- | --- |
| `python .agent-toolkit/manage.py list` | Lists agents, skills and MCP configuration; refreshes the full inventory. |
| `python .agent-toolkit/manage.py setup` | Reopens guided optional tool installation, Strix access and MCP checks. |
| `python .agent-toolkit/manage.py install-runtime strix` | Installs a reviewed project-local CLI; replace `strix` with `spec-kit`, `clawscan`, `lighthouse` or `graphify`. |
| `python .agent-toolkit/manage.py run-tool strix -- --help` | Runs an installed project-local CLI explicitly; replace the tool/arguments as needed. |
| `python .agent-toolkit/manage.py doctor` | Checks for missing files, credentials and required runtimes. |
| `python .agent-toolkit/manage.py doctor --probe-mcp` | Checks setup and MCP communication by initializing servers and listing their tools. |
| `python .agent-toolkit/manage.py update` | Updates registered skills/MCP packages from their declared sources, preserving customized files. |

Read `.agent-toolkit/INVENTORY.md` for the full inventory and `.agent-toolkit/mcp-probes.json` for connection-check results. A `verified` MCP result confirms protocol communication; client loading and model access need separate checks. Optional audit tools have additional requirements. These checks do not run application tests, scans or pentests.

## Documentation

- [Setup, upgrades and builds](.agent-toolkit/INSTALLER.md)
- [Agent roles](.agent-toolkit/agents/README.md) and [AGENTS.md template](.agent-toolkit/AGENTS.template.md)
- [Tool registry](.agent-toolkit/registry.json) and [model-selection instructions](.agent-toolkit/prompts/select-agent-models.md)
- [Security policy and current OWASP guidance](.agent-toolkit/agents/Security-Policy.md)

## Included skills and MCPs

Each main skill/toolkit is listed once below. Bundled subskills remain included in setup; use `manage.py list` for the full project inventory.

### MCP servers

| Server | Purpose and connection | Credential variable |
| --- | --- | --- |
| [Context7](https://github.com/upstash/context7) | Retrieves current library/API documentation over HTTP | `CONTEXT7_API_KEY` |
| [TestSprite](https://docs.testsprite.com/mcp/getting-started/installation) | Connects the AI to TestSprite's application-testing tools through a local stdio runtime | `TESTSPRITE_API_KEY` |

Provide the credential variables in your environment and approve the MCPs in your selected client.

<details>
<summary>Skills and toolkits</summary>

| Skill / toolkit | Purpose |
| --- | --- |
| [agent-toolkit](.agents/skills/agent-toolkit/SKILL.md) | Installs, inventories, updates and exports project agents and tools. |
| [cyber-neo](https://github.com/Hainrixz/cyber-neo) | Audits dependencies, code, secrets and security configuration. |
| [thermo-nuclear-code-quality-review](https://www.skills.sh/cursor/plugins/thermo-nuclear-code-quality-review) | Reviews maintainability, abstractions and unnecessary code complexity. |
| [ponytail](https://github.com/DietrichGebert/ponytail) | Simplifies implementation and reviews, and tracks deliberate technical debt. |
| [impeccable](https://github.com/pbakaus/impeccable) | Designs and refines frontend interfaces and user experience. |
| [ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | Guides interface design, accessibility and layout across platforms. |
| [graphify](https://github.com/Graphify-Labs/graphify) | Builds a searchable knowledge graph of project files and relationships. |
| [design.md](https://github.com/google-labs-code/design.md) | Defines and preserves visual identity through DESIGN.md. |
| [strix](https://github.com/usestrix/strix) | Tests application, API and code security, and guides verified fixes. |
| [taste-skill](https://github.com/Leonxlnx/taste-skill) | Creates distinctive interfaces and improves existing designs. |
| [spec-kit](https://github.com/github/spec-kit) | Defines requirements, acceptance criteria and implementation plans. |
| [clawscan](https://github.com/openclaw/clawscan) | Scans agent skills for security and supply-chain risks. |
| [lighthouse](https://github.com/GoogleChrome/lighthouse) | Measures web performance, accessibility and best practices. |
| [boneyard](https://github.com/0xGF/boneyard) | Builds skeleton loading screens. |

</details>

Skills and source adapters are prepared locally. The guided step installs selected optional CLI runtimes from their official publisher distributions, checks artifact integrity and preserves existing global tools. Strix also requires Docker and a supported model/authentication method; Lighthouse needs a supported browser for audits. Unsupported platforms or distributions receive manual guidance. The optional `boneyard-js` application dependency is not added automatically. Setup does not run tests, scans or pentests.
