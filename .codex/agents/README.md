# Generic agent toolkit

These role cards describe a reusable team for local projects. Each card has frontmatter for native configuration, but frontmatter alone does not switch the current session's primary model. Native configuration is generated separately; report unavailable models rather than inventing a replacement.

All agents read [Agent-Contract.md](Agent-Contract.md) before acting. Cards retain generic names and responsibilities so they can be installed in another project without assuming a domain, provider or framework. Maintain toolkit instructions, documentation and examples in English.

## Model matrix

| Role | Preferred model | Reasoning | Mode |
| --- | --- | --- | --- |
| Orchestrator | `gpt-6.1-sol` | `high` | `primary` |
| Requirements-Agent | `gpt-6-luna` | `medium` | `subagent` |
| Architecture-Agent | `gpt-6.1-sol` | `high` | `subagent` |
| Implementation-Agent | `gpt-6.1-sol` | `medium` | `subagent` |
| Interface-Agent | `gpt-6.1-sol` | `medium` | `subagent` |
| Data-Agent | `gpt-6.1-sol` | `medium` | `subagent` |
| Integrations-Agent | `gpt-6.1-sol` | `medium` | `subagent` |
| Security-Agent | `gpt-6.1-sol` | `high` | `subagent` |
| Debugger-Agent | `gpt-6.1-sol` | `high` | `subagent` |
| Testing-Agent | `gpt-6.1-sol` | `medium` | `subagent` |
| QA-Reviewer-Agent | `gpt-6.1-sol` | `high` | `subagent` |
| Operations-Agent | `gpt-6.1-sol` | `medium` | `subagent` |
| Documentation-Agent | `gpt-6-luna` | `medium` | `subagent` |

Models are declarative preferences. Check availability in the environment running the agent and report any difference from this matrix. Escalation to `gpt-6-astra` is reserved for the Orchestrator after repeated failures or unresolved high risk.

Matrix updated on 2026-10-05 using [official Codex subagent documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents): `gpt-6.1-sol` for substantive work and `gpt-6-luna` for bounded requirements and documentation tasks. Existing reasoning levels are preserved. The validator accepts GPT-6 family identifiers (`gpt-6.1-sol`, `gpt-6-sol`, `gpt-6-luna`, `gpt-6-astra`); the active catalogue uses GPT-6.1 Sol and GPT-6 Luna, with Astra reserved for escalation.

## Dispatch behavior

The Orchestrator classifies each request, maintains context and assigns each specialist an independent surface without overlapping edits. Small tasks stay with the primary agent. Requirements and Architecture are activated only when needed; sensitive changes go through Security first; QA closes substantive changes. Only the Orchestrator creates, continues or escalates agents.

Reports distinguish implemented, verified, pending and proposed work. A downloaded or configured tool is not runtime-available until checked. User-managed skills, configuration and inventories are preserved; conflicts are reported.

Before sensitive implementation, all roles apply [Security-Policy.md](Security-Policy.md): verify the current OWASP edition from its official source, document risks, controls and tests, and have QA check the evidence at closure. This is preserved when exporting the toolkit. The Strix OWASP testing skill requires an expressly authorized target and scope.

## Toolkit commands

Run from the project root containing `.codex/toolkit/`:

```text
python .codex/toolkit/manage.py bootstrap
python .codex/toolkit/manage.py list
python .codex/toolkit/manage.py update [--tool ID]
python .codex/toolkit/manage.py doctor
python .codex/toolkit/manage.py doctor --probe-mcp
python .codex/toolkit/manage.py sync-agents
python .codex/toolkit/manage.py export --project PATH
python .codex/toolkit/manage.py add --id ID --repo owner/repo --skill PATH
python .codex/toolkit/manage.py add --id ID --repo owner/repo --skill GLOB
python .codex/toolkit/manage.py add --id ID --mcp-url URL
python .codex/toolkit/manage.py add --id ID --mcp-package package --env ENV_NAME
```

Examples for copying to another system and extending the catalogue:

```powershell
python .codex/toolkit/manage.py export --project "C:/Repositories/another-system"
python .codex/toolkit/manage.py update --tool impeccable
python .codex/toolkit/manage.py add --id new-skill --repo organization/repository --skill skills/new-skill
python .codex/toolkit/manage.py add --id new-mcp --mcp-url https://example.org/mcp --env NEW_MCP_API_KEY
python .codex/toolkit/manage.py bootstrap
```

These are usage examples: replace example sources with real repositories and services. You can also edit `registry.json` directly; no installer changes are needed.

`bootstrap` downloads missing sources, prepares MCP configuration, and generates TOML and inventory; it does not install global processes, hooks or daemons. The first project task receives bootstrap instructions from `AGENTS.md`; there is no persistent automatic background execution. Installation does not run scans or upload code or data. `list`, `doctor` and `sync-agents` provide explicit inspection or synchronization. `export` installs the reusable toolkit in another project and appends the generic routing block without replacing its `AGENTS.md`. `add` registers a skill by path or glob, or an MCP server by URL or package; `--env` records the required credential name.

The registry is `.codex/toolkit/registry.json`, locks are in `.codex/toolkit/tools.lock.json`, the readable report is `.codex/toolkit/INVENTORY.md`, and the machine inventory is ignored `inventory.json`. Skills are installed under `.agents/skills`; downloaded sources under `.codex/toolkit/vendor` remain ignored. Unmanaged or modified skills and configuration are preserved and conflicts are reported.

npm MCP runtimes stay isolated in `.codex/toolkit/runtime/`. Dependencies are restored using portable locks in `.codex/toolkit/runtime-locks/`; installation scripts are disabled. An existing skill with different content is preserved as `preserved-unmanaged`: updating its source does not replace that customization. Download instructions run automatically when the agent starts work after the toolkit has been exported to the project.

## Selecting skills and MCPs

| Area | Tools according to scope |
| --- | --- |
| Requirements and architecture | Spec Kit, graphify, Context7 and ponytail |
| Implementation, data and integrations | Context7, graphify and ponytail; Security for sensitive boundaries |
| Interfaces | DESIGN.md, Impeccable, UI/UX Pro Max and Taste; select relevant guidance and respect the brief |
| Debugging and testing | graphify, Context7, existing tests and connected TestSprite for authorized flows |
| Quality and security | Thermo-Nuclear for strict review, Cyber Neo for read-only audits, ClawScan for skills and Strix for authorized pentests |
| Operations and documentation | Context7, graphify and project evidence; Lighthouse for web criteria and Boneyard for skeletons where appropriate |

All 15 requested sources are registered. Some repositories contain multiple skills, so the inventory may have more than 15 entries. DESIGN.md and Spec Kit use clearly identified local adapters; graphify receives its Codex document and complete references. Internal contributor skills from upstream repositories are not imported indiscriminately.

`doctor --probe-mcp` only initializes managed MCPs and lists their tools. It does not start tests, pentests or page audits. Its exit code may be 1 even when both MCPs respond if optional runtimes or CLI prerequisites are missing.

## Operational limitations

Downloading sources and skills for Strix, Specify, ClawScan or Lighthouse does not install their executables. Before use, check upstream instructions and platform prerequisites. Strix requires Docker and LLM provider configuration; Lighthouse needs a browser and running web interface. Strix variables are registered by name without fixing a provider or creating credentials.

The Markdown catalogue defines context and model preferences. Generated `.toml` files register native subagents; they do not automatically change the primary conversation model. Reload Codex or start a new turn when new skills/MCPs are not yet exposed. Plugin-injected MCPs may be available without appearing in local files; the inventory explains this distinction.

Configuration sources: [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents), [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli), [Context7](https://github.com/upstash/context7) and [TestSprite](https://docs.testsprite.com/mcp/getting-started/installation). The registry retains each upstream tool's link.

## Credentials and trust

Document variable names only, never values: `CONTEXT7_API_KEY` and `TESTSPRITE_API_KEY`. The TestSprite launcher maps `TESTSPRITE_API_KEY` to `API_KEY`. After editing variables or MCP configuration, reload the environment and review tool trust on the execution host. The presence of a variable, MCP entry or downloaded file does not prove that the service responds.

## Documentation validation

Check that each role frontmatter contains exactly `name`, `description`, `mode`, `model` and `reasoning_effort`; `description` is a one-line YAML string; the name matches the filename; and referenced paths exist where they form part of the destination project. Documentation review does not replace project tests or broad audits.
