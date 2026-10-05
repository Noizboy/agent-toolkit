# Security policy: OWASP before implementation

This policy applies to all roles when a change affects authentication, sessions, permissions, isolation between users, sensitive data, secrets, cryptography, untrusted inputs, files, external calls, dependencies, MCPs/skills, deployment configuration or error handling that can alter a control. The Orchestrator classifies the task and performs or assigns the Security review before designing or writing the change. A small review may remain with the primary agent, with the same evidence requirements.

## Required current-source consultation

1. Before implementing each security task, consult the [official OWASP Top 10 portal](https://owasp.org/Top10/) and check the latest published edition. Do not assume that the year stored in a skill or this document remains current. Record the edition, consultation date and links to relevant categories. Reuse this consultation within the same task only while its scope remains unchanged.
2. For APIs, also check the [OWASP API Security Top 10](https://owasp.org/API-Security/). For implementable, verifiable controls, consult the relevant [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/) recommendations and applicable [ASVS](https://owasp.org/www-project-application-security-verification-standard/) requirements, recording the version when citing an identifier. For other surfaces, supplement these with the applicable OWASP standard; do not claim full mobile, hardware or AI coverage from reviewing only the web Top 10.
3. Use Context7 for documentation of the exact library or framework version; the official OWASP publication takes precedence when determining the current standard. If Context7 is unavailable, consult the provider's official documentation directly and record the limitation.
4. If the official source cannot be verified, record the failure and label the last known reference as unverified. Continue diagnosis and independent work; do not start dependent implementation or claim current recommendations until that verification is resolved. Document an explicit requirement for another edition and compare it with the current edition without mixing identifiers from different years.

Initial references checked on 2026-10-05: [OWASP Top 10:2025](https://top10.owasp.org/2025/), API Security Top 10:2023 and ASVS 5.0.0. This is dated evidence, not a version pin for future tasks.

## Evidence before the change

Prepare a short note in the task plan or report; create a separate document only when scope justifies it:

- Affected surfaces, assets, actors and trust boundaries.
- Consulted editions, date and official links.
- For each applicable category: identifier including year, abuse scenario, recommended control and planned verification. Review all ten categories to determine applicability; briefly justify exclusions or group exclusions sharing the same reason. Never mark an unreviewed category as passed.
- Pending risks, assumptions, dependencies and the Security decision that allows implementation within the authorized scope.

The Top 10 guides risk assessment; it is not sufficient on its own as a control specification or certification. Concrete controls must be supported by the consulted recommendations and the system's behavior.

## Implementation and closure

- The implementer receives this evidence before editing and applies the agreed controls. If another sensitive surface is discovered, return the decision to the Orchestrator before expanding the change.
- Testing and QA check relevant negative scenarios in addition to valid behavior: cross-user access, malicious inputs, invalid credentials, resource exhaustion or dependency failures, according to the change. Record the test, result and actual limitations for each control.
- QA does not close a security change without evidence of prior consultation and verified controls; document deferred recommendations and residual risks. Do not claim complete OWASP compliance because a scanner found no issues.
- `cyber-neo` may support read-only review. The Strix `owasp-top-10-testing` skill performs active testing: activate it only when the user authorizes that target and scope. Consulting OWASP never automatically triggers exploitation, pentesting, code uploads or tool installation.
