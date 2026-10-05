# Installer security decisions — 2026-10-05

Official sources checked before implementation: [OWASP Top 10:2025](https://top10.owasp.org/2025/) and [OWASP software supply-chain guidance](https://cheatsheetseries.owasp.org/cheatsheets/Software_Supply_Chain_Security_Cheat_Sheet.html). This scoped review concerns local setup and repository/configuration handling.

| Category | Applicable risk and control | Verification |
|---|---|---|
| A01:2025 | File writes outside the chosen project or through links. Validate managed relative paths, reject linked destination ancestors and preserve existing custom files. | Traversal, junction, path ownership and conflict tests. |
| A02:2025 | Wrong-client configuration and unsafe automatic permissions. Use native provider schemas, credential variable references and inherited client permissions. | Provider fixtures; configuration parsing; UI provider selection tests. |
| A03:2025 | Source or dependency substitution. Restrict repository input to HTTPS GitHub, resolve and record a commit, restore Git/npm locks, reject repository links, disable hooks and lifecycle scripts. The executable runs its own reviewed manager modules rather than downloaded Python during setup. | Git command fixtures, pinned restoration tests, release SHA-256 and actual download smoke test. |
| A04:2025 | Credential disclosure. Use existing GitHub CLI keychain and named MCP environment variables; do not collect keys or display subprocess diagnostics. | Credential-placeholder and sanitized inventory/environment tests. |
| A05:2025 | Command or project-description injection. Pass subprocess argument arrays, validate repository/ref/model inputs and encode descriptions as JSON data. | Malicious-input fixtures and command-shape assertions. |
| A06:2025 | Confusing configured tools with live integrations. Keep bootstrap separate from active assessment and report optional runtimes, credentials and reload requirements. | Installation report tests and documented acceptance criteria. |
| A08:2025 | Modified installer/toolkit content. Preserve owned-file hashes; distribute a dedicated repository/release and checksum. | Modified-file conflict tests and release checksum verification. |
| A09:2025 | Missing setup failure evidence or sensitive logs. Persist bounded status/revision/issues without keys. | Installation report and error-path fixtures. |
| A10:2025 | Partial setup treated as success. Use bounded download timeouts, preflight known conflicts, mark unresolved bootstrap/provider issues incomplete and return nonzero. | Failure fixtures and real isolated installation. |

A07 is outside this installer change: the coding clients and services perform authentication; no login/session service is implemented here. A checksum detects accidental artifact changes but is not a signed provenance claim. Client/model availability and complete third-party source security are not certified by these checks. A user-authorized alternate repository is trusted as the toolkit source; no downloaded skill or remote setup script is automatically executed.
