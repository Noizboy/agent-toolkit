# Toolkit maintenance

Usage and model-tier guidance is in [agents/README.md](agents/README.md). The entry point is `manage.py`, with no external Python dependencies; it requires Python 3.11+ and Git. Package-based MCPs require Node.js and npm. `bootstrap` prepares project-local tools; `update` is the only command that advances upstream versions.

## Canonical source and selected client output

The canonical provider-neutral source is `.agent-toolkit/`. Role cards use `model_tier: strong|light` and do not contain provider-specific model IDs. The installer records the selected provider and its model mapping in `.agent-toolkit/project.json`; native settings are generated only for that provider.

| Selected client | Generated native output | Skills location |
| --- | --- | --- |
| ChatGPT / Codex | `.codex/agents/`, `.codex/config.toml` | `.agents/skills/` when shared skills are used |
| Anthropic / Claude Code | `.claude/agents/`, `.claude/skills/`, `CLAUDE.md`, `.mcp.json` | `.claude/skills/` |
| OpenCode | `.opencode/agents/`, `opencode.json` | shared `.agents/skills/` |

An uninstalled checkout does not create provider-native directories by default. Existing native files or customized shared content are preserved and conflicts are reported for deliberate migration.

## Installer and concise template

- [INSTALLER.md](INSTALLER.md): Windows setup, provider output, migration and executable build instructions.
- [manage.py](manage.py): project skill/MCP installer and manager.
- [registry.json](registry.json): editable catalogue of tools to prepare.
- [AGENTS.template.md](AGENTS.template.md): concise provider-neutral instructions for role coordination, tool use and OWASP review.

To prepare this project and inspect its tools:

```text
python .agent-toolkit/manage.py bootstrap
python .agent-toolkit/manage.py list
```

To reuse the toolkit, run this from the source project:

```text
python .agent-toolkit/manage.py export --project "C:/Repositories/another-system"
```

Export copies the canonical toolkit, registry, locks, agents and template; appends the concise block to the destination `AGENTS.md`, preserves its context and prepares tools. It does not choose a native client until the destination installer records one. If the destination already contains a different toolkit source version, it reports the conflict for a deliberate merge. Copying the template alone does not install the toolkit.

## Adding tools

`registry.json` has `schema_version: 1` and a `tools` list. Each entry requires a stable `id`, a descriptive `type` and, optionally, `docs`, `notes` or `enabled: false`. Identifiers support lowercase letters, digits and hyphens. Automatic source downloads are restricted to public HTTPS GitHub repositories.

For skills, declare `repo: "owner/repo"`, `ref` (branch, tag or HEAD) and `skills` (relative directories or globs containing `SKILL.md`). The entire directory is copied, including scripts, references and resources. Paths that escape the project, links or destinations outside the project are rejected.

For distributions with a different structure, `payloads` supports a skill name and a `files` mapping from source paths to relative destination paths. See graphify in the registry. An `adapter` refers to a directory under `adapters/`; its `SKILL.md` must explain that it is a local integration rather than an upstream skill.

For HTTP MCPs, declare `mcp.transport: "http"`, an HTTPS `url` and, where applicable, `credential_env`. The selected client adapter maps that declaration to its native configuration. For npm stdio MCPs, declare `mcp.transport: "stdio"`, `package`, an optional exact `version`, `credential_env` and the selected client's expected environment field. If the package exposes multiple executables, specify `bin_name`. `add --help` covers common cases without editing code.

The `command`, `requirements` and `credential_envs` fields report CLIs and prerequisites. These are presence checks; bootstrap does not execute these commands, install application dependencies, run scans or upload code or data.

## Restoration and preservation

`tools.lock.json` records Git commits, managed skill hashes, npm artifacts and generated configuration blocks. Downloaded source trees are not executed during preparation. npm dependencies are pinned under `runtime-locks/` and installed with lifecycle scripts disabled. Keep both kinds of lock in Git.

An unmanaged skill with different content is preserved. A modified managed skill produces a conflict and is not forcibly replaced. Customized native configuration and modified MCP blocks are also preserved. To update a customization, review the downloaded new source and merge manually. Do not delete locks to resolve conflicts: this would remove the information protecting customizations.

Export checks collisions before copying toolkit files, preserves the destination `AGENTS.md` and shares pins. It does not copy credentials, source-machine inventories, caches or installed dependencies. If the destination already contains a different toolkit, it reports the conflict for a deliberate merge. A project from the old `v0.1.0` layout requires that same deliberate migration; source updates do not automatically delete or overwrite its native directories.

## Verification

```text
python -m unittest discover -s .agent-toolkit/tests -v
python .agent-toolkit/manage.py bootstrap
python .agent-toolkit/manage.py list
python .agent-toolkit/manage.py doctor --probe-mcp
```

Tests use local fixtures for restoration, updates, export, preservation, locks, paths, links and credentials. External probes perform only `initialize` and `tools/list`; they do not call business tools. The inventory distinguishes downloaded sources, installed skills, native configuration, runtime and the last connection check. It does not certify complete security or tool loading within the current session.
