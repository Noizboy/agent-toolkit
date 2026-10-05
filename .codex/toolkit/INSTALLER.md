# Windows project installer

Double-click **AgentToolkitSetup.exe**. Enter the project name, description, target folder and environment:

- **ChatGPT / Codex**: native Codex TOML agents and project MCP configuration; GPT-6.1 Sol for substantive roles, GPT-6 Luna for requirements/documentation, GPT-6 Astra for justified escalation.
- **Anthropic / Claude Code**: native Claude agents, CLAUDE.md routing, skills and project MCP configuration; Sonnet/Haiku aliases with Opus escalation.
- **OpenCode**: native OpenCode agents, skills and MCP configuration; editable provider/model IDs. OpenCode is a client; authenticate the underlying model provider separately.

The repository defaults to `Noizboy/agent-toolkit`, version `v0.1.0`. You can enter a GitHub repository and an explicit tag, branch or commit. The installer records the resolved commit in the project's installation report. Private repository downloads use GitHub CLI authentication: install `gh`, run `gh auth login`, then reopen the installer. Credentials are never requested in the form or written into project files.

## Requirements and results

Git, Python 3.11+ and Node.js/npm must be available on PATH. The executable bundles its own UI Python runtime, but installed maintenance scripts and the Codex MCP launcher use the project's available Python. Setup reports prerequisites instead of silently installing software globally.

Downloads can take several minutes. Existing AGENTS.md context, unrelated native configuration and custom skills are preserved. Conflicting customized files are reported rather than overwritten; unresolved issues produce an incomplete result. Read `.codex/toolkit/installation.json` and `INVENTORY.md` after setup. Project details and provider choices are in `.codex/toolkit/project.json`.

Restart the selected coding client, sign in to the selected model provider and approve the project's MCP servers. Source preparation and configuration do not prove client/model availability. Optional Strix, Specify, ClawScan, graphify and Lighthouse CLIs have separate prerequisites; the installer does not start tests, scans or pentests.

## Maintenance

```text
python .codex/toolkit/manage.py list
python .codex/toolkit/manage.py update
python .codex/toolkit/manage.py sync-agents
```

Bootstrap, updates and agent synchronization also refresh the selected provider adapter, preserving locally modified generated files. Add future tools to `registry.json`; adapter formats remain provider-specific.

`manage.py update` updates registered upstream skills/MCP packages. Re-running the wizard does not overwrite a different existing toolkit source version: merge an installer/toolkit revision update deliberately when a source-file conflict is reported.

## Build the executable

Run from the dedicated repository root on Windows:

```powershell
python -m venv .codex/toolkit/.build-venv
.codex/toolkit/.build-venv/Scripts/python.exe -m pip install -r .codex/toolkit/build-requirements.txt
.codex/toolkit/.build-venv/Scripts/python.exe .codex/toolkit/build_installer.py
```

Output: `.codex/toolkit/installer-dist/AgentToolkitSetup.exe`. Build artifacts and the virtual environment are ignored. Publish the executable and its SHA-256 checksum as release assets. The executable is unsigned; it does not request administrator privileges.

For scripted setup, use the same executable's `--install --project PATH --name NAME --description TEXT --provider codex|claude|opencode` flags, optionally `--repository owner/repo --ref TAG`. Exit status is nonzero for unresolved issues. `--self-test RESULT.json` verifies the packaged setup form without installation.

Configuration references: [Codex](https://learn.chatgpt.com/docs/agent-configuration/subagents), [Claude agents](https://code.claude.com/docs/en/sub-agents), [Claude MCP](https://code.claude.com/docs/en/mcp), [OpenCode agents](https://opencode.ai/docs/agents/), [OpenCode MCP](https://opencode.ai/docs/mcp-servers/), [PyInstaller](https://pyinstaller.org/en/stable/usage.html).
