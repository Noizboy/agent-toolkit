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

| Server | Purpose and connection | Credential variable |
| --- | --- | --- |
| [Context7](https://github.com/upstash/context7) | Retrieves current library/API documentation over HTTP | `CONTEXT7_API_KEY` |
| [TestSprite](https://docs.testsprite.com/mcp/getting-started/installation) | Connects the AI to TestSprite's application-testing tools through a local stdio runtime | `TESTSPRITE_API_KEY` |

Provide the credential variables in your environment and approve the MCPs in your selected client.

<details>
<summary>All 31 skills and their purpose</summary>

| Skill | Purpose |
| --- | --- |
| [agent-toolkit](.agents/skills/agent-toolkit/SKILL.md) | Installs, inventories, updates and exports project agents and tools. |
| [api-security-testing](https://github.com/usestrix/strix) | Tests API authorization and other vulnerabilities using Strix. |
| [application-security-testing](https://github.com/usestrix/strix) | Selects security tests across application assets and prioritizes fixes. |
| [boneyard](https://github.com/0xGF/boneyard) | Builds and maintains skeleton loading screens with boneyard-js. |
| [ci-security-scanning-with-strix](https://github.com/usestrix/strix) | Adds Strix security checks to CI and pull-request workflows. |
| [clawscan-cli](https://github.com/openclaw/clawscan) | Scans agent skills for security and supply-chain risks. |
| [context7-mcp](https://github.com/upstash/context7) | Guides current documentation lookup through the Context7 MCP. |
| [cyber-neo](https://github.com/Hainrixz/cyber-neo) | Audits dependencies, code, secrets and security configuration. |
| [design-md](https://github.com/google-labs-code/design.md) | Applies and maintains visual design rules in DESIGN.md. |
| [find-security-vulnerabilities-in-code](https://github.com/usestrix/strix) | Guides source-code security review and exploit validation with Strix. |
| [fix-security-vulnerabilities-with-strix](https://github.com/usestrix/strix) | Remediates Strix findings and retests the affected behavior. |
| [gpt-tasteskill](https://github.com/Leonxlnx/taste-skill) | Builds expressive interfaces with typography, layouts and GSAP motion. |
| [graphify](https://github.com/Graphify-Labs/graphify) | Maps project files and relationships into a queryable knowledge graph. |
| [impeccable](https://github.com/pbakaus/impeccable) | Designs, reviews and refines frontend interfaces and user experience. |
| [lighthouse](https://github.com/GoogleChrome/lighthouse) | Measures web performance, accessibility and best practices. |
| [lighthouse-verification](https://github.com/GoogleChrome/lighthouse) | Validates changes to Lighthouse itself, including tests and fixtures. |
| [managed-pentesting-with-strix](https://github.com/usestrix/strix) | Runs authorized security assessments through the managed Strix Cloud platform. |
| [owasp-top-10-testing](https://github.com/usestrix/strix) | Maps authorized Strix tests and findings to OWASP risk categories. |
| [penetration-testing-with-strix](https://github.com/usestrix/strix) | Guides authorized Strix penetration tests across supported targets. |
| [ponytail](https://github.com/DietrichGebert/ponytail) | Keeps implementations simple and avoids unnecessary dependencies or abstractions. |
| [ponytail-audit](https://github.com/DietrichGebert/ponytail) | Finds unnecessary complexity across the whole repository. |
| [ponytail-debt](https://github.com/DietrichGebert/ponytail) | Collects marked shortcuts and deferred work into a debt ledger. |
| [ponytail-gain](https://github.com/DietrichGebert/ponytail) | Displays published Ponytail benchmark results. |
| [ponytail-help](https://github.com/DietrichGebert/ponytail) | Explains Ponytail modes, skills and commands. |
| [ponytail-review](https://github.com/DietrichGebert/ponytail) | Reviews code changes for overengineering and opportunities to simplify. |
| [redesign-skill](https://github.com/Leonxlnx/taste-skill) | Improves existing interfaces while preserving their functionality. |
| [spec-kit](https://github.com/github/spec-kit) | Defines requirements, acceptance criteria and implementation plans. |
| [taste-skill](https://github.com/Leonxlnx/taste-skill) | Creates distinctive landing pages, portfolios and redesigns. |
| [thermo-nuclear-code-quality-review](https://www.skills.sh/cursor/plugins/thermo-nuclear-code-quality-review) | Performs strict reviews of maintainability and code structure. |
| [ui-ux-pro-max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | Guides interface design, accessibility and layout across platforms. |
| [web-app-penetration-testing](https://github.com/usestrix/strix) | Tests live web applications for exploitable security flaws with Strix. |

</details>

Skills and source adapters are prepared locally. Optional **graphify, Strix, Specify, ClawScan and Lighthouse CLI runtimes** require separate installation; Strix also requires Docker and model credentials. The optional `boneyard-js` application dependency is not added automatically. Setup does not run tests, scans or pentests.
