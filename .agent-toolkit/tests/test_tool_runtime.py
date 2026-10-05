import hashlib
import io
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tool_runtime as runtime


class RuntimeTests(unittest.TestCase):
    def install_fake(self, root, tool="strix"):
        def native(root, tool_id, stage):
            (stage / runtime.NATIVE[tool_id][2].format(version="1.7.0")).write_bytes(b"verified executable")
            return "1.7.0", {"publisher": runtime.NATIVE[tool_id][0], "sha256": "f" * 64,
                             "artifact": runtime.NATIVE[tool_id][1].format(version="1.7.0")}
        with patch.object(runtime, "_native", side_effect=native):
            return runtime.install_runtime(root, tool, log=lambda line: None)

    def archive(self, directory, names):
        target = directory / "payload.zip"
        with zipfile.ZipFile(target, "w") as archive:
            for name, data, mode in names:
                item = zipfile.ZipInfo(name)
                item.external_attr = mode << 16
                archive.writestr(item, data)
        return target

    def test_unknown_selection_never_executes(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runtime, "_quiet") as quiet:
            root = Path(directory)
            for name in ["other", "strix;whoami", "../strix"]:
                self.assertEqual(runtime.install_runtime(root, name)["status"], "unsupported")
            quiet.assert_not_called()
            self.assertFalse((root / ".agent-toolkit").exists())

    def test_fixed_install_and_idempotence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(self.install_fake(root)["status"], "installed")
            command = runtime.runtime_command(root, "strix")
            self.assertTrue(command[0].endswith("strix-1.7.0-windows-x86_64.exe"))
            with patch.object(runtime, "_native") as install:
                self.assertEqual(runtime.install_runtime(root, "strix")["status"], "installed")
                install.assert_not_called()

    def test_entrypoint_and_dependency_changes_reject_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.install_fake(root)
            path = Path(runtime.runtime_command(root, "strix")[0])
            path.write_bytes(b"modified")
            self.assertIsNone(runtime.runtime_command(root, "strix"))
            self.assertEqual(runtime.runtime_status(root, "strix")["status"], "conflict")
            self.assertEqual(runtime.install_runtime(root, "strix")["status"], "conflict")
            self.assertEqual(path.read_bytes(), b"modified")

    def test_manifest_cannot_supply_custom_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.install_fake(root)
            path = root / runtime.STATE
            state = json.loads(path.read_text())
            state["tools"]["strix"]["command"] = ["cmd", "/c", "whoami"]
            path.write_text(json.dumps(state))
            with patch.object(runtime.subprocess, "run") as run:
                self.assertIsNone(runtime.runtime_command(root, "strix"))
                self.assertEqual(runtime.probe_command(root, "strix")["status"], "not-installed")
                run.assert_not_called()

    def test_partial_directory_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / runtime.BASE / "strix"
            target.mkdir(parents=True)
            sentinel = target / "custom.txt"
            sentinel.write_text("custom")
            with patch.object(runtime, "_native") as install:
                self.assertEqual(runtime.install_runtime(root, "strix")["status"], "manual")
                install.assert_not_called()
            self.assertEqual(sentinel.read_text(), "custom")

    def test_custom_manifest_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / runtime.STATE
            path.parent.mkdir(parents=True)
            original = '{"schema_version":1,"tools":{},"custom":"do not remove"}'
            path.write_text(original)
            self.assertEqual(runtime.install_runtime(root, "strix")["status"], "manual")
            self.assertEqual(path.read_text(), original)

    def test_unknown_exception_and_process_output_are_not_logged(self):
        with tempfile.TemporaryDirectory() as directory:
            logs = []
            with patch.object(runtime, "_native", side_effect=ValueError("secret-api-key-fixture")):
                result = runtime.install_runtime(Path(directory), "strix", log=logs.append)
            self.assertEqual(result["status"], "failed")
            self.assertNotIn("secret-api-key-fixture", json.dumps([result, logs]))
            self.assertFalse((Path(directory) / runtime.STATE).exists())

    def test_network_urls_and_redirects_rejected(self):
        for value in ["http://github.com/a", "https://evil.test/a", "https://github.com.evil.test/a",
                      "https://token@github.com/a", "https://github.com:444/a", "https://github.com/a#fragment"]:
            with self.subTest(value=value), self.assertRaises(runtime.RuntimeBlocked):
                runtime._validate_url(value, runtime.GITHUB_HOSTS)
        self.assertEqual(runtime._validate_url("https://release-assets.githubusercontent.com/a", runtime.GITHUB_HOSTS),
                         "https://release-assets.githubusercontent.com/a")
        redirect = runtime._Redirects(runtime.GITHUB_HOSTS)
        with self.assertRaises(runtime.RuntimeBlocked):
            redirect.redirect_request(None, None, 302, "", {}, "https://evil.test/token")

    def test_response_bounds_enforced(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = "https://github.com/file"
        response.headers = {"Content-Length": "1000"}
        opener = MagicMock()
        opener.open.return_value = response
        with patch.object(runtime.urllib.request, "build_opener", return_value=opener), self.assertRaises(runtime.RuntimeBlocked):
            runtime._fetch("https://github.com/file", runtime.GITHUB_HOSTS, limit=10)
        response.headers = {}
        response.read.return_value = b"x" * 11
        with patch.object(runtime.urllib.request, "build_opener", return_value=opener), self.assertRaises(runtime.RuntimeBlocked):
            runtime._fetch("https://github.com/file", runtime.GITHUB_HOSTS, limit=10)

    def test_archive_negative_cases_preflight_no_writes(self):
        cases = ["../tool.exe", "/tool.exe", "C:/tool.exe", "//server/tool.exe", "dir\\tool.exe",
                 "tool.exe\x01", "unwanted.exe"]
        for value in cases:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                archive = self.archive(root, [("tool.exe", b"ok", stat.S_IFREG), (value, b"bad", stat.S_IFREG)])
                destination = root / "unpacked"
                destination.mkdir()
                with self.assertRaises(runtime.RuntimeBlocked):
                    runtime._extract_zip(archive, destination, {"tool.exe"})
                self.assertEqual(list(destination.iterdir()), [])

    def test_archive_duplicates_links_and_special_files_rejected(self):
        for names in [[("tool.exe", b"ok", stat.S_IFREG), ("TOOL.EXE", b"bad", stat.S_IFREG)],
                      [("tool.exe", b"target", stat.S_IFLNK)], [("tool.exe", b"bad", stat.S_IFIFO)]]:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                archive = self.archive(root, names)
                with self.assertRaises(runtime.RuntimeBlocked):
                    runtime._extract_zip(archive, root / "out", {"tool.exe"})

    def test_archive_limits_and_complete_expected_members(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self.archive(root, [("tool.exe", b"1234", stat.S_IFREG)])
            with patch.object(runtime, "MAX_EXPANDED", 2), self.assertRaises(runtime.RuntimeBlocked):
                runtime._extract_zip(archive, root / "out", {"tool.exe"})
            with self.assertRaises(runtime.RuntimeBlocked):
                runtime._extract_zip(archive, root / "out", {"tool.exe", "missing"})

    def test_native_requires_publisher_digest_exact_url_and_platform(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = {"draft": False, "prerelease": False, "tag_name": "v1.7.0", "assets": [{
                "name": "strix-1.7.0-windows-x86_64.zip", "digest": "", "size": 10,
                "browser_download_url": "https://github.com/usestrix/strix/releases/download/v1.7.0/strix-1.7.0-windows-x86_64.zip"}]}
            with patch.object(runtime.os, "name", "nt"), patch.object(runtime.platform, "machine", return_value="AMD64"), patch.object(runtime, "_metadata", return_value=data), patch.object(runtime, "_fetch") as fetch:
                with self.assertRaises(runtime.RuntimeBlocked):
                    runtime._native(root, "strix", root)
                fetch.assert_not_called()
                data["assets"][0]["digest"] = "sha256:" + "a" * 64
                data["assets"][0]["browser_download_url"] = "https://github.com/other/strix/file.zip"
                with self.assertRaises(runtime.RuntimeBlocked):
                    runtime._native(root, "strix", root)
                fetch.assert_not_called()
            with patch.object(runtime.platform, "machine", return_value="arm64"), self.assertRaises(runtime.RuntimeBlocked):
                runtime._native(root, "strix", root)

    def test_native_bad_digest_not_extracted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = {"draft": False, "prerelease": False, "tag_name": "v1.7.0", "assets": [{
                "name": "strix-1.7.0-windows-x86_64.zip", "digest": "sha256:" + "a" * 64, "size": 3,
                "browser_download_url": "https://github.com/usestrix/strix/releases/download/v1.7.0/strix-1.7.0-windows-x86_64.zip"}]}
            with patch.object(runtime.os, "name", "nt"), patch.object(runtime.platform, "machine", return_value="AMD64"), patch.object(runtime, "_metadata", return_value=data), patch.object(runtime, "_fetch", return_value=b"bad"), patch.object(runtime, "_extract_zip") as extract:
                with self.assertRaises(runtime.RuntimeBlocked):
                    runtime._native(root, "strix", root)
                extract.assert_not_called()

    def test_native_fixed_clawscan_layout_activated_only_after_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = [("clawscan_v0.2.0_windows_amd64/", b"", stat.S_IFDIR),
                     ("clawscan_v0.2.0_windows_amd64/clawscan.exe", b"binary", stat.S_IFREG),
                     ("clawscan_v0.2.0_windows_amd64/README.md", b"official guide", stat.S_IFREG)]
            payload = self.archive(root, names).read_bytes()
            data = {"draft": False, "prerelease": False, "tag_name": "v0.2.0", "assets": [{
                "name": "clawscan_v0.2.0_windows_amd64.zip", "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
                "size": len(payload), "browser_download_url": "https://github.com/openclaw/clawscan/releases/download/v0.2.0/clawscan_v0.2.0_windows_amd64.zip"}]}
            with patch.object(runtime.os, "name", "nt"), patch.object(runtime.platform, "machine", return_value="AMD64"), patch.object(runtime, "_metadata", return_value=data), patch.object(runtime, "_fetch", return_value=payload):
                version, source = runtime._native(root, "clawscan", root)
            self.assertEqual(version, "0.2.0")
            self.assertEqual((root / "clawscan.exe").read_bytes(), b"binary")
            self.assertEqual(source["publisher"], "openclaw/clawscan")
            self.assertFalse((root / "clawscan_v0.2.0_windows_amd64").exists())

    def test_python_wheels_only_published_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "specify_cli-1.0.13-py3-none-any.whl"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("specify_cli-1.0.13.dist-info/METADATA", "Name: specify-cli\nVersion: 1.0.13\n")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            data = {"info": {"name": "specify-cli", "version": "1.0.13"}, "urls": [{"filename": path.name,
                    "packagetype": "bdist_wheel", "digests": {"sha256": digest}, "url": "https://files.pythonhosted.org/package.whl"}]}
            with patch.object(runtime, "_metadata", return_value=data):
                self.assertEqual(runtime._verify_wheels(root, "specify-cli", "1.0.13")["specify-cli"]["sha256"], digest)
                data["urls"][0]["digests"]["sha256"] = "0" * 64
                with self.assertRaises(runtime.RuntimeBlocked):
                    runtime._verify_wheels(root, "specify-cli", "1.0.13")
            path.unlink()
            (root / "package.tar.gz").write_bytes(b"source build")
            with self.assertRaises(runtime.RuntimeBlocked):
                runtime._verify_wheels(root, "specify-cli", "1.0.13")

    def test_probe_is_bounded_version_only_and_redacted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.install_fake(root)
            with patch.object(runtime.subprocess, "run", return_value=MagicMock(returncode=0)) as run:
                result = runtime.probe_command(root, "strix")
                self.assertEqual(result["status"], "verified")
                self.assertEqual(run.call_args.args[0][-1], "--version")
                self.assertEqual(run.call_args.kwargs["timeout"], 30)
                self.assertEqual(run.call_args.kwargs["stdout"], subprocess.DEVNULL)
                self.assertFalse(run.call_args.kwargs["shell"])
            with patch.object(runtime.subprocess, "run", side_effect=subprocess.TimeoutExpired("secret", 30)):
                result = runtime.probe_command(root, "strix")
                self.assertEqual(result["status"], "timeout")
                self.assertNotIn("secret", json.dumps(result))

    def test_unmanaged_command_detected_but_never_executed(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runtime.shutil, "which", return_value="C:/global/tool.exe"), patch.object(runtime.subprocess, "run") as run:
            root = Path(directory)
            self.assertTrue(runtime.runtime_status(root, "strix")["command_detected"])
            self.assertEqual(runtime.strix_auth_status(root)["status"], "not-installed")
            runtime.probe_command(root, "strix")
            run.assert_not_called()

    def test_docker_detected_daemon_unavailable_and_timeout(self):
        with patch.object(runtime.shutil, "which", return_value="docker.exe"), patch.object(runtime.subprocess, "run", return_value=MagicMock(returncode=1)) as run:
            self.assertEqual(runtime.docker_status()["status"], "daemon-unavailable")
            self.assertEqual(run.call_args.args[0], ["docker.exe", "info"])
            self.assertEqual(run.call_args.kwargs["timeout"], 20)
        with patch.object(runtime.shutil, "which", return_value="docker.exe"), patch.object(runtime.subprocess, "run", side_effect=subprocess.TimeoutExpired("secret", 20)):
            self.assertEqual(runtime.docker_status()["status"], "timeout")

    def test_strix_auth_only_saved_session_no_token_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.install_fake(root)
            with patch.object(runtime.subprocess, "run", return_value=MagicMock(returncode=0)) as run:
                self.assertEqual(runtime.strix_auth_status(root)["status"], "session-detected")
                self.assertEqual(run.call_args.args[0][-2:], ["auth", "status"])
                self.assertEqual(run.call_args.kwargs["stdout"], subprocess.DEVNULL)
            with patch.object(runtime.subprocess, "Popen") as start:
                runtime.start_strix_login(root)
                self.assertEqual(start.call_args.args[0][-3:], ["auth", "login", "chatgpt"])
                self.assertEqual(start.call_args.kwargs["stdin"], subprocess.DEVNULL)

    def test_child_environment_keeps_only_selected_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = root / runtime.BASE / "settings.json"
            settings.parent.mkdir(parents=True)
            settings.write_text(json.dumps({"auth_mode": "chatgpt", "model": "chatgpt/gpt-6.1-sol"}))
            with patch.dict(runtime.os.environ, {"OTHER_SECRET": "fixture", "LLM_API_KEY": "api-fixture"}):
                env = runtime._env(root, "strix")
                self.assertNotIn("OTHER_SECRET", env)
                self.assertNotIn("LLM_API_KEY", env)
                self.assertEqual(env["STRIX_LLM"], "chatgpt/gpt-6.1-sol")
                settings.write_text(json.dumps({"auth_mode": "api", "model": "openai/gpt-6"}))
                self.assertEqual(runtime._env(root, "strix")["LLM_API_KEY"], "api-fixture")
                settings.write_text(json.dumps({"auth_mode": "chatgpt", "model": "chatgpt/model;whoami"}))
                with self.assertRaises(ValueError):
                    runtime._env(root, "strix")
                settings.write_text(json.dumps({"auth_mode": "later", "model": ""}))
                self.assertNotIn("STRIX_LLM", runtime._env(root, "strix"))
                settings.write_text(json.dumps({"auth_mode": "api", "model": "openrouter/vendor/model"}))
                self.assertEqual(runtime._env(root, "strix")["STRIX_LLM"], "openrouter/vendor/model")

    def test_install_subprocess_timeout_kills_and_output_discarded(self):
        process = MagicMock()
        process.poll.return_value = None
        with patch.object(runtime.subprocess, "Popen", return_value=process) as start, patch.object(runtime.time, "monotonic", side_effect=[0, 2]):
            with self.assertRaises(subprocess.TimeoutExpired):
                runtime._quiet(["fixed", "argument"], Path.cwd(), timeout=1)
            process.kill.assert_called_once()
            self.assertEqual(start.call_args.kwargs["stdout"], subprocess.DEVNULL)
            self.assertFalse(start.call_args.kwargs["shell"])

    def test_runtime_link_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.install_fake(root)
            executable = Path(runtime.runtime_command(root, "strix")[0])
            external = root / "outside.exe"
            external.write_bytes(executable.read_bytes())
            executable.unlink()
            try:
                executable.symlink_to(external)
            except OSError:
                self.skipTest("Windows symbolic-link permission unavailable")
            self.assertIsNone(runtime.runtime_command(root, "strix"))

    def test_python_commands_isolate_project_imports(self):
        for tool in ["spec-kit", "graphify"]:
            command = runtime._relative_command(tool, "1.0.0", "fixed/runtime")
            self.assertEqual(command[1:4], ["-I", "-B", "-c"])

    def test_isolated_python_recipe_does_not_execute_project_shadow(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "shadow-executed.txt"
            (root / "specify_cli.py").write_text("from pathlib import Path\nPath('shadow-executed.txt').write_text('bad')\ndef main(): pass\n")
            flags = runtime._relative_command("spec-kit", "1.0.0", "fixed/runtime")[1:]
            subprocess.run([sys.executable, *flags], cwd=root, timeout=15, shell=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.assertFalse(marker.exists())

    @unittest.skipUnless(sys.platform == "win32", "Windows long-path fixture")
    def test_windows_tree_hash_covers_deep_files_and_survives_relocation(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            stage = fixture / "short"
            stage.mkdir()
            deep = runtime._extended(stage) / ("nested-" + "x" * 95) / ("more-" + "y" * 95)
            deep.mkdir(parents=True)
            file = deep / "dependency.js"
            file.write_text("verified content")
            before = runtime._tree_digest(stage)
            target = fixture / "longer-activation-folder" / "runtime-version"
            target.parent.mkdir()
            stage.rename(target)
            self.assertEqual(before, runtime._tree_digest(target))
            activated = runtime._extended(target) / file.relative_to(runtime._extended(stage))
            activated.write_text("modified content")
            self.assertNotEqual(before, runtime._tree_digest(target))
            # Windows temporary cleanup itself needs the extended path.
            runtime.shutil.rmtree(runtime._extended(target))

    @unittest.skipUnless(sys.platform == "win32", "Windows junction fixture")
    def test_managed_parent_junction_rejected_external_contents_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            root, external = fixture / "project", fixture / "external"
            root.mkdir()
            external.mkdir()
            sentinel = external / "keep.txt"
            sentinel.write_text("do not overwrite")
            parent = root / ".agent-toolkit" / "runtime"
            parent.mkdir(parents=True)
            link = parent / "optional"
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(external)],
                                    capture_output=True, timeout=10, shell=False)
            if result.returncode:
                self.skipTest("Windows junction could not be created")
            with patch.object(runtime, "_native") as install:
                self.assertEqual(runtime.install_runtime(root, "strix", log=lambda _: None)["status"], "failed")
                install.assert_not_called()
            self.assertEqual(sentinel.read_text(), "do not overwrite")
            self.assertEqual(list(external.iterdir()), [sentinel])


if __name__ == "__main__":
    unittest.main()
