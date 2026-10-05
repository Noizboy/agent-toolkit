"""Behavioral tests with local fixtures; no downloads, scanners or external MCP calls."""
import argparse
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from configuration import configure_mcp, install_mcp_runtime, sync_agents
from manage import Toolkit, append_once
from sources import checkout, install_skill, mcp_environment, safe_path, save_json, tree_hash, validate_tool


class ToolkitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.home = self.root / ".agent-toolkit"
        self.home.mkdir(parents=True)
        (self.root / ".agent-toolkit/agents").mkdir()
        self.source = Path(self.temp.name) / "source"
        self.skill = self.source / "skills/example"
        self.skill.mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("---\nname: example\ndescription: Example fixture\n---\nVersion one\n", encoding="utf-8")
        (self.skill / "references").mkdir()
        (self.skill / "references/guide.md").write_text("Complete resource", encoding="utf-8")
        self.tool = {"id": "example", "type": "skill", "repo": "fixture/repo", "ref": "main", "skills": ["skills/example"]}
        self.registry([self.tool])
        self.output = io.StringIO()
        self.output_context = redirect_stdout(self.output)
        self.output_context.__enter__()
        self.addCleanup(self.output_context.__exit__, None, None, None)

    def registry(self, tools):
        save_json(self.home / "registry.json", {"schema_version": 1, "tools": tools})

    def fake_checkout(self, tool, vendor, previous, update):
        target = vendor / tool["id"] / ("b" * 40 if update else previous.get("commit", "a" * 40))
        target.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copytree(self.source / "skills", target / "skills", dirs_exist_ok=True)
        return target, target.name

    def bootstrap(self, update=False):
        toolkit = Toolkit(self.root)
        with patch("manage.checkout", side_effect=self.fake_checkout), patch("manage.mcp_configs", return_value=[]):
            errors = toolkit.bootstrap(update=update)
        return toolkit, errors

    def test_bootstrap_is_idempotent_and_copies_resources(self):
        first, errors = self.bootstrap()
        self.assertEqual(errors, [])
        snapshot = (self.home / "tools.lock.json").read_bytes()
        second, errors = self.bootstrap()
        self.assertEqual(errors, [])
        self.assertEqual(snapshot, (self.home / "tools.lock.json").read_bytes())
        self.assertEqual((self.root / ".agents/skills/example/references/guide.md").read_text(), "Complete resource")
        self.assertEqual(first.state, second.state)

    def test_update_advances_pin_and_clean_managed_skill(self):
        self.bootstrap()
        (self.skill / "SKILL.md").write_text("Version two", encoding="utf-8")
        updated, errors = self.bootstrap(update=True)
        self.assertEqual(errors, [])
        self.assertEqual(updated.state["tools"]["example"]["commit"], "b" * 40)
        self.assertEqual((self.root / ".agents/skills/example/SKILL.md").read_text(), "Version two")

    def test_modified_skill_is_preserved_with_conflict(self):
        self.bootstrap()
        dest = self.root / ".agents/skills/example/SKILL.md"
        dest.write_text("Local customization", encoding="utf-8")
        (self.skill / "SKILL.md").write_text("Upstream update", encoding="utf-8")
        updated, errors = self.bootstrap(update=True)
        self.assertTrue(errors)
        self.assertEqual(dest.read_text(), "Local customization")
        self.assertEqual(updated.state["tools"]["example"]["skills"]["example"]["status"], "conflict-local-changes")

    def test_unmanaged_skill_is_preserved(self):
        dest = self.root / ".agents/skills/example"
        dest.mkdir(parents=True)
        (dest / "SKILL.md").write_text("Existing custom skill", encoding="utf-8")
        toolkit, errors = self.bootstrap()
        self.assertEqual(errors, [])
        self.assertEqual((dest / "SKILL.md").read_text(), "Existing custom skill")
        self.assertEqual(toolkit.state["tools"]["example"]["skills"]["example"]["status"], "preserved-unmanaged")
        self.assertNotIn("/example/", (self.root / ".agents/skills/.gitignore").read_text())

    def test_missing_skill_is_restored_at_locked_pin(self):
        import shutil
        original, _ = self.bootstrap()
        shutil.rmtree(self.root / ".agents/skills/example")
        restored, errors = self.bootstrap()
        self.assertEqual(errors, [])
        self.assertEqual(restored.state["tools"]["example"]["commit"], original.state["tools"]["example"]["commit"])
        self.assertTrue((self.root / ".agents/skills/example/SKILL.md").is_file())

    def test_traversal_and_cross_platform_absolute_paths_rejected(self):
        for path in ["../outside", "/outside", "C:/outside", "..\\outside", "ok/../../outside"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                safe_path(self.root, path)

    def test_invalid_registry_entries_rejected(self):
        for item in [{"id": "../bad"}, {"id": "tool", "repo": "https://evil.test/repo"},
                     {"id": "tool", "skills": ["../../escape"]},
                     {"id": "tool", "mcp": {"transport": "http", "url": "http://insecure.test"}},
                     {"id": "tool", "mcp": {"package": "pkg;evil"}}]:
            with self.subTest(item=item), self.assertRaises(ValueError):
                validate_tool(item)

    def test_symlink_destination_and_resource_rejected(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        link = self.root / "linked"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("Host lacks symlink creation privileges")
        with self.assertRaises(ValueError):
            safe_path(self.root, "linked/file")
        resource = self.skill / "linked.md"
        resource.symlink_to(outside / "data.md")
        with self.assertRaises(ValueError):
            tree_hash(self.skill)

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_windows_junction_destination_rejected(self):
        outside = Path(self.temp.name) / "junction-target"
        outside.mkdir()
        junction = self.root / "junction"
        # A fixture wholly inside the test's temporary directory; no shell deletion/move.
        command = f"New-Item -ItemType Junction -Path '{junction}' -Target '{outside}' | Out-Null"
        result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True)
        self.assertEqual(result.returncode, 0)
        try:
            with self.assertRaises(ValueError):
                safe_path(self.root, "junction/file")
            (outside / "SKILL.md").write_text("Not an installed skill")
            self.assertNotIn("junction", [s["name"] for s in Toolkit.skill_inventory(self.root, "project")])
        finally:
            os.rmdir(junction)

    def test_preserve_existing_mcp_and_unrelated_config(self):
        file = self.root / ".codex/config.toml"
        file.parent.mkdir(parents=True, exist_ok=True)
        original = 'model = "keep-model"\n[mcp_servers.context7]\nurl = "https://custom.test/mcp"\n'
        file.write_text(original)
        tool = {"id": "context7", "mcp": {"transport": "http", "url": "https://mcp.context7.com/mcp"}}
        configure_mcp(self.root, [tool], {})
        self.assertEqual(file.read_text(), original)

    def test_customized_managed_mcp_block_is_preserved(self):
        state = {}
        tool = {"id": "context7", "mcp": {"transport": "http", "url": "https://mcp.context7.com/mcp"}}
        configure_mcp(self.root, [tool], state)
        file = self.root / ".codex/config.toml"
        custom = file.read_text().replace("enabled = true", "enabled = false")
        file.write_text(custom)
        configure_mcp(self.root, [tool], state)
        self.assertEqual(file.read_text(), custom)

    def test_inventory_never_contains_credential_values(self):
        self.registry([{"id": "context7", "type": "mcp", "mcp": {"transport": "http", "url": "https://mcp.context7.com/mcp", "credential_env": "CONTEXT7_API_KEY"}}])
        with patch.dict(os.environ, {"CONTEXT7_API_KEY": "sentinel-do-not-print-this"}), patch("manage.mcp_configs", return_value=[]):
            report = Toolkit(self.root).inventory()
        self.assertTrue(report["tools"][0]["credentials"]["CONTEXT7_API_KEY"])
        self.assertNotIn("sentinel-do-not-print-this", json.dumps(report))
        self.assertNotIn("sentinel-do-not-print-this", (self.home / "INVENTORY.md").read_text())

    def test_mcp_environment_limits_credentials_to_declared_server(self):
        with patch.dict(os.environ, {"TESTSPRITE_API_KEY": "server-fixture", "DB_PASSWORD": "unrelated-fixture",
                                     "UNRELATED_CLOUD_SECRET": "another-fixture", "PATH": "fixture-path"}, clear=True):
            env = mcp_environment({"credential_env": "TESTSPRITE_API_KEY", "server_env": "API_KEY"})
        self.assertEqual(env, {"PATH": "fixture-path", "API_KEY": "server-fixture"})

    def test_stdio_probe_does_not_pass_unrelated_secrets(self):
        from probe import probe_stdio
        entry = self.root / "server.js"
        entry.write_text("fixture")
        class Child:
            def __init__(self):
                self.stdin = io.StringIO()
                self.stdout = io.StringIO('{"id":1,"result":{"protocolVersion":"2025-03-26"}}\n{"id":2,"result":{"tools":[]}}\n')
            def terminate(self): pass
            def wait(self, **kwargs): return 0
        tool = {"mcp": {"credential_env": "TESTSPRITE_API_KEY", "server_env": "API_KEY"}}
        with patch.dict(os.environ, {"TESTSPRITE_API_KEY": "server-fixture", "DB_PASSWORD": "unrelated-fixture"}), \
             patch("probe.shutil.which", return_value="node"), patch("probe.subprocess.Popen", return_value=Child()) as process:
            result = probe_stdio(self.root, tool, {"npm": {"entrypoint": "server.js"}})
        self.assertEqual(result["status"], "verified")
        self.assertNotIn("DB_PASSWORD", process.call_args.kwargs["env"])
        self.assertNotIn("unrelated-fixture", process.call_args.kwargs["env"].values())

    def test_native_agent_config_matches_card_and_preserves_customizations(self):
        card = self.root / ".agent-toolkit/agents/Example.md"
        card.write_text('---\nname: Example\ndescription: "Example agent"\nmodel_tier: strong\nreasoning_effort: high\n---\nGeneric instructions\n')
        state = {}
        sync_agents(self.root, state)
        config = self.root / ".codex/agents/Example.toml"
        parsed = tomllib.loads(config.read_text())
        self.assertEqual(parsed["model"], "gpt-6.1-sol")
        self.assertIn("Generic instructions", parsed["developer_instructions"])
        config.write_text(config.read_text() + "# customized\n")
        before = config.read_text()
        card.write_text(card.read_text().replace("Generic instructions", "Updated card"))
        sync_agents(self.root, state)
        self.assertEqual(config.read_text(), before)

    def test_native_agent_model_catalogue_accepts_gpt6_and_rejects_legacy_or_unknown_ids(self):
        card = self.root / ".agent-toolkit/agents/Example.md"
        state = {}
        card.write_text('---\nname: Example\ndescription: "Example agent"\nmodel_tier: strong\nreasoning_effort: high\n---\nGeneric instructions\n')
        config = self.root / ".codex/agents/Example.toml"
        for model in ["gpt-6.1-sol", "gpt-6-sol", "gpt-6-luna", "gpt-6-astra"]:
            with self.subTest(model=model):
                sync_agents(self.root, state, {"strong_model": model})
                self.assertEqual(tomllib.loads(config.read_text())["model"], model)
        before = config.read_bytes()
        for model in ["gpt-5.6-sol", "gpt-5.6-luna", "gpt-5.6-terra", "gpt-6.1", "openai/gpt-6.1-sol"]:
            with self.subTest(model=model):
                with self.assertRaisesRegex(ValueError, "approved ChatGPT catalogue"):
                    sync_agents(self.root, state, {"strong_model": model})
                self.assertEqual(config.read_bytes(), before)

    def test_neutral_bootstrap_does_not_select_a_client(self):
        toolkit, errors = self.bootstrap()
        self.assertEqual(errors, [])
        self.assertEqual(toolkit.inventory()["provider"], "not-selected")
        for client in [".codex", ".claude", ".opencode"]:
            self.assertFalse((self.root / client).exists())

    def test_native_mcp_inventory_uses_selected_client_and_hides_values(self):
        from configuration import mcp_configs
        for provider, relative, config in [
            ("claude", ".mcp.json", {"mcpServers": {"context7": {"url": "https://mcp.context7.com/mcp", "headers": {"CONTEXT7_API_KEY": "${CONTEXT7_API_KEY}"}, "custom": "private-fixture"}}}),
            ("opencode", "opencode.json", {"mcp": {"context7": {"url": "https://mcp.context7.com/mcp", "headers": {"CONTEXT7_API_KEY": "{env:CONTEXT7_API_KEY}"}, "custom": "private-fixture"}}}),
        ]:
            with self.subTest(provider=provider):
                save_json(self.home / "project.json", {"provider": provider})
                save_json(self.root / relative, config)
                with patch.dict(os.environ, {"CONTEXT7_API_KEY": "secret-fixture"}):
                    result = mcp_configs(self.root)
                self.assertEqual(result[0]["credential_presence"], {"CONTEXT7_API_KEY": True})
                self.assertNotIn("secret-fixture", json.dumps(result))
                self.assertNotIn("private-fixture", json.dumps(result))
                self.assertFalse((self.root / ".codex").exists())

    def test_checkout_uses_lock_without_resolving_new_ref(self):
        source = self.home / "vendor/example" / ("a" * 40)
        (source / ".git").mkdir(parents=True)
        prior = {"source": "fixture/repo@main", "commit": "a" * 40}
        with patch("sources.git", side_effect=["a" * 40, ""]) as command:
            result, pin = checkout(self.tool, self.home / "vendor", prior, False)
        self.assertEqual(result, source)
        self.assertEqual(pin, prior["commit"])
        self.assertFalse(any("ls-remote" in call.args for call in command.call_args_list))

    def test_update_resolves_new_upstream_ref(self):
        source = self.home / "vendor/example" / ("b" * 40)
        (source / ".git").mkdir(parents=True)
        prior = {"source": "fixture/repo@main", "commit": "a" * 40}
        with patch("sources.git", side_effect=["b" * 40 + "\trefs/heads/main", "b" * 40, ""]) as command:
            _, pin = checkout(self.tool, self.home / "vendor", prior, True)
        self.assertEqual(pin, "b" * 40)
        self.assertIn("ls-remote", command.call_args_list[0].args)

    def test_annotated_tag_locks_peeled_commit(self):
        source = self.home / "vendor/example" / ("b" * 40)
        (source / ".git").mkdir(parents=True)
        tool = {**self.tool, "ref": "v1.0.0"}
        remote = "a" * 40 + "\trefs/tags/v1.0.0\n" + "b" * 40 + "\trefs/tags/v1.0.0^{}"
        with patch("sources.git", side_effect=[remote, "b" * 40, ""]):
            _, pin = checkout(tool, self.home / "vendor", {}, False)
        self.assertEqual(pin, "b" * 40)

    def test_explicit_commit_does_not_require_branch_resolution(self):
        source = self.home / "vendor/example" / ("a" * 40)
        (source / ".git").mkdir(parents=True)
        tool = {**self.tool, "ref": "a" * 40}
        with patch("sources.git", side_effect=["a" * 40, ""]) as command:
            _, pin = checkout(tool, self.home / "vendor", {}, False)
        self.assertEqual(pin, "a" * 40)
        self.assertFalse(any("ls-remote" in call.args for call in command.call_args_list))

    def test_npm_install_disables_scripts_and_isolates_runtime(self):
        tool = {"id": "testsprite", "mcp": {"transport": "stdio", "package": "@scope/server"}}
        pinned = {"package": "@scope/server", "version": "1.2.3", "integrity": "sha512-fixture"}
        runtime = self.home / "runtime/testsprite/1.2.3"
        def install(*args, **kwargs):
            package = runtime / "node_modules/@scope/server"
            package.mkdir(parents=True)
            save_json(package / "package.json", {"version": "1.2.3", "bin": {"server": "main.js"}})
            (package / "main.js").write_text("fixture")
            save_json(runtime / "package-lock.json", {"packages": {"node_modules/@scope/server": {"integrity": "sha512-fixture"}}})
            self.assertIn("--ignore-scripts", args[0])
            self.assertIn("--workspaces=false", args[0])
            self.assertEqual(kwargs["cwd"], runtime)
            return subprocess.CompletedProcess(args[0], 0)
        with patch("configuration.npm_command", return_value=["node", "npm-cli.js"]), patch("configuration.subprocess.run", side_effect=install):
            result = install_mcp_runtime(tool, self.root, pinned)
        self.assertEqual(result["runtime"], "installed")
        self.assertTrue((self.root / result["entrypoint"]).is_file())
        self.assertFalse((self.root / "package.json").exists())

    def test_add_extends_registry_without_code_changes(self):
        args = argparse.Namespace(id="new-docs", repo=None, skill=None, mcp_url="https://docs.test/mcp", mcp_package=None,
                                  env="DOCS_API_KEY", docs=None, ref="HEAD", version=None, server_env=None)
        Toolkit(self.root).add(args)
        registered = Toolkit(self.root).tools[-1]
        self.assertEqual(registered["mcp"]["credential_env"], "DOCS_API_KEY")

    def test_routing_block_appends_without_replacing_project_context(self):
        file = self.root / "AGENTS.md"
        file.write_text("Existing project rules\n")
        block = "<!-- BEGIN generic-agent-toolkit -->\nGeneric rules\n<!-- END generic-agent-toolkit -->"
        append_once(self.root, "AGENTS.md", block)
        first = file.read_text()
        append_once(self.root, "AGENTS.md", block)
        self.assertEqual(file.read_text(), first)
        self.assertTrue(first.startswith("Existing project rules"))

    def test_export_preserves_context_and_copies_portable_lock(self):
        toolkit, _ = self.bootstrap()
        (self.home / "AGENTS.template.md").write_text("Generic routing block\n")
        (self.home / "gitignore.template").write_text(".agent-toolkit/vendor/\n")
        startup = self.root / ".agents/skills/agent-toolkit"
        startup.mkdir()
        (startup / "SKILL.md").write_text("Startup fixture")
        destination = Path(self.temp.name) / "other-project"
        destination.mkdir()
        (destination / "AGENTS.md").write_text("Other system rules\n")
        with patch.object(Toolkit, "bootstrap", return_value=[]) as bootstrap:
            errors = toolkit.export(destination)
        self.assertEqual(errors, [])
        self.assertTrue(bootstrap.called)
        self.assertTrue((destination / "AGENTS.md").read_text().startswith("Other system rules"))
        lock = json.loads((destination / ".agent-toolkit/tools.lock.json").read_text())
        self.assertEqual(lock["tools"]["example"]["commit"], "a" * 40)
        self.assertNotIn("source_path", lock["tools"]["example"])

    def test_export_preflights_routing_conflicts_without_partial_files(self):
        toolkit, _ = self.bootstrap()
        (self.home / "AGENTS.template.md").write_text("<!-- BEGIN generic-agent-toolkit -->\nNew routing\n")
        (self.home / "gitignore.template").write_text("# BEGIN generic-agent-toolkit\nNew ignore rules\n")
        startup = self.root / ".agents/skills/agent-toolkit"
        startup.mkdir()
        (startup / "SKILL.md").write_text("Startup fixture")
        for filename, original in [("AGENTS.md", "<!-- BEGIN generic-agent-toolkit -->\nExisting customized routing\n"),
                                   (".gitignore", "# BEGIN generic-agent-toolkit\nExisting customized ignore rules\n")]:
            destination = Path(self.temp.name) / ("conflict-" + filename.replace(".", ""))
            destination.mkdir()
            (destination / filename).write_text(original)
            before = {p.relative_to(destination): p.read_bytes() for p in destination.rglob("*") if p.is_file()}
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                toolkit.export(destination)
            after = {p.relative_to(destination): p.read_bytes() for p in destination.rglob("*") if p.is_file()}
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
