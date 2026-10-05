#!/usr/bin/env python3
"""Start a pinned project MCP runtime, mapping credential names without storing values."""
from pathlib import Path
import shutil
import subprocess
import sys

from sources import mcp_environment, read_json, safe_path


def launch(tool_id: str) -> int:
    root = Path(__file__).resolve().parents[1]
    toolkit = root / ".agent-toolkit"
    tools = read_json(toolkit / "registry.json", {})["tools"]
    tool = next(item for item in tools if item["id"] == tool_id)
    runtime = read_json(toolkit / "tools.lock.json", {})["tools"][tool_id]["npm"]
    entry = safe_path(root, runtime["entrypoint"])
    node = shutil.which("node")
    if not node or not entry.is_file():
        raise RuntimeError("Run toolkit bootstrap to install this MCP runtime")
    env = mcp_environment(tool["mcp"])
    # stdout is reserved for the server's MCP protocol.
    child = subprocess.Popen([node, str(entry)], cwd=root, env=env)
    try:
        return child.wait()
    except KeyboardInterrupt:
        child.terminate()
        return child.wait()


if __name__ == "__main__":
    try:
        sys.exit(launch(sys.argv[1]))
    except (KeyError, StopIteration, IndexError, RuntimeError, ValueError) as error:
        print(f"MCP launcher: {error}", file=sys.stderr)
        sys.exit(1)
