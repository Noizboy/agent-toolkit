# Agent Toolkit

A reusable agent team, project-local skills/MCP manager and English Windows setup wizard.

Download **AgentToolkitSetup.exe** from the [latest release](https://github.com/Noizboy/agent-toolkit/releases/latest), then double-click it. Enter your project name, description, folder and provider/environment: ChatGPT/Codex, Anthropic/Claude Code or OpenCode.

Git, Python 3.11+ and Node.js/npm are required. For this private repository, authenticate with GitHub CLI using `gh auth login` before downloading/installing. The installer downloads a selected repository revision and restores pinned tool versions; credentials remain in your environment/keychain.

- [Setup and build instructions](.codex/toolkit/INSTALLER.md)
- [Agent roles and models](.codex/agents/README.md)
- [Reusable AGENTS.md template](.codex/toolkit/AGENTS.template.md)
- [Editable tool registry](.codex/toolkit/registry.json)
- [Security policy](.codex/agents/Security-Policy.md)

To install from a checkout:

```text
python .codex/toolkit/installer.py
```

After installation, run these inside the target project:

```text
python .codex/toolkit/manage.py list
python .codex/toolkit/manage.py update
```

There are 13 roles and 15 registered tool sources. Codex uses GPT-6.1 Sol/GPT-6 Luna with GPT-6 Astra escalation; Claude uses Sonnet/Haiku aliases with Opus escalation; OpenCode accepts configurable provider/model IDs. Client authentication and model availability are separate from configuration.

Existing project instructions and custom skills/configuration are preserved. Unresolved conflicts are reported. Optional audit CLIs have separate runtime prerequisites; setup does not execute audits, tests or pentests. Before security-sensitive implementation, agents must consult current official OWASP guidance and record controls and verification evidence.

All maintained toolkit instructions are in English. Third-party skills are fetched from their upstream repositories and retain upstream licenses and authorship. The executable is unsigned and does not request administrator privileges.
