# Registry maintenance

Usage and model guidance is in [../agents/README.md](../agents/README.md). The entry point is `manage.py`, with no external Python dependencies; it requires Python 3.11+ and Git. Package-based MCPs require Node.js and npm. `bootstrap` prepares project-local tools; `update` is the only command that advances upstream versions.

## Installer and concise template

- [INSTALLER.md](INSTALLER.md): Windows setup executable with project details and ChatGPT/Codex, Claude Code or OpenCode selection.
- [manage.py](manage.py): project skill/MCP installer and manager.
- [registry.json](registry.json): editable catalogue of tools to prepare.
- [AGENTS.template.md](AGENTS.template.md): concise instructions for role coordination, tool use and OWASP review.

To prepare this project and inspect its tools:

```text
python .codex/toolkit/manage.py bootstrap
python .codex/toolkit/manage.py list
```

To reuse the toolkit, run this from the source project:

```text
python .codex/toolkit/manage.py export --project "C:/Repositories/another-system"
```

Export copies the installer, registry, locks, agents and template; appends the concise block to the destination `AGENTS.md`, preserves its context and prepares tools. If that file does not exist, export creates it. Then add that project's purpose, stack, commands and specific rules. Copying the template alone does not install the toolkit. Conflicts are reported for a deliberate merge.

## Adding tools

`registry.json` has `schema_version: 1` and a `tools` list. Each entry requires a stable `id`, a descriptive `type` and, optionally, `docs`, `notes` or `enabled: false`. Identifiers support lowercase letters, digits and hyphens. Automatic source downloads are restricted to public HTTPS GitHub repositories.

For skills, declare `repo: "owner/repo"`, `ref` (branch, tag or HEAD) and `skills` (relative directories or globs containing SKILL.md). The entire directory is copied, including scripts, references and resources. Paths that escape the project, links or destinations outside the project are rejected.

For distributions with a different structure, `payloads` supports a skill name and a `files` mapping from source paths to relative destination paths. See graphify in the registry. An `adapter` refers to a directory under `adapters/`; its SKILL.md must explain that it is a local integration rather than an upstream skill.

For HTTP MCPs, declare `mcp.transport: "http"`, an HTTPS `url` and, where applicable, `credential_env`; Codex uses it as a Bearer token. For npm stdio MCPs, declare `mcp.transport: "stdio"`, `package`, an optional exact `version`, `credential_env` and the provider's expected `server_env`. If the package exposes multiple executables, specify `bin_name`. `add --help` covers common cases without editing code.

The `command`, `requirements` and `credential_envs` fields report CLIs and prerequisites. These are presence checks; bootstrap does not execute these commands or install application dependencies.

## Restoration and preservation

`tools.lock.json` records Git commits, managed skill hashes, npm artifacts and generated configuration blocks. Downloaded source trees are not executed during preparation. npm dependencies are pinned under `runtime-locks/` and installed with lifecycle scripts disabled. Keep both kinds of lock in Git.

An unmanaged skill with different content is preserved. A modified managed skill produces a conflict and is not forcibly replaced. Customized `.toml` files and modified MCP blocks are also preserved. To update a customization, review the downloaded new source and merge manually. Do not delete locks to resolve conflicts: this would remove the information protecting customizations.

Export checks collisions before copying toolkit files, preserves the destination AGENTS.md and shares pins. It does not copy credentials, source-machine inventories, caches or installed dependencies. If the destination already contains a different toolkit, it reports the conflict for a deliberate merge.

## Verification

```text
python -m unittest discover -s .codex/toolkit/tests -v
python .codex/toolkit/manage.py bootstrap
python .codex/toolkit/manage.py list
python .codex/toolkit/manage.py doctor --probe-mcp
```

Tests use local fixtures for restoration, updates, export, preservation, locks, paths, links and credentials. External probes perform only `initialize` and `tools/list`; they do not call business tools. The inventory distinguishes downloaded sources, installed skills, MCP configuration, runtime and the last connection check. It does not certify complete security or tool loading within the current session.
