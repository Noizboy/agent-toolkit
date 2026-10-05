"""Client adapter behavior using local fixtures; no client launches or downloads."""
import json
import os
from pathlib import Path
import sys
import tempfile
import tomllib
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from providers import configure_provider
from sources import save_json


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project with spaces"
        self.root.mkdir()
        self.write("AGENTS.md", "Existing project rules.\n")
        self.card("Orchestrator", "strong", "primary")
        self.card("Docs-Agent", "light")
        self.card("Architect-Agent", "escalation")
        self.write(".agents/skills/example/SKILL.md", "---\nname: example\ndescription: Example\n---\nBody\n")
        self.write(".agents/skills/example/references/guide.md", "Complete reference\n")
        self.write(".agents/skills/example/scripts/run.py", "print('fixture')\n")
        self.write(".agents/skills/example/assets/icon.bin", b"\0\1\2")
        self.write(".agent-toolkit/runtime/testsprite/0.0.46/server.js", "// fixture")
        save_json(self.root / ".agent-toolkit/registry.json", {"schema_version": 1, "tools": [
            {"id": "context7", "mcp": {"transport": "http", "url": "https://mcp.context7.com/mcp", "credential_env": "CONTEXT7_API_KEY"}},
            {"id": "testsprite", "mcp": {"transport": "stdio", "package": "@testsprite/testsprite-mcp", "version": "0.0.46", "credential_env": "TESTSPRITE_API_KEY", "server_env": "API_KEY"}},
        ]})
        save_json(self.root / ".agent-toolkit/tools.lock.json", {"tools": {"testsprite": {"npm": {
            "version": "0.0.46", "entrypoint": ".agent-toolkit/runtime/testsprite/0.0.46/server.js"}}}})

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, bytes):
            path.write_bytes(value)
        else:
            path.write_text(value, encoding="utf-8")
        return path

    def card(self, name, tier, mode="subagent"):
        self.write(f".agent-toolkit/agents/{name}.md", f'---\nname: {name}\ndescription: "Role fixture"\nmode: {mode}\nmodel_tier: {tier}\nreasoning_effort: high\n---\n\nEscalate to the selected provider\'s escalation model only after repeated failures.\n')

    def snapshot(self):
        return {file.relative_to(self.root).as_posix(): file.read_bytes()
                for file in self.root.rglob("*") if file.is_file()}

    def config(self, relative):
        return json.loads((self.root / relative).read_text(encoding="utf-8"))

    def test_claude_roles_and_complete_skill_payload(self):
        self.assertEqual(configure_provider(self.root, "claude", {}), [])
        for name, model in [("orchestrator", "sonnet"), ("docs-agent", "haiku"), ("architect-agent", "opus")]:
            text = (self.root / f".claude/agents/{name}.md").read_text()
            frontmatter = text.split("---", 2)[1]
            self.assertIn(f'name: "{name}"', frontmatter)
            self.assertIn(f'model: "{model}"', frontmatter)
            self.assertNotIn("permissionMode", text)
            self.assertNotIn("reasoning_effort", frontmatter)
            self.assertIn("Canonical role cards are provider-neutral", text)
            self.assertNotIn("provider override", text)
            self.assertNotIn("gpt-6", text)
            self.assertIn("Escalate to opus only after repeated failures.", text)
        for relative in ["SKILL.md", "references/guide.md", "scripts/run.py", "assets/icon.bin"]:
            self.assertEqual((self.root / ".agents/skills/example" / relative).read_bytes(),
                             (self.root / ".claude/skills/example" / relative).read_bytes())
        self.assertIn("@AGENTS.md", (self.root / "CLAUDE.md").read_text())
        self.assertIn("Selected client: Claude Code", (self.root / "AGENTS.md").read_text())
        self.assertIn("model_tier: strong", (self.root / ".agent-toolkit/agents/Orchestrator.md").read_text())
        self.assertFalse((self.root / ".codex").exists())
        self.assertFalse((self.root / ".opencode").exists())

    def test_opencode_models_modes_and_escalation_selection(self):
        settings = {"strong_model": "anthropic/claude-sonnet-4", "light_model": "anthropic/claude-haiku-4", "escalation_model": "anthropic/claude-opus-4"}
        self.assertEqual(configure_provider(self.root, "opencode", settings), [])
        for name, model, mode in [("orchestrator", settings["strong_model"], "primary"),
                                   ("docs-agent", settings["light_model"], "subagent"),
                                   ("architect-agent", settings["escalation_model"], "subagent")]:
            text = (self.root / f".opencode/agents/{name}.md").read_text()
            frontmatter = text.split("---", 2)[1]
            self.assertIn(f'model: "{model}"', frontmatter)
            self.assertIn(f'mode: "{mode}"', frontmatter)
            self.assertNotIn("reasoning_effort", frontmatter)
            self.assertNotIn("effort:", frontmatter)
            self.assertIn("Canonical role cards are provider-neutral", text)
            self.assertNotIn("provider override", text)
            self.assertIn("Escalate to anthropic/claude-opus-4 only after repeated failures", text)
        config = self.config("opencode.json")
        self.assertEqual(config["model"], settings["strong_model"])
        self.assertEqual(config["small_model"], settings["light_model"])
        self.assertEqual(config["default_agent"], "orchestrator")
        self.assertEqual(config["instructions"], ["AGENTS.md"])
        self.assertFalse((self.root / ".opencode/skills").exists())
        self.assertFalse((self.root / ".codex").exists())
        self.assertFalse((self.root / ".claude").exists())

    def test_codex_tiers_generate_only_selected_native_client(self):
        settings = {"strong_model": "gpt-6-sol", "light_model": "gpt-6-luna", "escalation_model": "gpt-6-astra"}
        self.assertEqual(configure_provider(self.root, "codex", settings), [])
        for name, model in [("Orchestrator", "gpt-6-sol"), ("Docs-Agent", "gpt-6-luna"), ("Architect-Agent", "gpt-6-astra")]:
            path = self.root / f".codex/agents/{name}.toml"
            config = tomllib.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(config["model"], model)
            self.assertIn(".agent-toolkit/agents/Agent-Contract.md", config["developer_instructions"])
            self.assertIn("gpt-6-astra", config["developer_instructions"])
        self.assertTrue((self.root / ".codex/config.toml").is_file())
        self.assertFalse((self.root / ".claude").exists())
        self.assertFalse((self.root / ".opencode").exists())
        self.assertFalse((self.root / ".mcp.json").exists())
        self.assertFalse((self.root / "opencode.json").exists())
        self.assertFalse((self.root / "CLAUDE.md").exists())
        self.assertFalse(list((self.root / ".agent-toolkit/agents").glob("*.toml")))

    def test_codex_dry_run_generates_no_native_directory(self):
        before = self.snapshot()
        self.assertEqual(configure_provider(self.root, "codex", {}, dry_run=True), [])
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / ".codex").exists())

    def test_codex_unmanaged_agent_collision_prevents_other_native_writes(self):
        self.write(".codex/agents/Docs-Agent.toml", 'name = "Custom Docs"\nmodel = "gpt-6-luna"\n')
        before = self.snapshot()
        errors = configure_provider(self.root, "codex", {})
        self.assertTrue(any("preserved" in error for error in errors))
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / ".codex/config.toml").exists())

    def test_codex_unmanaged_mcp_collision_prevents_agent_writes(self):
        self.write(".codex/config.toml", '[mcp_servers.context7]\nurl = "https://custom.example/mcp"\n')
        before = self.snapshot()
        self.assertTrue(configure_provider(self.root, "codex", {}))
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / ".codex/agents").exists())

    def test_codex_modified_owned_agent_prevents_all_updates(self):
        self.assertEqual(configure_provider(self.root, "codex", {}), [])
        path = self.root / ".codex/agents/Docs-Agent.toml"
        self.write(".codex/agents/Docs-Agent.toml", path.read_text().replace('name = "Docs-Agent"', 'name = "My Docs"'))
        self.card("New-Agent", "strong")
        before = self.snapshot()
        self.assertTrue(configure_provider(self.root, "codex", {}))
        self.assertEqual(before, self.snapshot())

    def test_credentials_are_placeholders_and_stdio_is_pinned(self):
        with patch.dict(os.environ, {"CONTEXT7_API_KEY": "never-copy-secret", "TESTSPRITE_API_KEY": "other-secret"}):
            for provider, relative, field in [("claude", ".mcp.json", "mcpServers"), ("opencode", "opencode.json", "mcp")]:
                self.assertEqual(configure_provider(self.root, provider, {}), [])
                mcp = self.config(relative)[field]
                placeholder = "${CONTEXT7_API_KEY}" if provider == "claude" else "{env:CONTEXT7_API_KEY}"
                self.assertEqual(mcp["context7"]["headers"]["CONTEXT7_API_KEY"], placeholder)
                environment = mcp["testsprite"]["env" if provider == "claude" else "environment"]
                self.assertEqual(environment, {"API_KEY": "${TESTSPRITE_API_KEY}" if provider == "claude" else "{env:TESTSPRITE_API_KEY}"})
                arguments = mcp["testsprite"]["args" if provider == "claude" else "command"]
                self.assertIn("0.0.46", arguments[-1])
                self.assertNotIn("npx", arguments)
                self.assertNotIn("never-copy-secret", (self.root / relative).read_text())
                self.assertNotIn("other-secret", (self.root / relative).read_text())

    def test_idempotency_for_all_providers(self):
        for provider in ("codex", "claude", "opencode"):
            self.assertEqual(configure_provider(self.root, provider, {}), [])
            before = self.snapshot()
            self.assertEqual(configure_provider(self.root, provider, {}), [])
            self.assertEqual(before, self.snapshot())
        self.assertIn("/provider-state.json", (self.root / ".agent-toolkit/.gitignore").read_text())

    def test_unrelated_client_configuration_and_defaults_are_preserved(self):
        self.write("CLAUDE.md", "My Claude instructions.\n")
        self.write(".claude/agents/custom.md", "Custom unrelated agent\n")
        self.write(".claude/skills/custom/SKILL.md", "Custom skill\n")
        save_json(self.root / ".mcp.json", {"customSetting": True, "mcpServers": {"custom": {"command": "custom"}}})
        save_json(self.root / "opencode.json", {"model": "custom/model", "small_model": "custom/small", "default_agent": "build",
                                                "instructions": ["docs/my-rules.md"], "mcp": {"custom": {"type": "local", "command": ["custom"]}}})
        self.assertEqual(configure_provider(self.root, "claude", {}), [])
        self.assertEqual(configure_provider(self.root, "opencode", {}), [])
        self.assertTrue((self.root / "CLAUDE.md").read_text().startswith("My Claude instructions."))
        self.assertEqual((self.root / ".claude/agents/custom.md").read_text(), "Custom unrelated agent\n")
        self.assertEqual((self.root / ".claude/skills/custom/SKILL.md").read_text(), "Custom skill\n")
        self.assertEqual(self.config(".mcp.json")["mcpServers"]["custom"], {"command": "custom"})
        config = self.config("opencode.json")
        self.assertEqual(config["model"], "custom/model")
        self.assertEqual(config["small_model"], "custom/small")
        self.assertEqual(config["default_agent"], "build")
        self.assertEqual(config["instructions"], ["docs/my-rules.md", "AGENTS.md"])

    def test_unmanaged_mcp_collision_causes_no_partial_writes(self):
        for provider, relative, container in [("claude", ".mcp.json", "mcpServers"), ("opencode", "opencode.json", "mcp")]:
            save_json(self.root / relative, {container: {"context7": {"url": "https://custom.example/mcp"}}})
            before = self.snapshot()
            errors = configure_provider(self.root, provider, {})
            self.assertTrue(any("conflict" in error for error in errors))
            self.assertEqual(before, self.snapshot())

    def test_modified_owned_file_prevents_all_updates(self):
        self.assertEqual(configure_provider(self.root, "claude", {}), [])
        self.write(".claude/agents/docs-agent.md", "My custom agent\n")
        self.card("New-Agent", "strong")
        before = self.snapshot()
        errors = configure_provider(self.root, "claude", {"strong_model": "opus"})
        self.assertTrue(any("docs-agent.md" in error for error in errors))
        self.assertEqual(before, self.snapshot())

    def test_modified_owned_skill_prevents_all_updates(self):
        self.assertEqual(configure_provider(self.root, "claude", {}), [])
        self.write(".claude/skills/example/references/guide.md", "My modified reference")
        before = self.snapshot()
        self.assertTrue(configure_provider(self.root, "claude", {}))
        self.assertEqual(before, self.snapshot())

    def test_unmanaged_skill_collision_prevents_all_writes(self):
        self.write(".claude/skills/example/SKILL.md", "Pre-existing customization")
        before = self.snapshot()
        self.assertTrue(configure_provider(self.root, "claude", {}))
        self.assertEqual(before, self.snapshot())

    def test_modified_owned_mcp_entry_prevents_all_updates(self):
        self.assertEqual(configure_provider(self.root, "opencode", {}), [])
        config = self.config("opencode.json")
        config["mcp"]["context7"]["headers"] = {"custom": "user-value"}
        save_json(self.root / "opencode.json", config)
        before = self.snapshot()
        self.assertTrue(configure_provider(self.root, "opencode", {}))
        self.assertEqual(before, self.snapshot())

    def test_modified_owned_routing_block_prevents_updates(self):
        self.assertEqual(configure_provider(self.root, "codex", {}), [])
        path = self.root / "AGENTS.md"
        path.write_text(path.read_text().replace("Selected client:", "User selected client:"), encoding="utf-8")
        before = self.snapshot()
        self.assertTrue(configure_provider(self.root, "claude", {}))
        self.assertEqual(before, self.snapshot())

    def test_unowned_native_agent_config_collision(self):
        save_json(self.root / "opencode.json", {"agent": {"orchestrator": {"model": "custom/model"}}})
        before = self.snapshot()
        self.assertTrue(configure_provider(self.root, "opencode", {}))
        self.assertEqual(before, self.snapshot())

    def test_duplicate_agent_identity_at_another_path_is_preserved(self):
        self.write(".claude/agents/review/custom-name.md", '---\nname: docs-agent\ndescription: Custom\n---\nCustom body\n')
        before = self.snapshot()
        self.assertTrue(configure_provider(self.root, "claude", {}))
        self.assertEqual(before, self.snapshot())

    def test_existing_opencode_jsonc_requires_review_without_writes(self):
        self.write("opencode.jsonc", '{// custom config\n"model": "custom/model"}\n')
        before = self.snapshot()
        self.assertTrue(configure_provider(self.root, "opencode", {}))
        self.assertEqual(before, self.snapshot())

    def test_clean_owned_skill_update_removes_stale_resources(self):
        self.assertEqual(configure_provider(self.root, "claude", {}), [])
        (self.root / ".agents/skills/example/references/guide.md").unlink()
        self.write(".agents/skills/example/references/new.md", "New resource")
        self.assertEqual(configure_provider(self.root, "claude", {}), [])
        self.assertFalse((self.root / ".claude/skills/example/references/guide.md").exists())
        self.assertEqual((self.root / ".claude/skills/example/references/new.md").read_text(), "New resource")

    def test_dry_run_has_no_writes(self):
        before = self.snapshot()
        self.assertEqual(configure_provider(self.root, "claude", {}, dry_run=True), [])
        self.assertEqual(before, self.snapshot())

    def test_invalid_provider_model_and_missing_runtime_have_no_writes(self):
        for provider, settings in [("missing", {}), ("claude", {"strong_model": "openai/gpt-6.1-sol"}),
                                    ("opencode", {"strong_model": "gpt-6.1-sol"})]:
            before = self.snapshot()
            self.assertTrue(configure_provider(self.root, provider, settings))
            self.assertEqual(before, self.snapshot())
        (self.root / ".agent-toolkit/runtime/testsprite/0.0.46/server.js").unlink()
        before = self.snapshot()
        self.assertTrue(configure_provider(self.root, "claude", {}))
        self.assertEqual(before, self.snapshot())

    def test_missing_neutral_cards_prevents_every_client_configuration(self):
        for card in (self.root / ".agent-toolkit/agents").glob("*.md"):
            card.unlink()
        for provider in ("codex", "claude", "opencode"):
            before = self.snapshot()
            self.assertTrue(configure_provider(self.root, provider, {}))
            self.assertEqual(before, self.snapshot())

    def test_link_destination_rejected_before_writes(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        try:
            (self.root / ".claude").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("Creating links requires Windows developer mode or privileges")
        before = self.snapshot()
        self.assertTrue(configure_provider(self.root, "claude", {}))
        self.assertEqual(before, self.snapshot())
        self.assertEqual(list(outside.iterdir()), [])

    def test_windows_junction_attribute_rejected_before_writes(self):
        target = self.root / ".claude"
        target.mkdir()
        original = Path.lstat

        def junction_metadata(path, *args, **kwargs):
            result = original(path, *args, **kwargs)
            if path == target:
                return SimpleNamespace(st_mode=result.st_mode, st_file_attributes=0x400)
            return result

        before = self.snapshot()
        with patch.object(Path, "lstat", junction_metadata):
            errors = configure_provider(self.root, "claude", {})
        self.assertTrue(any("Links are not allowed" in error for error in errors))
        self.assertEqual(before, self.snapshot())

    def test_unmanaged_agent_file_is_preserved_before_any_writes(self):
        self.write(".claude/agents/docs-agent.md", "Custom owned by user")
        before = self.snapshot()
        self.assertTrue(configure_provider(self.root, "claude", {}))
        self.assertEqual(before, self.snapshot())

    def test_adding_unrelated_mcp_does_not_conflict_with_managed_entries(self):
        self.assertEqual(configure_provider(self.root, "opencode", {}), [])
        config = self.config("opencode.json")
        config["mcp"]["extra"] = {"type": "local", "command": ["custom"]}
        save_json(self.root / "opencode.json", config)
        self.assertEqual(configure_provider(self.root, "opencode", {}), [])
        self.assertEqual(self.config("opencode.json")["mcp"]["extra"], config["mcp"]["extra"])

    def test_malformed_state_and_unpinned_entrypoint_have_no_writes(self):
        save_json(self.root / ".agent-toolkit/provider-state.json", {"schema_version": 1, "files": []})
        before = self.snapshot()
        self.assertTrue(configure_provider(self.root, "claude", {}))
        self.assertEqual(before, self.snapshot())
        (self.root / ".agent-toolkit/provider-state.json").unlink()
        self.write("custom.js", "// outside runtime")
        save_json(self.root / ".agent-toolkit/tools.lock.json", {"tools": {"testsprite": {"npm": {
            "version": "0.0.46", "entrypoint": "custom.js"}}}})
        before = self.snapshot()
        self.assertTrue(configure_provider(self.root, "claude", {}))
        self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
