"""Independent negative and behavior checks for guided optional setup."""
import io
import json
import os
from pathlib import Path
import queue
import sys
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import installer
import probe
import setup_support as support
import setup_wizard as guided

SECRET = "qa-secret-fixture-must-never-appear"


class GuidedSetupTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def write(self, relative, data):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def wizard(self):
        wizard = object.__new__(guided.ToolsWizard)
        wizard.project = self.root
        wizard.events = queue.Queue()
        wizard.running = False
        wizard.cancel = threading.Event()
        wizard.actions = [MagicMock()]
        wizard.status = MagicMock()
        wizard.window = MagicMock()
        wizard.window.winfo_exists.return_value = False
        wizard.append = MagicMock()
        return wizard

    def fake_thread(self, target, **kwargs):
        thread = MagicMock()
        thread.start.side_effect = target
        return thread

    def test_preferences_roundtrip_preserves_provider_boundaries(self):
        for mode, model in [("chatgpt", "chatgpt/gpt-6.1-sol"),
                            ("api", "openrouter/anthropic/claude-sonnet-4")]:
            with self.subTest(mode=mode), patch.dict(os.environ, {"LLM_API_KEY": SECRET}):
                support.save_strix_settings(self.root, mode, model)
                self.assertEqual(support.strix_settings(self.root), {"auth_mode": mode, "model": model})
                stored = (self.root / ".agent-toolkit/runtime/optional/settings.json").read_text()
                self.assertNotIn(SECRET, stored)
                self.assertEqual(set(json.loads(stored)), {"auth_mode", "model"})
        self.assertFalse((self.root / ".codex").exists())
        self.assertFalse((self.root / ".claude").exists())

    def test_explicit_later_does_not_inherit_model(self):
        support.save_strix_settings(self.root, "later", "ignored")
        with patch.dict(os.environ, {"STRIX_LLM": "chatgpt/gpt-6.1-sol"}):
            self.assertEqual(support.strix_settings(self.root), {"auth_mode": "later", "model": ""})

    def test_unset_preferences_detect_current_auth_mode(self):
        for model, mode in [("", "later"), ("chatgpt/gpt-6.1-sol", "chatgpt"), ("openai/gpt-6.1-sol", "api")]:
            with self.subTest(model=model), patch.dict(os.environ, {"STRIX_LLM": model}):
                self.assertEqual(support.strix_settings(self.root), {"auth_mode": mode, "model": model})

    def test_invalid_auth_or_model_never_replaces_valid_preferences(self):
        support.save_strix_settings(self.root, "chatgpt", "chatgpt/gpt-6.1-sol")
        original = (self.root / ".agent-toolkit/runtime/optional/settings.json").read_bytes()
        for mode, model in [("other", "openai/gpt-6.1-sol"), ("api", "chatgpt/gpt-6.1-sol"),
                            ("chatgpt", "openai/gpt-6.1-sol"), ("api", "--model"),
                            ("api", "openai/gpt;whoami"), ("api", "openai/gpt\nprivate")]:
            with self.subTest(mode=mode, model=model), self.assertRaises(ValueError):
                support.save_strix_settings(self.root, mode, model)
            self.assertEqual((self.root / ".agent-toolkit/runtime/optional/settings.json").read_bytes(), original)

    def test_malformed_preferences_fail_without_exposing_data(self):
        for value in [None, [], SECRET, {"auth_mode": []}, {"model": [SECRET]},
                      {"auth_mode": "api", "model": "bad;" + SECRET}]:
            with self.subTest(value=type(value).__name__):
                self.write(".agent-toolkit/runtime/optional/settings.json", value)
                with patch.dict(os.environ, {"STRIX_LLM": ""}), self.assertRaises(ValueError) as raised:
                    support.strix_settings(self.root)
                self.assertNotIn(SECRET, str(raised.exception))

    def test_session_credentials_do_not_touch_registry_or_project(self):
        registry = MagicMock()
        with patch.dict(sys.modules, {"winreg": registry}), patch.dict(os.environ, {}, clear=True):
            result = support.set_credential("TESTSPRITE_API_KEY", SECRET)
            self.assertEqual(os.environ["TESTSPRITE_API_KEY"], SECRET)
            self.assertIn("session-only", result)
            self.assertNotIn(SECRET, result)
            registry.CreateKeyEx.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_invalid_credentials_never_write_environment_or_registry(self):
        registry = MagicMock()
        for name, value in [("PATH", SECRET), ("TESTSPRITE_API_KEY", ""), ("LLM_API_KEY", "x\ny"),
                            ("CONTEXT7_API_KEY", "x\0y"), ("TESTSPRITE_API_KEY", "x" * 8193)]:
            with self.subTest(name=name), patch.dict(sys.modules, {"winreg": registry}), \
                 patch.dict(os.environ, {"TESTSPRITE_API_KEY": "original"}, clear=True):
                with self.assertRaises(ValueError) as raised:
                    support.set_credential(name, value, persist=True)
                self.assertNotIn(SECRET, str(raised.exception))
                self.assertEqual(dict(os.environ), {"TESTSPRITE_API_KEY": "original"})
                registry.CreateKeyEx.assert_not_called()

    def registry(self, old_value):
        registry = MagicMock()
        registry.QueryValueEx.side_effect = FileNotFoundError() if old_value is None else None
        registry.QueryValueEx.return_value = (old_value, 1)
        return registry

    def test_explicit_persistence_conflict_preserves_old_values_and_redacts(self):
        registry = self.registry("existing-private-value")
        with patch.dict(sys.modules, {"winreg": registry}), patch.object(support.sys, "platform", "win32"), \
             patch.dict(os.environ, {"TESTSPRITE_API_KEY": "process-old"}, clear=True):
            with self.assertRaises(ValueError) as raised:
                support.set_credential("TESTSPRITE_API_KEY", SECRET, persist=True)
            registry.SetValueEx.assert_not_called()
            self.assertEqual(os.environ["TESTSPRITE_API_KEY"], "process-old")
            self.assertNotIn(SECRET, str(raised.exception))
            self.assertNotIn("existing-private-value", str(raised.exception))

    def test_windows_persistence_needs_explicit_opt_in_and_fixed_name(self):
        registry = self.registry(None)
        with patch.dict(sys.modules, {"winreg": registry}), patch.object(support.sys, "platform", "win32"), \
             patch("ctypes.windll", create=True), patch.dict(os.environ, {}, clear=True):
            result = support.set_credential("CONTEXT7_API_KEY", SECRET, persist=True)
            self.assertEqual(registry.SetValueEx.call_args.args[1], "CONTEXT7_API_KEY")
            self.assertEqual(registry.SetValueEx.call_args.args[4], SECRET)
            self.assertNotIn(SECRET, result)
            self.assertEqual(os.environ["CONTEXT7_API_KEY"], SECRET)

    def test_non_windows_persistence_stays_manual(self):
        with patch.object(support.sys, "platform", "linux"), patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                support.set_credential("LLM_API_KEY", SECRET, persist=True)
            self.assertNotIn("LLM_API_KEY", os.environ)

    def test_credentials_ui_clears_entries_and_sanitizes_worker_exception(self):
        wizard = self.wizard()
        wizard.credentials = {"TESTSPRITE_API_KEY": MagicMock(), "CONTEXT7_API_KEY": MagicMock()}
        wizard.credentials["TESTSPRITE_API_KEY"].get.return_value = SECRET
        wizard.credentials["CONTEXT7_API_KEY"].get.return_value = ""
        wizard.persist = MagicMock()
        wizard.persist.get.return_value = False
        with patch("setup_wizard.threading.Thread", side_effect=self.fake_thread), \
             patch("setup_wizard.set_credential", side_effect=ValueError(SECRET)) as setter:
            wizard.apply_credentials()
        setter.assert_called_once_with("TESTSPRITE_API_KEY", SECRET, persist=False)
        for variable in wizard.credentials.values():
            variable.set.assert_called_once_with("")
        wizard.poll()
        visible = repr(wizard.append.call_args_list) + repr(wizard.status.set.call_args_list)
        self.assertNotIn(SECRET, visible)
        self.assertIn("not-saved", visible)

    def test_optional_worker_failure_keeps_base_installed_and_redacts(self):
        wizard = self.wizard()
        with patch("setup_wizard.threading.Thread", side_effect=self.fake_thread):
            wizard.work(lambda: (_ for _ in ()).throw(RuntimeError(SECRET)))
        wizard.poll()
        visible = repr(wizard.append.call_args_list)
        self.assertNotIn(SECRET, visible)
        self.assertIn("Base toolkit remains installed", visible)
        self.assertIn("RuntimeError", visible)
        self.assertFalse(wizard.running)

    def test_unselected_tools_do_not_install(self):
        wizard = self.wizard()
        wizard.selected = {"strix": MagicMock()}
        wizard.selected["strix"].get.return_value = False
        with patch("setup_wizard.install_runtime") as install:
            wizard.install_selected()
        install.assert_not_called()
        self.assertTrue(wizard.events.empty())

    def test_optional_tool_failure_does_not_prevent_other_selection(self):
        wizard = self.wizard()
        wizard.selected = {name: MagicMock() for name in ["strix", "lighthouse"]}
        for variable in wizard.selected.values():
            variable.get.return_value = True
        with patch("setup_wizard.threading.Thread", side_effect=self.fake_thread), \
             patch("setup_wizard.install_runtime", side_effect=[ValueError(SECRET), {"status": "installed"}]) as install:
            wizard.install_selected()
        self.assertEqual([call.args[1] for call in install.call_args_list], ["strix", "lighthouse"])
        wizard.poll()
        visible = repr(wizard.append.call_args_list)
        self.assertNotIn(SECRET, visible)
        self.assertIn("failed", visible)
        self.assertIn("installed", visible)

    def test_browser_login_requires_chatgpt_choice_and_cancel_kills_owned_child(self):
        wizard = self.wizard()
        wizard.mode = MagicMock()
        wizard.mode.get.return_value = "api"
        with patch("setup_wizard.start_strix_login") as start:
            wizard.login()
            start.assert_not_called()
        wizard.mode.get.return_value = "chatgpt"
        wizard.model = MagicMock()
        wizard.model.get.return_value = "chatgpt/gpt-6.1-sol"
        wizard.work = MagicMock()
        child = MagicMock()
        child.poll.return_value = None
        with patch("setup_wizard.start_strix_login", return_value=child), \
             patch("setup_wizard.strix_auth_status") as status:
            wizard.login()
            wizard.cancel_login()
            result = wizard.work.call_args.args[0]()
        self.assertEqual(result["Strix auth"]["status"], "cancelled")
        child.terminate.assert_called_once()
        child.wait.assert_called_once_with(timeout=5)
        status.assert_not_called()
        self.assertIsNone(wizard.login_child)

    def test_base_guidance_only_opens_on_success_when_selected(self):
        for status, selected, should_open in [("installed", True, True), ("installed", False, False), ("incomplete", True, False)]:
            with self.subTest(status=status, selected=selected):
                wizard = object.__new__(installer.Wizard)
                wizard.events = queue.Queue()
                wizard.events.put(("done", {"status": status, "agents": 13, "project_skills": 31, "issues": []}))
                wizard.fields = []
                for name in ["root", "select", "browse", "button", "configure", "status", "guide", "configure_tools"]:
                    setattr(wizard, name, MagicMock())
                wizard.guide.get.return_value = selected
                with patch("installer.messagebox.showwarning"), patch("installer.messagebox.showinfo"):
                    wizard.poll()
                self.assertEqual(wizard.configure_tools.called, should_open)

    def test_doctor_flags_managed_conflict_even_when_global_cli_is_detected(self):
        from manage import Toolkit
        self.write(".agent-toolkit/registry.json", {"schema_version": 1, "tools": [
            {"id": "lighthouse", "type": "cli", "command": "lighthouse"}]})
        self.write(".agent-toolkit/runtime/optional/manifest.json", {"custom": "preserve"})
        output = io.StringIO()
        with patch("manage.shutil.which", return_value="global-unverified-command"), \
             patch("manage.mcp_configs", return_value=[]), patch("manage.Path.home", return_value=self.root), \
             patch("sys.stdout", output):
            result = Toolkit(self.root).doctor()
        self.assertEqual(result, 1, output.getvalue())
        self.assertIn("managed runtime", output.getvalue())

    def test_chatgpt_doctor_does_not_require_api_key(self):
        from manage import Toolkit
        self.write(".agent-toolkit/registry.json", {"schema_version": 1, "tools": [
            {"id": "strix", "type": "cli", "command": "strix", "credential_envs": ["STRIX_LLM", "LLM_API_KEY"]}]})
        support.save_strix_settings(self.root, "chatgpt", "chatgpt/gpt-6.1-sol")
        output = io.StringIO()
        with patch("manage.shutil.which", return_value="global-unverified-command"), \
             patch("manage.mcp_configs", return_value=[]), patch.dict(os.environ, {}, clear=True), \
             patch("manage.Path.home", return_value=self.root), \
             patch("tool_runtime.strix_auth_status", return_value={"status": "session-detected"}), \
             patch("sys.stdout", output):
            result = Toolkit(self.root).doctor()
        self.assertEqual(result, 0, output.getvalue())
        self.assertNotIn("missing LLM_API_KEY", output.getvalue())
        self.assertNotIn("missing STRIX_LLM", output.getvalue())

    def response(self, data):
        response = MagicMock()
        response.__enter__.return_value = response
        response.headers = {}
        response.read.return_value = data
        return response

    def test_http_probe_only_initializes_lists_and_discards_descriptions(self):
        opener = MagicMock()
        opener.open.side_effect = [self.response(b'{"result":{"protocolVersion":"2025-03-26"}}'),
                                   self.response(b""), self.response(json.dumps({"result": {"tools": [{"name": "fixture", "description": SECRET}]}}).encode())]
        with patch("probe.urllib.request.build_opener", return_value=opener), patch.dict(os.environ, {"CONTEXT7_API_KEY": SECRET}):
            result = probe.probe_http({"url": "https://mcp.context7.com/mcp", "env_http_headers": {"CONTEXT7_API_KEY": "CONTEXT7_API_KEY"}})
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["tool_count"], 1)
        self.assertNotIn(SECRET, json.dumps(result))
        methods = [json.loads(call.args[0].data)["method"] for call in opener.open.call_args_list]
        self.assertEqual(methods, ["initialize", "notifications/initialized", "tools/list"])
        for call in opener.open.call_args_list:
            self.assertEqual(call.kwargs["timeout"], 20)

    def test_http_probe_refuses_redirect_before_sending_credentials_elsewhere(self):
        original_builder = urllib.request.build_opener
        def simulated_builder(*handlers):
            opener = original_builder(*handlers)
            redirect = next(handler for handler in opener.handlers if isinstance(handler, urllib.request.HTTPRedirectHandler))
            def open_request(request, **kwargs):
                return redirect.redirect_request(request, None, 302, "Found", {}, "https://evil.example/collect")
            opener.open = open_request
            return opener
        with patch("probe.urllib.request.build_opener", side_effect=simulated_builder), \
             patch.dict(os.environ, {"CONTEXT7_API_KEY": SECRET}):
            with self.assertRaises(ValueError) as raised:
                probe.probe_http({"url": "https://mcp.context7.com/mcp", "env_http_headers": {"CONTEXT7_API_KEY": "CONTEXT7_API_KEY"}})
        self.assertNotIn(SECRET, str(raised.exception))

    def test_http_probe_oversized_body_cannot_return_verified(self):
        opener = MagicMock()
        opener.open.return_value = self.response(b"x" * 2_000_001)
        with patch("probe.urllib.request.build_opener", return_value=opener):
            with self.assertRaises(ValueError):
                probe.probe_http({"url": "https://mcp.context7.com/mcp"})
        self.assertEqual(opener.open.call_count, 1)

    def test_http_malformed_protocol_cannot_be_verified(self):
        for tools in [SECRET, {}, None, [SECRET], [{}], [{"name": []}]]:
            with self.subTest(tools=type(tools).__name__):
                opener = MagicMock()
                opener.open.side_effect = [self.response(b'{"result":{"protocolVersion":"2025-03-26"}}'),
                                           self.response(b""), self.response(json.dumps({"result": {"tools": tools}}).encode())]
                with patch("probe.urllib.request.build_opener", return_value=opener):
                    try:
                        result = probe.probe_http({"url": "https://mcp.context7.com/mcp"})
                    except ValueError as error:
                        self.assertNotIn(SECRET, str(error))
                    else:
                        self.assertNotEqual(result["status"], "verified")
        for payload in [b"null", b"[]", b'{"result": "secret-fixture"}', b'{"result": {}}']:
            with self.subTest(payload=payload):
                opener = MagicMock()
                opener.open.return_value = self.response(payload)
                with patch("probe.urllib.request.build_opener", return_value=opener):
                    try:
                        result = probe.probe_http({"url": "https://mcp.context7.com/mcp"})
                    except ValueError:
                        pass
                    else:
                        self.assertNotEqual(result["status"], "verified")

    def project_mcp(self, tool):
        self.write(".agent-toolkit/project.json", {"provider": "claude"})
        self.write(".mcp.json", {"mcpServers": {tool["id"]: {"type": "http", "url": tool["mcp"]["url"]}}})

    def test_custom_and_forged_registry_mcp_do_not_execute(self):
        tools = [{"id": "unknown", "mcp": {"transport": "http", "url": "https://evil.example/mcp"}},
                 {"id": "context7", "mcp": {"transport": "http", "url": "https://evil.example/mcp", "credential_env": "CONTEXT7_API_KEY"}}]
        for tool in tools:
            with self.subTest(tool=tool["id"]):
                self.project_mcp(tool)
                with patch("probe.probe_http") as http, patch("probe.probe_stdio") as stdio:
                    result = probe.probe_mcps(self.root, [tool], {"tools": {}})
                http.assert_not_called()
                stdio.assert_not_called()
                self.assertNotEqual(result[tool["id"]]["status"], "verified")

    def test_testsprite_modified_state_and_custom_launch_are_not_probed(self):
        tool = {"id": "testsprite", "mcp": {"transport": "stdio", "package": "@testsprite/testsprite-mcp",
                                             "version": "0.0.46", "credential_env": "TESTSPRITE_API_KEY", "server_env": "API_KEY"}}
        self.write(".agent-toolkit/project.json", {"provider": "codex"})
        config = self.root / ".codex/config.toml"
        config.parent.mkdir()
        config.write_text('[mcp_servers.testsprite]\ncommand = "arbitrary-command"\nargs = ["fake-mcp_launch.py", "wrong-tool"]\n')
        arbitrary = self.root / "server.js"
        arbitrary.write_text("custom file must never execute")
        state = {"tools": {"testsprite": {"npm": {"package": "@testsprite/testsprite-mcp", "version": "0.0.46", "entrypoint": "server.js"}}}}
        with patch("probe.probe_stdio") as stdio:
            result = probe.probe_mcps(self.root, [tool], state)
        stdio.assert_not_called()
        self.assertNotEqual(result["testsprite"]["status"], "verified")

    def test_generated_testsprite_launch_is_accepted_for_every_provider(self):
        from configuration import configure_mcp
        from providers import _mcp
        tool = {"id": "testsprite", "mcp": {"transport": "stdio", "package": "@testsprite/testsprite-mcp",
                                             "version": "0.0.46", "credential_env": "TESTSPRITE_API_KEY", "server_env": "API_KEY"}}
        entry = ".agent-toolkit/runtime/testsprite/0.0.46/node_modules/@testsprite/testsprite-mcp/dist/index.js"
        path = self.root / entry
        path.parent.mkdir(parents=True)
        path.write_text("fixture protocol server")
        state = {"tools": {"testsprite": {"npm": {"package": "@testsprite/testsprite-mcp", "version": "0.0.46", "entrypoint": entry}}}}
        for provider in ["codex", "claude", "opencode"]:
            with self.subTest(provider=provider):
                self.write(".agent-toolkit/project.json", {"provider": provider})
                if provider == "codex":
                    configure_mcp(self.root, [tool], state)
                else:
                    config = _mcp(self.root, provider, tool, state)
                    self.write(".mcp.json" if provider == "claude" else "opencode.json",
                               {"mcpServers" if provider == "claude" else "mcp": {"testsprite": config}})
                with patch("probe.probe_stdio", return_value={"status": "verified", "tool_count": 1}) as stdio:
                    result = probe.probe_mcps(self.root, [tool], state)
                self.assertEqual(result["testsprite"]["status"], "verified")
                stdio.assert_called_once()


if __name__ == "__main__":
    unittest.main()
