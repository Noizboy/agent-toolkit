<!-- BEGIN generic-agent-toolkit -->
## Agents and tools

- Act as Orchestrator. Before substantive work, read `.agent-toolkit/agents/Orchestrator.md` and `Agent-Contract.md` in that directory.
- At the first substantive project task, run `python .agent-toolkit/manage.py bootstrap` once to prepare declared skills/MCPs and restore pinned versions. Bootstrap is provider-neutral; native client files are generated only after the installer records the selected provider in `.agent-toolkit/project.json`.
- Show the summary with `python .agent-toolkit/manage.py list`. The full inventory is `.agent-toolkit/INVENTORY.md`; never expose credentials.
- Select the role from `.agent-toolkit/agents/README.md` and read its card plus relevant skills. Only Orchestrator delegates; tasks must be bounded, independent and have disjoint file ownership. Small tasks may remain with the primary agent.
- Use Context7 for current documentation; graphify for an existing graph and update it after code changes; ponytail for simplification; design skills for UI; Testing and QA for validation. Activate other tools only when scope justifies them.
- Before security design or implementation, apply `.agent-toolkit/agents/Security-Policy.md`: verify current OWASP guidance in the official source and record date, edition, risks, controls and tests. Security reviews come first; QA verifies before closure. Installation or guidance lookup does not authorize pentests, exploitation or code uploads.
- Use model tiers declared in `.agent-toolkit/agents/*.md`. Native settings are generated per the selected provider and its `.agent-toolkit/project.json` model mapping; this does not switch the primary chat model. Distinguish downloaded, configured, available and verified tools, and report actual limitations.
- To update tools, use `python .agent-toolkit/manage.py update`; to add tools, use `add` or edit `registry.json` and run `bootstrap`. To refresh provider-native agents, use `python .agent-toolkit/manage.py sync-agents`. Consult `.agent-toolkit/README.md`.
- Keep this project's context, commands and rules in this `AGENTS.md`. Write maintained toolkit instructions and documentation in English. Follow user instructions and preserve other contributors' changes. Close with results, validation and pending work.
<!-- END generic-agent-toolkit -->
