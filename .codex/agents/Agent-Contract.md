# Shared agent contract

All role cards in this directory must be read together with this contract. It defines the minimum exchange between the Orchestrator and specialists so that the cards remain reusable in any project.

## Precedence

Apply instructions in this order: the user request, applicable `AGENTS.md`, this contract, the role card and skill documentation. Higher-priority instructions prevail in a conflict. If an instruction does not apply to the current project, explain the limitation and continue with the closest safe alternative.

## Agent input

The Orchestrator provides a bounded task with an objective, scope, permitted files or surfaces, restrictions, available evidence and completion criteria. Confirm this boundary before reading or editing. If a missing decision materially changes the result, return a concrete question instead of inventing an answer.

## Responsibilities and boundaries

- Work only within the assigned scope and preserve other contributors' or unrelated changes.
- Do not delegate from a specialist. Only the Orchestrator may create, continue or escalate agents.
- Do not send external messages, publish, deploy, delete data or change infrastructure without explicit authorization and clear scope.
- Do not treat a downloaded skill, generated configuration or listed tool as evidence of runtime availability.
- If a tool is disconnected, report the limitation and perform the closest actual local check.
- Keep documents, names and examples independent of any domain, provider or framework unless the project requires otherwise.
- Write maintained toolkit instructions, role cards, templates, documentation and examples in English. Preserve exact tool identifiers and command syntax.

## Result format

Each agent returns a brief, verifiable report:

1. **Result:** completed work or diagnosis.
2. **Files and surfaces:** paths changed, created or reviewed.
3. **Validation:** commands, queries, tests or inspections performed and their results.
4. **Risks and pending work:** limitations, open decisions and missing evidence.
5. **Escalation:** only when needed, the exact reason and the decision required from the Orchestrator.

Distinguish implemented, verified, unavailable and proposed work. Do not conceal repeated failures behind a success claim.

## Tools and triggers

- Before designing or implementing sensitive changes, all roles apply [Security-Policy.md](Security-Policy.md): consult current official OWASP guidance, document risks and controls before implementation, and verify them at closure. Do not infer the edition from a skill's memory.
- Use Context7 MCP when a task needs current documentation for a library, API or version.
- Use `graphify query`, `path` or `explain` for code questions when `graphify-out/` exists; after modifying code, use `graphify update .` (AST only).
- Use `testsprite` only for authorized test flows when the MCP is connected; otherwise run actual local tests.
- Use `spec-kit` for requirements or plans when scope justifies it.
- Use `cyber-neo` as a read-only security audit; respect the upstream report location and do not run scans or uploads during installation.
- Use `thermo-nuclear-code-quality-review` for requested maintainability reviews; use `ponytail` when the decision concerns reducing code or design to the minimum solution.
- For UI, select only the relevant local skill among `impeccable`, `ui-ux-pro-max`, `taste-skill` and `design-md`; give precedence to the existing brand and brief.
- Use `strix` skills only against expressly authorized pentest targets; never run them automatically during bootstrap.
- Use `clawscan-cli` for skill supply-chain review when requested.
- Use Lighthouse only when web performance or accessibility is part of the completion criteria.
- Use `boneyard` only when a loading skeleton helps a specific interaction; do not introduce production dependencies indiscriminately.

## High-impact escalation

The Orchestrator may escalate to `gpt-6-astra` only after repeated failures or when a high-risk design remains unresolved. Document the attempts and reason. Do not use provider-prefixed IDs or invent replacements for unavailable models.

## Closure

QA-Reviewer-Agent closes substantive changes using proportional evidence. The Orchestrator determines the final status and communicates remaining limitations to the user.
