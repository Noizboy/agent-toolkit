# Generic agent toolkit

These role cards describe a reusable team for local projects. Each card has frontmatter for native configuration, but frontmatter alone does not switch the current session's primary model. Native configuration is generated separately for the provider selected by the installer; report unavailable models rather than inventing a replacement.

All agents read [Agent-Contract.md](Agent-Contract.md) before acting. Cards retain generic names and responsibilities so they can be installed in another project without assuming a domain, provider or framework. Maintain toolkit instructions, documentation and examples in English.

## Model tiers

| Role | Model tier | Reasoning | Mode |
| --- | --- | --- | --- |
| Orchestrator | `strong` | `high` | `primary` |
| Requirements-Agent | `light` | `medium` | `subagent` |
| Architecture-Agent | `strong` | `high` | `subagent` |
| Implementation-Agent | `strong` | `medium` | `subagent` |
| Interface-Agent | `strong` | `medium` | `subagent` |
| Data-Agent | `strong` | `medium` | `subagent` |
| Integrations-Agent | `strong` | `medium` | `subagent` |
| Security-Agent | `strong` | `high` | `subagent` |
| Debugger-Agent | `strong` | `high` | `subagent` |
| Testing-Agent | `strong` | `medium` | `subagent` |
| QA-Reviewer-Agent | `strong` | `high` | `subagent` |
| Operations-Agent | `strong` | `medium` | `subagent` |
| Documentation-Agent | `light` | `medium` | `subagent` |

Model tiers are declarative preferences. The installer records the selected provider and its strong, light and escalation model identifiers in `.agent-toolkit/project.json`; `sync-agents` maps each tier to that provider's native configuration. Role cards never carry provider-specific model IDs, provider prefixes or a global model default. The Orchestrator may use the selected provider's escalation model only after repeated failures or unresolved high-risk design.

## Dispatch behavior

The Orchestrator classifies each request, maintains context and assigns each specialist an independent surface without overlapping edits. Small tasks stay with the primary agent. Requirements and Architecture are activated only when needed; sensitive changes go through Security first; QA closes substantive changes. Only the Orchestrator creates, continues or escalates agents.

Reports distinguish implemented, verified, pending and proposed work. A downloaded or configured tool is not runtime-available until checked. User-managed skills, configuration and inventories are preserved; conflicts are reported.

Before sensitive implementation, all roles apply [Security-Policy.md](Security-Policy.md): verify the current OWASP edition from its official source, document risks, controls and tests, and have QA check the evidence at closure. The Strix OWASP testing skill requires an expressly authorized target and scope.

## Canonical and native layout

The canonical source is `.agent-toolkit/`. Native files are generated only for the provider selected by the installer:

| Selected client | Native files generated | Skills location |
| --- | --- | --- |
| ChatGPT / Codex | `.codex/agents/`, `.codex/config.toml` | Shared `.agents/skills/` when applicable |
| Anthropic / Claude Code | `.claude/agents/`, `.claude/skills/`, `CLAUDE.md`, `.mcp.json` | `.claude/skills/` |
| OpenCode | `.opencode/agents/`, `opencode.json` | Shared `.agents/skills/` |

An uninstalled checkout has no provider-native layout by default. Do not infer the selected provider from a role card or create another client's native files manually during bootstrap.

## Toolkit commands

Run from the project root containing `.agent-toolkit/`:

```text
python .agent-toolkit/manage.py bootstrap
python .agent-toolkit/manage.py list
python .agent-toolkit/manage.py update [--tool ID]
python .agent-toolkit/manage.py doctor
python .agent-toolkit/manage.py doctor --probe-mcp
python .agent-toolkit/manage.py sync-agents
python .agent-toolkit/manage.py export --project PATH
python .agent-toolkit/manage.py add --id ID --repo owner/repo --skill PATH
python .agent-toolkit/manage.py add --id ID --repo owner/repo --skill GLOB
python .agent-toolkit/manage.py add --id ID --mcp-url URL
python .agent-toolkit/manage.py add --id ID --mcp-package package --env ENV_NAME
```

Examples for copying to another system and extending the catalogue:

```powershell
python .agent-toolkit/manage.py export --project "C:/Repositories/another-system"
python .agent-toolkit/manage.py update --tool impeccable
python .agent-toolkit/manage.py add --id new-skill --repo organization/repository --skill skills/new-skill
python .agent-toolkit/manage.py add --id new-mcp --mcp-url https://example.org/mcp --env NEW_MCP_API_KEY
python .agent-toolkit/manage.py bootstrap
```

These are usage examples: replace example sources with real repositories and services. You can also edit `registry.json` directly; no installer changes are needed.

`bootstrap` downloads missing sources, prepares MCP configuration, and generates inventory plus provider-native files when a provider has been selected; it does not install global processes, hooks or daemons. The first project task receives bootstrap instructions from `AGENTS.md`; there is no persistent automatic background execution. Installation does not run scans or upload code or data. `list`, `doctor` and `sync-agents` provide explicit inspection or synchronization. `export` installs the reusable toolkit in another project and appends the generic routing block without replacing its `AGENTS.md`. `add` registers a skill by path or glob, or an MCP server by URL or package; `--env` records the required credential name.

The registry is `.agent-toolkit/registry.json`, locks are in `.agent-toolkit/tools.lock.json`, the readable report is `.agent-toolkit/INVENTORY.md`, and the machine inventory is ignored `inventory.json`. Skills are installed under `.agents/skills`; downloaded sources under `.agent-toolkit/vendor` remain ignored. Unmanaged or modified skills and configuration are preserved and conflicts are reported.

npm MCP runtimes stay isolated in `.agent-toolkit/runtime/`. Dependencies are restored using portable locks in `.agent-toolkit/runtime-locks/`; installation scripts are disabled. An existing skill with different content is preserved as `preserved-unmanaged`: updating its source does not replace that customization. Download instructions run automatically when the agent starts work after the toolkit has been exported to the project.

## Selecting skills and MCPs

| Area | Tools according to scope |
| --- | --- |
| Requirements and architecture | Spec Kit, graphify, Context7 and ponytail |
| Implementation, data and integrations | Context7, graphify and ponytail; Security for sensitive boundaries |
| Interfaces | DESIGN.md, Impeccable, UI/UX Pro Max and Taste; select relevant guidance and respect the brief |
| Debugging and testing | graphify, Context7, existing tests and connected TestSprite for authorized flows |
| Quality and security | Thermo-Nuclear for strict review, Cyber Neo for read-only audits, ClawScan for skills and Strix for authorized pentests |
| Operations and documentation | Context7, graphify and project evidence; Lighthouse for web criteria and Boneyard for skeletons where appropriate |

All 15 requested sources are registered. Some repositories contain multiple skills, so the inventory may have more than 15 entries. DESIGN.md and Spec Kit use clearly identified local adapters; graphify receives its selected client's document and complete references. Internal contributor skills from upstream repositories are not imported indiscriminately.

## Operational limitations

Downloading sources and skills for Strix, Specify, ClawScan or Lighthouse does not install their executables. Before use, check upstream instructions and platform prerequisites. Strix requires Docker and an LLM provider configuration; Lighthouse needs a browser and running web interface. Strix variables are registered by name without fixing a provider or creating credentials.

The Markdown catalogue defines context and model tiers. Generated native files register subagents for the selected client; they do not automatically change the primary conversation model. Reload or restart that client when new skills or MCPs are not yet exposed. Plugin-injected MCPs may be available without appearing in local files; the inventory explains this distinction.

## Credentials and trust

Document variable names only, never values: `CONTEXT7_API_KEY` and `TESTSPRITE_API_KEY`. The TestSprite launcher maps `TESTSPRITE_API_KEY` to `API_KEY`. After editing variables or MCP configuration, reload the environment and review tool trust on the execution host. The presence of a variable, MCP entry or downloaded file does not prove that the service responds.

## Migration note

Release `v0.2.0` uses the canonical `.agent-toolkit/` layout and selected-provider native output. An installation created with the older `v0.1.0` layout is not automatically deleted or overwritten by source updates. Review collisions and perform a deliberate migration while preserving custom files.

## Documentation validation

Check that each role frontmatter contains exactly `name`, `description`, `mode`, `model_tier` and `reasoning_effort`; `description` is a one-line YAML string; the name matches the filename; and referenced paths exist where they form part of the destination project. Documentation review does not replace project tests or broad audits.
