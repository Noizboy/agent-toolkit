"""Opt-in, project-local CLI installation. Setup never runs scans or model calls.

Recipes are bundled code, not commands supplied by the downloaded registry.
Publisher digests, exact versions and entrypoint/tree hashes gate activation and use.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile

from sources import mcp_environment, safe_path, save_json


RECIPES = {
    "strix": {"label": "Strix", "command": "strix", "docs": "https://docs.strix.ai/quickstart"},
    "spec-kit": {"label": "Spec Kit / Specify", "command": "specify", "docs": "https://github.github.io/spec-kit/installation.html"},
    "clawscan": {"label": "ClawScan", "command": "clawscan", "docs": "https://github.com/openclaw/clawscan"},
    "lighthouse": {"label": "Lighthouse", "command": "lighthouse", "docs": "https://github.com/GoogleChrome/lighthouse"},
    "graphify": {"label": "Graphify", "command": "graphify", "docs": "https://github.com/Graphify-Labs/graphify"},
}
NATIVE = {"strix": ("usestrix/strix", "strix-{version}-windows-x86_64.zip", "strix-{version}-windows-x86_64.exe"),
          "clawscan": ("openclaw/clawscan", "clawscan_v{version}_windows_amd64.zip", "clawscan.exe")}
PYTHON = {"spec-kit": ("specify-cli", "from specify_cli import main; main()"),
          "graphify": ("graphifyy", "from graphify.__main__ import main; main()")}
GITHUB_HOSTS = {"api.github.com", "github.com", "release-assets.githubusercontent.com"}
PYPI_HOSTS = {"pypi.org", "files.pythonhosted.org"}
MAX_METADATA = 8 * 1024 * 1024
MAX_ARTIFACT = 256 * 1024 * 1024
MAX_EXPANDED = 768 * 1024 * 1024
MAX_MEMBERS = 12000
STATE = ".agent-toolkit/runtime/optional/manifest.json"
BASE = ".agent-toolkit/runtime/optional"


class RuntimeBlocked(Exception):
    """Controlled, non-secret reason; unexpected exception text is never surfaced."""


def _result(tool_id, status, message, **extra):
    return {"tool": tool_id, "status": status, "message": message,
            "docs": RECIPES.get(tool_id, {}).get("docs", ""),
            "checked_at": datetime.now(timezone.utc).isoformat(), **extra}


def _validate_url(url, hosts):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username
            or parsed.password or parsed.port not in (None, 443) or parsed.fragment):
        raise RuntimeBlocked("Download destination is outside the trusted publisher hosts.")
    return url


class _Redirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, hosts):
        self.hosts = hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_url(newurl, self.hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch(url, hosts, limit=MAX_METADATA):
    _validate_url(url, hosts)
    opener = urllib.request.build_opener(_Redirects(hosts))
    request = urllib.request.Request(url, headers={"User-Agent": "Agent-Toolkit-Guided-Setup", "Accept": "application/json"})
    with opener.open(request, timeout=45) as response:
        _validate_url(response.geturl(), hosts)
        length = response.headers.get("Content-Length")
        if length and int(length) > limit:
            raise RuntimeBlocked("Publisher response exceeds the download limit.")
        data = response.read(limit + 1)
        if len(data) > limit:
            raise RuntimeBlocked("Publisher response exceeds the download limit.")
        return data


def _metadata(url, hosts):
    data = json.loads(_fetch(url, hosts))
    if not isinstance(data, dict):
        raise RuntimeBlocked("Publisher metadata is invalid.")
    return data


def _version(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,3}(?:[a-z][a-z0-9.]*)?", value):
        raise RuntimeBlocked("Publisher version cannot be safely pinned.")
    return value


def _hash(path):
    path = _extended(path)
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _extended(path):
    """Avoid Win32 silently treating deep managed files as nonexistent."""
    path = Path(path).resolve()
    if sys.platform == "win32" and not str(path).startswith("\\\\?\\"):
        value = str(path)
        return Path("\\\\?\\UNC\\" + value[2:]) if value.startswith("\\\\") else Path("\\\\?\\" + value)
    return path


def _tree_digest(root):
    root = _extended(root)
    digest = hashlib.sha256()
    for item in sorted(root.rglob("*")):
        safe_path(root, item.relative_to(root).as_posix())
        if item.is_file():
            digest.update(item.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            digest.update(_hash(item).encode())
    return digest.hexdigest()


def _env(root=None, tool_id=None):
    env = mcp_environment({})
    env.update({"PYTHONDONTWRITEBYTECODE": "1", "PIP_CONFIG_FILE": os.devnull,
                "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PIP_NO_INPUT": "1"})
    if tool_id == "strix" and root is not None:
        from setup_support import strix_settings
        settings = strix_settings(root)
        mode, model = settings["auth_mode"], settings["model"]
        if mode != "later" and model:
            env["STRIX_LLM"] = model
        if mode == "api" and os.environ.get("LLM_API_KEY"):
            env["LLM_API_KEY"] = os.environ["LLM_API_KEY"]
    return env


def _background():
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if sys.platform == "win32" else {}


def _quiet(command, cwd, timeout=300, env=None, bounded_directory=None):
    """Installation commands discard all subprocess text, including errors."""
    process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, shell=False, env=env or _env(), **_background())
    deadline = time.monotonic() + timeout
    try:
        while process.poll() is None:
            if time.monotonic() > deadline:
                raise subprocess.TimeoutExpired(command, timeout)
            if bounded_directory is not None:
                files = list(_extended(bounded_directory).rglob("*"))
                if len(files) > 100000 or sum(item.stat().st_size for item in files if item.is_file()) > MAX_EXPANDED:
                    raise RuntimeBlocked("Package staging exceeds disk resource limits.")
            time.sleep(0.1)
        if process.returncode:
            raise RuntimeBlocked("The verified installation command did not complete; use the official guide.")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)


def _read_state(root):
    path = safe_path(root, STATE)
    if not path.exists():
        return {"schema_version": 1, "tools": {}}
    if path.stat().st_size > MAX_METADATA:
        raise RuntimeBlocked("Runtime manifest is invalid; preserve it and review the conflict.")
    state = json.loads(path.read_text(encoding="utf-8-sig"))
    if (not isinstance(state, dict) or set(state) != {"schema_version", "tools"}
            or state["schema_version"] != 1 or not isinstance(state["tools"], dict)
            or any(key not in RECIPES for key in state["tools"])):
        raise RuntimeBlocked("Runtime manifest is customized or invalid; preserve it and review the conflict.")
    return state


def _relative_command(tool_id, version, prefix):
    if tool_id in NATIVE:
        return [prefix + "/" + NATIVE[tool_id][2].format(version=version)]
    if tool_id in PYTHON:
        executable = "/venv/Scripts/python.exe" if os.name == "nt" else "/venv/bin/python"
        return [prefix + executable, "-I", "-B", "-c", PYTHON[tool_id][1]]
    if tool_id == "lighthouse":
        node = "/node.exe" if os.name == "nt" else "/node"
        return [prefix + node, prefix + "/node_modules/lighthouse/cli/index.js"]
    raise RuntimeBlocked("Unknown optional tool.")


def _entry(root, tool_id):
    if tool_id not in RECIPES:
        raise RuntimeBlocked("Unknown optional tool.")
    record = _read_state(root)["tools"].get(tool_id)
    if record is None:
        return None
    if not isinstance(record, dict):
        raise RuntimeBlocked("Runtime manifest entry is invalid.")
    if set(record) != {"version", "directory", "command", "hashes", "tree_sha256", "source"}:
        raise RuntimeBlocked("Runtime manifest entry is customized or incomplete.")
    version = _version(record.get("version"))
    prefix = BASE + "/" + tool_id + "/" + version
    expected = _relative_command(tool_id, version, prefix)
    if (record.get("command") != expected or record.get("directory") != prefix
            or not isinstance(record.get("hashes"), dict)
            or not re.fullmatch(r"[a-f0-9]{64}", record.get("tree_sha256", ""))):
        raise RuntimeBlocked("Managed runtime state differs from its fixed recipe; preserve it for review.")
    source = record.get("source")
    if not isinstance(source, dict):
        raise RuntimeBlocked("Managed publisher provenance is missing.")
    if tool_id in NATIVE:
        if (source.get("publisher") != NATIVE[tool_id][0]
                or source.get("artifact") != NATIVE[tool_id][1].format(version=version)
                or not re.fullmatch(r"[a-f0-9]{64}", source.get("sha256", ""))):
            raise RuntimeBlocked("Managed native publisher provenance is invalid.")
    elif tool_id in PYTHON:
        if source.get("publisher") != "pypi.org" or source.get("package") != PYTHON[tool_id][0] or not isinstance(source.get("wheels"), dict):
            raise RuntimeBlocked("Managed Python publisher provenance is invalid.")
    elif (source.get("publisher") != "registry.npmjs.org" or source.get("package") != "lighthouse"
          or not re.fullmatch(r"sha512-[A-Za-z0-9+/]+=*", source.get("integrity", ""))):
        raise RuntimeBlocked("Managed npm publisher provenance is invalid.")
    files = [part for part in expected if part.startswith(prefix + "/")]
    if set(files) != set(record["hashes"]):
        raise RuntimeBlocked("Managed entrypoint hashes are incomplete.")
    for relative in files:
        path = _extended(safe_path(root, relative))
        if not path.is_file() or _hash(path) != record["hashes"][relative]:
            raise RuntimeBlocked("Managed runtime was changed or is incomplete; preserve it for review.")
    directory = safe_path(root, prefix)
    if _tree_digest(directory) != record["tree_sha256"]:
        raise RuntimeBlocked("Managed runtime files changed; preserve them for review.")
    return record


def runtime_command(root: Path, tool_id: str):
    """Only return bundled-recipe commands whose managed artifacts still match."""
    try:
        record = _entry(root, tool_id)
        if record is None:
            return None
        return [str(safe_path(root, part)) if part.startswith(record["directory"] + "/") else part
                for part in record["command"]]
    except (OSError, ValueError, KeyError, TypeError, RuntimeBlocked):
        return None


def runtime_status(root: Path, tool_id: str):
    if tool_id not in RECIPES:
        return _result(tool_id, "unsupported", "Unknown optional tool.")
    try:
        record = _entry(root, tool_id)
        if record:
            return _result(tool_id, "installed", "Managed entrypoints and runtime hashes match; execution is not yet verified.", version=record["version"])
        detected = bool(shutil.which(RECIPES[tool_id]["command"]))
        return _result(tool_id, "not-installed", "An existing command was detected but is not executed or managed." if detected else "Managed runtime is not installed.", command_detected=detected)
    except (OSError, ValueError, KeyError, TypeError, RuntimeBlocked):
        return _result(tool_id, "conflict", "Runtime files or manifest are modified or incomplete; preserve them and review before retrying.")


def _archive_name(value):
    if (not isinstance(value, str) or not value or "\\" in value or ":" in value
            or value.startswith("/") or any(ord(ch) < 32 for ch in value)
            or ".." in PurePosixPath(value).parts):
        raise RuntimeBlocked("Archive contains an unsafe path.")
    return value


def _extract_zip(archive, destination, allowed):
    """Preflight all entries. This recipe admits only the expected executable."""
    with zipfile.ZipFile(archive) as source:
        members = source.infolist()
        if not members or len(members) > MAX_MEMBERS or sum(item.file_size for item in members) > MAX_EXPANDED:
            raise RuntimeBlocked("Archive exceeds extraction limits.")
        seen = set()
        for item in members:
            name = _archive_name(item.filename)
            mode = item.external_attr >> 16
            kind = stat.S_IFMT(mode)
            if (name in seen or name.casefold() in {n.casefold() for n in seen}
                    or name not in allowed
                    or kind not in (0, stat.S_IFREG, stat.S_IFDIR) or item.flag_bits & 1
                    or (kind == stat.S_IFDIR and not item.is_dir())
                    or (item.is_dir() and kind == stat.S_IFREG)):
                raise RuntimeBlocked("Archive contains an unexpected, duplicate or linked entry.")
            seen.add(name)
            safe_path(destination, name)
        if seen != set(allowed):
            raise RuntimeBlocked("Archive does not contain the fixed recipe entrypoint.")
        for item in members:
            target = safe_path(destination, item.filename)
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(item) as incoming, target.open("xb") as outgoing:
                remaining = item.file_size
                while chunk := incoming.read(min(1024 * 1024, remaining + 1)):
                    remaining -= len(chunk)
                    if remaining < 0:
                        raise RuntimeBlocked("Archive member exceeds declared size.")
                    outgoing.write(chunk)
                if remaining:
                    raise RuntimeBlocked("Archive member is incomplete.")


def _native(root, tool_id, stage):
    if os.name != "nt" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise RuntimeBlocked("This native recipe currently supports Windows x64; use the official platform guide.")
    repo, asset_pattern, executable_pattern = NATIVE[tool_id]
    data = _metadata("https://api.github.com/repos/" + repo + "/releases/latest", GITHUB_HOSTS)
    if data.get("draft") is not False or data.get("prerelease") is not False:
        raise RuntimeBlocked("A stable publisher release is required.")
    version = _version(str(data.get("tag_name", "")).removeprefix("v"))
    name = asset_pattern.format(version=version)
    matches = [asset for asset in data.get("assets", []) if asset.get("name") == name]
    if len(matches) != 1:
        raise RuntimeBlocked("The official platform asset was not found.")
    asset = matches[0]
    digest = asset.get("digest", "")
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
        raise RuntimeBlocked("Publisher SHA-256 metadata is missing; automatic installation was deferred.")
    expected_url = "https://github.com/" + repo + "/releases/download/" + data["tag_name"] + "/" + name
    if asset.get("browser_download_url") != expected_url or not 0 < asset.get("size", 0) <= MAX_ARTIFACT:
        raise RuntimeBlocked("Publisher asset identity or size is invalid.")
    payload = _fetch(expected_url, GITHUB_HOSTS, MAX_ARTIFACT)
    if len(payload) != asset["size"] or hashlib.sha256(payload).hexdigest() != digest.split(":")[1]:
        raise RuntimeBlocked("Publisher artifact digest does not match.")
    archive = stage / "download.zip"
    archive.write_bytes(payload)
    executable = executable_pattern.format(version=version)
    if tool_id == "clawscan":
        directory = "clawscan_v" + version + "_windows_amd64/"
        _extract_zip(archive, stage, {directory, directory + executable, directory + "README.md"})
        (stage / directory / executable).rename(stage / executable)
        shutil.rmtree(stage / directory)
    else:
        _extract_zip(archive, stage, {executable})
    archive.unlink()
    return version, {"publisher": repo, "artifact": name, "sha256": digest[7:]}


def _python_executable():
    candidate = sys.executable if not getattr(sys, "frozen", False) else shutil.which("python")
    if not candidate:
        raise RuntimeBlocked("Python 3.11+ is required; use the official installation guide.")
    return candidate


def _normalize_package(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
        raise RuntimeBlocked("Python package identity is invalid.")
    return re.sub(r"[-_.]+", "-", value).lower()


def _wheel_identity(path):
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > MAX_MEMBERS or sum(item.file_size for item in members) > MAX_EXPANDED:
            raise RuntimeBlocked("Python wheel exceeds archive limits.")
        seen = set()
        for member in members:
            name = _archive_name(member.filename)
            kind = stat.S_IFMT(member.external_attr >> 16)
            if name.casefold() in seen or kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise RuntimeBlocked("Python wheel contains a duplicate or linked entry.")
            seen.add(name.casefold())
        metadata = [member for member in members if member.filename.endswith(".dist-info/METADATA")]
        if len(metadata) != 1 or metadata[0].file_size > MAX_METADATA:
            raise RuntimeBlocked("Python wheel metadata is invalid.")
        headers = BytesParser().parsebytes(archive.read(metadata[0]))
        return _normalize_package(headers.get("Name")), _version(headers.get("Version"))


def _verify_wheels(wheels, requested_package, requested_version):
    records, total = {}, 0
    artifacts = sorted(wheels.iterdir())
    if not artifacts or len(artifacts) > 150:
        raise RuntimeBlocked("The verified Python dependency set is incomplete or too large.")
    for wheel in artifacts:
        if wheel.suffix != ".whl" or not wheel.is_file():
            raise RuntimeBlocked("Only binary Python wheels can be installed automatically.")
        safe_path(wheels, wheel.name)
        total += wheel.stat().st_size
        if wheel.stat().st_size > MAX_ARTIFACT or total > MAX_EXPANDED:
            raise RuntimeBlocked("Python wheel downloads exceed limits.")
        name, version = _wheel_identity(wheel)
        if name in records:
            raise RuntimeBlocked("Duplicate Python package wheels were downloaded.")
        data = _metadata(f"https://pypi.org/pypi/{name}/{version}/json", PYPI_HOSTS)
        if (_normalize_package(data.get("info", {}).get("name")) != name
                or data.get("info", {}).get("version") != version):
            raise RuntimeBlocked("PyPI package identity differs from the wheel.")
        entries = [entry for entry in data.get("urls", []) if entry.get("filename") == wheel.name and not entry.get("yanked")]
        digest = _hash(wheel)
        if (len(entries) != 1 or entries[0].get("digests", {}).get("sha256") != digest
                or entries[0].get("packagetype") != "bdist_wheel"):
            raise RuntimeBlocked("Python wheel differs from its published PyPI SHA-256.")
        _validate_url(entries[0]["url"], PYPI_HOSTS)
        records[name] = {"version": version, "filename": wheel.name, "sha256": digest}
    if records.get(requested_package, {}).get("version") != requested_version:
        raise RuntimeBlocked("The requested pinned Python package is missing.")
    return records


def _python(root, tool_id, stage):
    package = PYTHON[tool_id][0]
    data = _metadata(f"https://pypi.org/pypi/{package}/json", PYPI_HOSTS)
    if _normalize_package(data.get("info", {}).get("name")) != package:
        raise RuntimeBlocked("PyPI returned another package.")
    version = _version(data.get("info", {}).get("version"))
    executable = _python_executable()
    # Copies avoid a symlink leaving the project; no downloaded source builds run.
    _quiet([executable, "-I", "-m", "venv", "--copies", str(stage / "venv")], stage)
    venv_python = stage / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    safe_path(stage, venv_python.relative_to(stage).as_posix())
    wheels = stage / "wheels"
    wheels.mkdir()
    _quiet([str(venv_python), "-I", "-m", "pip", "--isolated", "download", "--only-binary=:all:",
            "--index-url", "https://pypi.org/simple", "--no-cache-dir", "--dest", str(wheels), package + "==" + version],
           stage, bounded_directory=stage)
    records = _verify_wheels(wheels, package, version)
    requirements = stage / "requirements.txt"
    requirements.write_text("".join(f"{name}=={record['version']} --hash=sha256:{record['sha256']}\n"
                                    for name, record in sorted(records.items())), encoding="utf-8")
    _quiet([str(venv_python), "-I", "-m", "pip", "--isolated", "install", "--no-index", "--no-compile",
            "--find-links", str(wheels), "--require-hashes", "-r", str(requirements)], stage, bounded_directory=stage)
    # Keep the complete published wheel lock; downloaded wheels need not stay installed.
    save_json(stage / "wheels.lock.json", {"packages": records})
    shutil.rmtree(wheels)
    requirements.unlink()
    return version, {"publisher": "pypi.org", "package": package, "wheels": records}


def _lighthouse(root, stage):
    from configuration import npm_command
    node = shutil.which("node")
    if not node:
        raise RuntimeBlocked("Node.js 22.19+ is required for Lighthouse.")
    # Only this fixed prerequisite receives a bounded version check.
    with tempfile.TemporaryFile() as output:
        result = subprocess.run([node, "--version"], stdout=output, stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL, timeout=15, shell=False, env=_env(), **_background())
        output.seek(0)
        version_text = output.read(256).decode("ascii", errors="replace").strip()
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", version_text)
    if result.returncode or not match or tuple(map(int, match.groups())) < (22, 19, 0):
        raise RuntimeBlocked("Node.js 22.19+ is required for Lighthouse.")
    data = _metadata("https://registry.npmjs.org/lighthouse/latest", {"registry.npmjs.org"})
    version = _version(data.get("version"))
    integrity = data.get("dist", {}).get("integrity", "")
    if data.get("name") != "lighthouse" or not re.fullmatch(r"sha512-[A-Za-z0-9+/]+=*", integrity):
        raise RuntimeBlocked("Lighthouse npm identity or integrity is invalid.")
    _validate_url(data.get("dist", {}).get("tarball", ""), {"registry.npmjs.org"})
    save_json(stage / "package.json", {"name": "agent-toolkit-lighthouse", "private": True,
                                       "version": "1.0.0", "dependencies": {"lighthouse": version}})
    _quiet([*npm_command(), "install", "lighthouse@" + version, "--ignore-scripts", "--no-audit",
            "--no-fund", "--workspaces=false", "--registry=https://registry.npmjs.org", "--cache", str(stage / "npm-cache")],
           stage, bounded_directory=stage)
    lock = json.loads((stage / "package-lock.json").read_text())
    own = lock.get("packages", {}).get("node_modules/lighthouse", {})
    if own.get("version") != version or own.get("integrity") != integrity:
        raise RuntimeBlocked("Lighthouse npm artifact differs from publisher integrity.")
    for name, entry in lock.get("packages", {}).items():
        if not name:
            continue
        _validate_url(entry.get("resolved", ""), {"registry.npmjs.org"})
        if not re.fullmatch(r"sha(?:256|384|512)-[A-Za-z0-9+/]+=*", entry.get("integrity", "")):
            raise RuntimeBlocked("A Lighthouse dependency lacks publisher integrity.")
    # A copy gives managed commands a hash-checked interpreter without modifying PATH.
    shutil.copy2(node, stage / ("node.exe" if os.name == "nt" else "node"))
    # Cleanup must succeed; silently retaining a mutable npm cache would corrupt
    # ownership hashes, especially when deep Windows paths exceed MAX_PATH.
    if (stage / "npm-cache").exists():
        shutil.rmtree(_extended(stage / "npm-cache"))
    return version, {"publisher": "registry.npmjs.org", "package": "lighthouse", "integrity": integrity}


def install_runtime(root: Path, tool_id: str, log=print):
    """Install a selected fixed recipe. Failures preserve custom and partial state."""
    root = Path(root)
    if tool_id not in RECIPES:
        return _result(tool_id, "unsupported", "Unknown optional tool.")
    try:
        state = _read_state(root)
        if tool_id in state["tools"]:
            status = runtime_status(root, tool_id)
            log(RECIPES[tool_id]["label"] + ": " + status["status"])
            return status
        parent = safe_path(root, BASE)
        parent.mkdir(parents=True, exist_ok=True)
        # Partial/custom directories are not overwritten or silently upgraded.
        tool_parent = safe_path(root, BASE + "/" + tool_id)
        if tool_parent.exists():
            raise RuntimeBlocked("An unmanaged or partial runtime exists; preserve it and review before retrying.")
        with tempfile.TemporaryDirectory(prefix="stage-", dir=parent) as temporary:
            stage = Path(temporary)
            safe_path(root, stage.relative_to(root).as_posix())
            log(RECIPES[tool_id]["label"] + ": resolving verified publisher artifacts")
            if tool_id in NATIVE:
                version, source = _native(root, tool_id, stage)
            elif tool_id in PYTHON:
                version, source = _python(root, tool_id, stage)
            else:
                version, source = _lighthouse(root, stage)
            prefix = BASE + "/" + tool_id + "/" + version
            relative = _relative_command(tool_id, version, prefix)
            files = [part for part in relative if part.startswith(prefix + "/")]
            staged_hashes = {}
            for part in files:
                item = _extended(safe_path(stage, part.removeprefix(prefix + "/")))
                if not item.is_file():
                    raise RuntimeBlocked("The verified recipe entrypoint is missing.")
                staged_hashes[part] = _hash(item)
            tree = _tree_digest(stage)
            target = safe_path(root, prefix)
            if target.exists() or tool_parent.exists():
                raise RuntimeBlocked("Runtime activation conflicts with an existing directory.")
            tool_parent.mkdir()
            stage.rename(target)
            state["tools"][tool_id] = {"version": version, "directory": prefix, "command": relative,
                                      "hashes": staged_hashes, "tree_sha256": tree, "source": source}
            save_json(safe_path(root, STATE), state)
            # Recheck final paths before returning an installed verdict. Stage
            # hashes alone cannot establish successful relocation/activation.
            _entry(root, tool_id)
        log(RECIPES[tool_id]["label"] + ": installed with verified artifact hashes")
        return _result(tool_id, "installed", "Verified artifacts installed locally; scan readiness is not established.", version=version)
    except RuntimeBlocked as error:
        log(RECIPES[tool_id]["label"] + ": manual setup required")
        return _result(tool_id, "manual", str(error))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, zipfile.BadZipFile):
        log(RECIPES[tool_id]["label"] + ": installation did not complete")
        return _result(tool_id, "failed", "Installation did not complete. Existing files were preserved; consult the official guide.")


def probe_command(root: Path, tool_id: str):
    command = runtime_command(root, tool_id)
    if not command:
        return _result(tool_id, "not-installed", "No valid managed command is available; existing PATH commands are not executed.")
    flag = "--help" if tool_id == "graphify" else "--version"
    try:
        result = subprocess.run([*command, flag], cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, shell=False, timeout=30, env=_env(root, tool_id), **_background())
        return _result(tool_id, "verified" if result.returncode == 0 else "failed",
                       "The managed version/help command responded." if result.returncode == 0 else "The managed version/help check failed.")
    except subprocess.TimeoutExpired:
        return _result(tool_id, "timeout", "The managed version/help check exceeded its time limit.")
    except (OSError, ValueError, RuntimeBlocked):
        return _result(tool_id, "failed", "The managed version/help check could not start.")


def run_tool(root: Path, tool_id: str, args: list[str]):
    """Explicit user CLI invocation only; setup never calls this function."""
    if not isinstance(args, list) or any(not isinstance(arg, str) or "\0" in arg for arg in args):
        raise ValueError("Tool arguments must be a list of strings")
    command = runtime_command(root, tool_id)
    if not command:
        raise RuntimeBlocked("No verified managed command is available.")
    return subprocess.run([*command, *args], cwd=root, shell=False, env=_env(root, tool_id)).returncode


def docker_status():
    docker = shutil.which("docker")
    if not docker:
        return {"status": "missing", "command_detected": False, "message": "Install Docker using its official platform guide.", "docs": "https://docs.docker.com/get-started/get-docker/"}
    try:
        result = subprocess.run([docker, "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL, shell=False, timeout=20, env=_env(), **_background())
        return {"status": "verified" if result.returncode == 0 else "daemon-unavailable", "command_detected": True,
                "message": "Docker daemon responded." if result.returncode == 0 else "Docker is detected but its daemon is unavailable."}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "command_detected": True, "message": "Docker readiness check timed out."}
    except OSError:
        return {"status": "unavailable", "command_detected": True, "message": "Docker readiness check could not start."}


def strix_auth_status(root: Path):
    command = runtime_command(root, "strix")
    if not command:
        return _result("strix", "not-installed", "Install the managed Strix CLI before checking authentication.")
    try:
        result = subprocess.run([*command, "auth", "status"], cwd=root, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False, timeout=20,
                                env=_env(root, "strix"), **_background())
        return _result("strix", "session-detected" if result.returncode == 0 else "not-authenticated",
                       "Strix detected its saved sign-in; token validity and model execution are not verified." if result.returncode == 0 else "Strix did not report a saved sign-in.")
    except subprocess.TimeoutExpired:
        return _result("strix", "timeout", "Strix authentication status check timed out.")
    except (OSError, ValueError, RuntimeBlocked):
        return _result("strix", "unavailable", "Strix authentication status could not be checked.")


def start_strix_login(root: Path):
    """Caller must obtain explicit browser-login selection and manage cancellation."""
    command = runtime_command(root, "strix")
    if not command:
        raise RuntimeBlocked("Install a verified managed Strix CLI before login.")
    return subprocess.Popen([*command, "auth", "login", "chatgpt"], cwd=root, shell=False,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            env=_env(root, "strix"), **_background())
