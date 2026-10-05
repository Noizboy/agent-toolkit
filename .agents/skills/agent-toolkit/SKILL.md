---
name: agent-toolkit
description: Bootstrap, inventory, update or export the repository's generic agent toolkit when beginning substantive work in a project that contains .agent-toolkit/registry.json, or when the user manages its agents, skills or MCP tools.
---

# Project agent toolkit

Read .agent-toolkit/agents/Orchestrator.md and Agent-Contract.md. At the first substantive project task in a session, run `python .agent-toolkit/manage.py bootstrap` once, then `python .agent-toolkit/manage.py list` and show a compact status. Bootstrap is provider-neutral: native client files are generated only for the provider selected by the installer and recorded in `.agent-toolkit/project.json`. The registry defines authorized project-local skill downloads and MCP setup; ordinary bootstrap restores pinned versions and preserves unmanaged/customized installations.

Do not recursively invoke this skill from its own bootstrap, a specialist or a read-only audit. A skill discovered after bootstrap may require a new turn/reload; read its SKILL.md directly if allowed rather than claiming it is already runtime-loaded.

For updates explicitly requested by the user, run `python .agent-toolkit/manage.py update`, optionally `--tool ID`. For model-selection requests, read `.agent-toolkit/prompts/select-agent-models.md`. Explicitly requested model changes update the provider mapping in project.json and, when needed, a role's model tier; run `sync-agents` to generate selected-client files. To add a skill or MCP use `add` or edit registry.json, then bootstrap. Run `--help` for exact command options. Export to another project only when the user requests it, with `export --project PATH`.

Read INVENTORY.md for project/user skills and configured MCPs. Configuration, source download, installed runtime and verified protocol are distinct. `doctor --probe-mcp` performs bounded initialize/tools-list checks, without running tests or scans. Credentials come from named environment variables; never display, commit or copy their values. Do not execute remote setup scripts, install application dependencies, upload project code or start a security assessment during bootstrap. Report missing prerequisites/conflicts and continue independent authorized work.
