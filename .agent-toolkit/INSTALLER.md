# Windows project installer

Double-click **AgentToolkitSetup.exe** in the repository root, or run `python installer.py` from a downloaded checkout. The executable is also available in GitHub releases. Enter only the project name, target folder and client/provider environment:

- **ChatGPT / Codex**: generates `.codex/agents/` and `.codex/config.toml` from the canonical cards and selected model settings.
- **Anthropic / Claude Code**: generates `.claude/agents/`, `.claude/skills/`, `CLAUDE.md` and `.mcp.json`.
- **OpenCode**: generates `.opencode/agents/` and `opencode.json`; it uses shared project skills from `.agents/skills/`.

The canonical role cards remain under `.agent-toolkit/agents/`, use `model_tier: strong|light`, and contain no provider-specific model IDs. The installer records the selected provider and its strong, light and escalation model settings in `.agent-toolkit/project.json`. `sync-agents` maps those tiers to native files for that provider.

No client is preselected in the form; scripted setup requires `--provider`. After selection, the initial model mappings are:

| Selected client | Strong | Light | Escalation |
| --- | --- | --- | --- |
| ChatGPT / Codex | `gpt-6.1-sol` | `gpt-6-luna` | `gpt-6-astra` |
| Claude Code | `sonnet` | `haiku` | `opus` |
| OpenCode | Editable provider/model IDs; initially `openai/gpt-6.1-sol` | Initially `openai/gpt-6-luna` | Initially `openai/gpt-6-astra` |

OpenCode is a client: select IDs actually exposed by the authenticated underlying provider. These mappings are configuration, not evidence that a provider currently exposes a particular model.

Every installation automatically resolves the latest published stable release of the public `Noizboy/agent-toolkit` repository through GitHub's latest-release API. There are no repository, version or description inputs, and GitHub sign-in is not required. Setup records the selected release and resolved commit in project metadata and the installation report. Discovery failures stop installation; setup does not fall back to an older release or a branch. Optional guided setup requests masked keys separately and never writes credentials into project files. Existing recorded descriptions are retained when reinstalling; add new project context directly to `AGENTS.md`.

## Requirements and results

Git, Python 3.11+ and Node.js/npm must be available on PATH. The executable bundles its own UI Python runtime, while installed maintenance scripts and MCP launchers use the project's available runtimes. Setup reports prerequisites instead of silently installing software globally.

Downloads can take several minutes. Existing `AGENTS.md` context, unrelated native configuration and custom skills are preserved. Conflicting customized files are reported rather than overwritten; unresolved issues produce an incomplete result. Read `.agent-toolkit/installation.json`, `INVENTORY.md` and `.agent-toolkit/project.json` after setup.

An uninstalled checkout contains the canonical `.agent-toolkit/` and shared `.agents/skills/` directories. Provider-native `.codex/`, `.claude/` and `.opencode/` directories are generated only for the provider selected by the installer. Restart the selected client, sign in to the selected model provider and approve the project's MCP servers. Source preparation and configuration do not prove client/model availability. Optional Strix, Specify, ClawScan, graphify and Lighthouse CLIs have separate prerequisites; the installer does not start tests, scans or pentests.

## Updating an existing project

The current source release is `v0.4.0`. Each installer run downloads the latest stable release automatically. Projects installed from older toolkit revisions are not automatically deleted or overwritten. Review reported source/routing collisions, preserve custom files and merge deliberately. The `v0.1.0` layout additionally requires a deliberate migration to the neutral shared directory. Do not treat a clean source download as permission to remove an old native layout.

## Guided optional setup

After successful base setup, **Guide optional tool setup after installation** opens a separate window. Reopen it using **Configure existing tools**, `python .agent-toolkit/manage.py setup`, or `AgentToolkitSetup.exe --configure-tools --project PATH`. Reopening does not download/export the toolkit or overwrite custom files.

1. **Tools:** select project-local Strix, Spec Kit/Specify, ClawScan, Lighthouse or Graphify runtimes. Fixed publisher recipes verify archive hashes, Python wheel hashes or npm integrity; package build/lifecycle scripts are disabled. Unsupported platforms/artifacts receive manual guidance. Optional runtime upgrades are deliberate; `update` updates skills/MCP packages, not these runtimes.
2. **Strix access:** choose Later, ChatGPT browser sign-in or an API provider/model ID. Save the choice, then explicitly start sign-in if selected. Strix owns its session; toolkit reads no token files. `session-detected` does not prove working inference. API mode additionally uses `LLM_API_KEY`.
3. **MCP access and checks:** enter masked keys, apply them and verify managed Context7/TestSprite communication. Only initialize/tools-list requests run; changed/custom endpoints and extra servers are skipped. Process-only keys work during setup; future clients need their environment configured separately. Optional Windows user environment persistence is plaintext, off by default, preserves differing values and needs a client restart.

Docker is not installed or reconfigured automatically. Its explicit check distinguishes missing CLI from unavailable daemon and links official installation guidance. Check current Windows compatibility before installing Docker Desktop. CLI version/help verification also requires an explicit button. Setup runs no tools against your application; Chrome availability and live model access need separate checks before audits/pentests.

Runtimes and non-secret preferences live in ignored `.agent-toolkit/runtime/optional/`. The manifest records versions and integrity hashes. Global CLIs remain detected but unverified. Use `python .agent-toolkit/manage.py run-tool TOOL -- --help` to invoke a managed runtime explicitly without changing PATH. Optional failures do not undo successful agent/skill installation.

Version `v0.2.1` includes [a model-selection prompt](prompts/select-agent-models.md) and a conditional `AGENTS.md` instruction to read it for model requests. It guides the AI's research and supported configuration changes; it does not add automatic discovery, live evaluations or active-session model switching to the executable.

## Maintenance

```text
python .agent-toolkit/manage.py list
python .agent-toolkit/manage.py update
python .agent-toolkit/manage.py sync-agents
```

Bootstrap, updates and agent synchronization refresh the selected provider adapter while preserving locally modified generated files. Add future tools to `registry.json`; adapter formats remain provider-specific. Reload or restart the selected client when new skills or MCPs are not yet exposed.

## Build the executable

Run from the dedicated repository root on Windows:

```powershell
python -m venv .agent-toolkit/.build-venv
.agent-toolkit/.build-venv/Scripts/python.exe -m pip install -r .agent-toolkit/build-requirements.txt
.agent-toolkit/.build-venv/Scripts/python.exe .agent-toolkit/build_installer.py
```

Output: `AgentToolkitSetup.exe` and `SHA256SUMS.txt` in the repository root. Intermediate build files and the virtual environment are ignored; the root executable/checksum are published with the source and as release assets. The executable is unsigned; it does not request administrator privileges.

For scripted setup, use the executable or Python source with `--install --project PATH --name NAME --provider codex|claude|opencode`. It also downloads the latest stable release; source overrides and description arguments are not supported. Exit status is nonzero for unresolved issues. `--self-test RESULT.json` verifies the packaged setup form without installation.

Configuration references: [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents), [Claude agents](https://code.claude.com/docs/en/sub-agents), [Claude MCP](https://code.claude.com/docs/en/mcp), [OpenCode agents](https://opencode.ai/docs/agents/), [OpenCode MCP](https://opencode.ai/docs/mcp-servers/) and [PyInstaller](https://pyinstaller.org/en/stable/usage.html).

## Existing toolkit conflicts

If setup stops because an existing toolkit file or marked routing block differs, the dialog names the affected relative path. Back up that file, preserve project-specific instructions and merge only the toolkit content before retrying. A legacy `.codex/toolkit` layout needs this deliberate migration to `.agent-toolkit`; removing the old folder alone does not update its startup skill, `AGENTS.md` routing or ignore block. Customized files are never automatically replaced. Unexpected export errors remain summarized by error type.
