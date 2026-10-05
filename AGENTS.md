<!-- BEGIN generic-agent-toolkit -->
## Agents and tools

- Act as Orchestrator. Before substantive work, read `.codex/agents/Orchestrator.md` and `Agent-Contract.md` in that directory.
- At the start of the session, run `python .codex/toolkit/manage.py bootstrap` once to prepare declared skills/MCPs and restore pinned versions. Preserve customizations and report conflicts or missing prerequisites.
- Show the summary with `python .codex/toolkit/manage.py list`. The full inventory is `.codex/toolkit/INVENTORY.md`; never expose credentials.
- Select the role from `.codex/agents/README.md` and read its card and relevant skills. Only Orchestrator delegates; tasks must be bounded, independent and have disjoint file ownership. Small tasks may remain with the primary agent.
- Use Context7 for current documentation; graphify for an existing graph and update it after code changes; ponytail for simplification; design skills for UI; Testing and QA for validation. Activate other tools only when scope justifies them.
- Before security design or implementation, apply `.codex/agents/Security-Policy.md`: verify current OWASP guidance in the official source and record date, edition, risks, controls and tests. Security reviews first; QA verifies before closure. Installation or guidance lookup does not authorize pentests, exploitation or code uploads.
- Use the models declared in `.codex/agents/*.toml`. This configuration does not switch the primary chat model. Distinguish downloaded, configured, available and verified tools; report actual limitations.
- To update tools, use `python .codex/toolkit/manage.py update`; to add tools, use `add` or edit `registry.json` and run `bootstrap`. To change models, edit the cards and run `sync-agents`. Consult `.codex/toolkit/README.md`.
- Keep this project's context, commands and rules in this AGENTS.md. Write maintained toolkit instructions and documentation in English. Follow user instructions and preserve other contributors' changes. Close with results, validation and pending work.
<!-- END generic-agent-toolkit -->
