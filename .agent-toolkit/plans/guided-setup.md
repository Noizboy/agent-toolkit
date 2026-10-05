# Guided optional tool setup

## Outcome

After a successful base installation, offer a guided window that can install selected optional runtimes, configure Strix authentication and masked MCP credentials, and check managed MCP protocol communication. Reopen it from an installed project without downloading or exporting the toolkit again.

## Acceptance criteria

- All tool downloads are explicit selections using fixed, reviewed recipes. Existing global commands and project customizations are preserved.
- Optional failures do not undo or misreport successful agent/skill installation. Each selected component has an independent result.
- Strix offers Later, ChatGPT browser login and API authentication. ChatGPT mode does not require an API key. Login does not run a model or pentest.
- Docker installation remains official manual guidance; check CLI presence and daemon readiness independently.
- Credentials are masked and process-only by default. Optional Windows user environment persistence requires explicit selection and a plaintext disclosure; no secrets enter project files or reports.
- Protocol verification only initializes managed Context7/TestSprite and lists tools; custom MCPs are not executed. Client loading remains a separate step.
- Tests cover unselected actions, malformed preferences, credential redaction, existing user-value conflicts, integrity failures, unsafe paths, runtime failures and base-install status.

## Implementation and validation

Security pre-review: [guided-setup-security.md](guided-setup-security.md), verified against current official OWASP sources on 2026-10-05. Runtime engine, guided UI and manager integration have separate ownership. QA reviews the completed diff and runs meaningful negative tests before packaging and publication. No scans, model calls, repository uploads or Docker/service changes are part of setup.
