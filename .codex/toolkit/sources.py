"""Bounded source downloads and project-local copies. Never execute upstream code."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile


def safe_path(root: Path, relative: str) -> Path:
    """Validate even nonexistent destinations and Windows paths on any platform."""
    parts = PurePosixPath(relative).parts
    if not parts or "\\" in relative or ":" in relative or relative.startswith("/") or ".." in parts:
        raise ValueError("Unsafe relative path")
    base = root.resolve()
    current = root
    for part in parts:
        current = current / part
        reparse = current.exists() and bool(getattr(current.lstat(), "st_file_attributes", 0)
                                           & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
        if current.is_symlink() or reparse:
            raise ValueError("Links are not allowed in managed paths")
    if not current.resolve().is_relative_to(base):
        raise ValueError("Path escapes managed root")
    return current


def validate_tool(tool: dict) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", tool.get("id", "")):
        raise ValueError("Invalid tool id")
    if "repo" in tool and not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", tool["repo"]):
        raise ValueError("Sources must be GitHub owner/repo names")
    if "ref" in tool and (not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_./+-]*", tool["ref"]) or ".." in tool["ref"]):
        raise ValueError("Invalid Git ref")
    for pattern in tool.get("skills", []):
        safe_path(Path.cwd(), pattern)
    for payload in tool.get("payloads", []):
        validate_tool({"id": payload["name"]})
        for source, dest in payload["files"].items():
            safe_path(Path.cwd(), source)
            safe_path(Path.cwd(), dest)
    if "adapter" in tool:
        validate_tool({"id": tool["adapter"]})
    mcp = tool.get("mcp", {})
    if mcp.get("transport") == "http" and not mcp.get("url", "").startswith("https://"):
        raise ValueError("MCP HTTP endpoints must use HTTPS")
    if "package" in mcp and not re.fullmatch(r"(?:@[a-z0-9_.-]+/)?[a-z0-9_.-]+", mcp["package"]):
        raise ValueError("Invalid npm package")
    if "version" in mcp and not re.fullmatch(r"\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?", mcp["version"]):
        raise ValueError("npm versions must be exact")
    for value in [*tool.get("credential_envs", []), mcp.get("credential_env"), mcp.get("server_env")]:
        if value and not re.fullmatch(r"[A-Z][A-Z0-9_]*", value):
            raise ValueError("Invalid credential environment variable name")


def atomic_text(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8-sig") == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as out:
        out.write(content)
        temporary = Path(out.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path: Path, default: dict) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default


def save_json(path: Path, data: dict) -> None:
    atomic_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def mcp_environment(mcp: dict) -> dict[str, str]:
    """Give third-party MCP runtimes OS basics and only their declared credential."""
    allowed = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "HOME", "USERPROFILE",
               "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE"}
    env = {name: value for name, value in os.environ.items() if name.upper() in allowed}
    credential = mcp.get("credential_env")
    if credential:
        value = os.environ.get(credential)
        if not value:
            raise RuntimeError(f"Required environment variable is missing: {credential}")
        env[mcp.get("server_env", credential)] = value
    return env


def tree_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for entry in sorted(path.rglob("*")):
        safe_path(path, entry.relative_to(path).as_posix())
        if entry.is_file() and "__pycache__" not in entry.parts:
            digest.update(entry.relative_to(path).as_posix().encode())
            digest.update(b"\0")
            digest.update(entry.read_bytes())
    return digest.hexdigest()


def git(*args: str, cwd: Path | None = None) -> str:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1"}
    # Prevent global hooks, autocrlf and configured checkout filters from changing sources.
    with tempfile.TemporaryDirectory(prefix="agent-git-") as home:
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        result = subprocess.run(["git", "-c", f"core.hooksPath={home}", "-c", "core.autocrlf=false",
                                 "-c", "core.symlinks=false", *args], cwd=cwd, env=env,
                                capture_output=True, text=True, timeout=240)
    if result.returncode:
        raise RuntimeError("Git source operation failed; check source/ref and network access")
    return result.stdout.strip()


def checkout(tool: dict, vendor: Path, previous: dict, update: bool) -> tuple[Path, str]:
    validate_tool(tool)
    url = f"https://github.com/{tool['repo']}.git"
    fingerprint = f"{tool['repo']}@{tool.get('ref', 'HEAD')}"
    commit = previous.get("commit") if previous.get("source") == fingerprint and not update else None
    if not commit:
        ref = tool.get("ref", "HEAD")
        if re.fullmatch(r"[a-f0-9]{40}", ref):
            commit = ref
        else:
            answer = git("ls-remote", url, ref, "refs/heads/" + ref, "refs/tags/" + ref, "refs/tags/" + ref + "^{}")
            if not answer:
                raise RuntimeError("Upstream ref was not found")
            lines = answer.splitlines()
            # Annotated tags have a tag-object id and a peeled commit id; lock the commit.
            selected = next((line for line in lines if line.endswith("^{}")), lines[0])
            commit = selected.split()[0]
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Expected a full git commit")
    parent = safe_path(vendor, tool["id"])
    parent.mkdir(parents=True, exist_ok=True)
    target = safe_path(parent, commit)
    if target.exists():
        if not (target / ".git").is_dir() or git("rev-parse", "HEAD", cwd=target) != commit:
            raise RuntimeError("Invalid cached source checkout")
        if git("status", "--porcelain", cwd=target):
            raise RuntimeError("Cached source has local modifications; preserve it and remove it manually if unwanted")
        return target, commit
    with tempfile.TemporaryDirectory(dir=parent, prefix="download-") as temporary:
        work = Path(temporary)
        git("init", cwd=work)
        git("remote", "add", "origin", url, cwd=work)
        git("fetch", "--depth", "1", "origin", commit, cwd=work)
        # Reject Git symlinks even on Windows where checkout may materialize link text.
        entries = git("ls-tree", "-r", "FETCH_HEAD", cwd=work)
        if any(line.startswith("120000 ") for line in entries.splitlines()):
            # Some upstream repos contain unrelated links; selected skill trees are checked below.
            safe_links = [line.split("\t", 1)[1] for line in entries.splitlines() if line.startswith("120000 ")]
        else:
            safe_links = []
        git("checkout", "--detach", "FETCH_HEAD", cwd=work)
        os.replace(work, target)
    # Sidecar outside checkout avoids dirtying pinned upstream sources.
    save_json(parent / f"{commit}.links.json", {"links": safe_links})
    return target, commit


def skill_payloads(tool: dict, source: Path, staging: Path) -> list[Path]:
    """Expand only declared directories, never import contributor/test skills by accident."""
    links_file = source.parent / f"{source.name}.links.json"
    links = read_json(links_file, {"links": []})["links"]
    result = []
    for pattern in tool.get("skills", []):
        matches = sorted(source.glob(pattern))
        if not matches:
            raise RuntimeError(f"No skill found at declared path: {pattern}")
        for folder in matches:
            relative = folder.relative_to(source).as_posix()
            safe_path(source, relative)
            if not (folder / "SKILL.md").is_file():
                raise RuntimeError(f"Missing SKILL.md: {relative}")
            if any(link == relative or link.startswith(relative + "/") for link in links):
                raise ValueError("Upstream skill contains a symlink")
            tree_hash(folder)
            dest = safe_path(staging, folder.name)
            shutil.copytree(folder, dest)
            result.append(dest)
    for payload in tool.get("payloads", []):
        dest = safe_path(staging, payload["name"])
        dest.mkdir()
        for original, relative in payload["files"].items():
            if any(link == original or link.startswith(original + "/") for link in links):
                raise ValueError("Upstream payload contains a symlink")
            entry = safe_path(source, original)
            output = safe_path(dest, relative)
            output.parent.mkdir(parents=True, exist_ok=True)
            if entry.is_dir():
                tree_hash(entry)
                shutil.copytree(entry, output)
            else:
                shutil.copy2(entry, output)
        if not (dest / "SKILL.md").is_file():
            raise ValueError("Payload lacks SKILL.md")
        result.append(dest)
    return result


def install_skill(payload: Path, skills: Path, previous: dict) -> dict:
    validate_tool({"id": payload.name})
    dest = safe_path(skills, payload.name)
    incoming = tree_hash(payload)
    current = tree_hash(dest) if dest.exists() else None
    if current is not None and current != incoming:
        if not previous.get("hash"):
            return {"status": "preserved-unmanaged", "name": payload.name}
        if current != previous["hash"]:
            return {**previous, "status": "conflict-local-changes", "name": payload.name}
    if current != incoming:
        skills.mkdir(parents=True, exist_ok=True)
        # Stage a complete copy first; rollback on failure preserves the previous skill.
        with tempfile.TemporaryDirectory(dir=skills, prefix=".install-") as tmp:
            stage = Path(tmp) / "new"
            backup = Path(tmp) / "old"
            shutil.copytree(payload, stage)
            if dest.exists():
                os.replace(dest, backup)
            try:
                os.replace(stage, dest)
            except OSError:
                if backup.exists():
                    os.replace(backup, dest)
                raise
    return {"name": payload.name, "hash": incoming, "status": "installed"}
