"""Bounded MCP initialize/tools-list probes. Never call tests, scans or domain tools."""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time
import urllib.request

from configuration import toml_data
from sources import mcp_environment, read_json, safe_path

INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
    "protocolVersion": "2025-03-26", "capabilities": {},
    "clientInfo": {"name": "project-agent-toolkit", "version": "1.0.0"}}}
LIST = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
READY = {"jsonrpc": "2.0", "method": "notifications/initialized"}


def decoded(body: bytes) -> dict:
    text = body.decode("utf-8")
    if text.lstrip().startswith("{"):
        return json.loads(text)
    for line in text.splitlines():
        if line.startswith("data:"):
            data = json.loads(line[5:].strip())
            if "id" in data:
                return data
    raise ValueError("No MCP JSON-RPC response")


def probe_http(config: dict) -> dict:
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    credential = config.get("bearer_token_env_var")
    if credential:
        if not os.environ.get(credential):
            return {"status": "credentials-missing"}
        headers["Authorization"] = "Bearer " + os.environ[credential]
    for header, variable in config.get("env_http_headers", {}).items():
        if not os.environ.get(variable):
            return {"status": "credentials-missing"}
        headers[header] = os.environ[variable]
    def send(message):
        request = urllib.request.Request(config["url"], data=json.dumps(message).encode(), headers=headers)
        with urllib.request.urlopen(request, timeout=20) as response:
            session = response.headers.get("Mcp-Session-Id")
            if session:
                headers["Mcp-Session-Id"] = session
            body = response.read(2_000_000)
            return decoded(body) if body else {}
    initialized = send(INIT)
    if "result" not in initialized:
        return {"status": "initialization-failed"}
    headers["MCP-Protocol-Version"] = initialized["result"].get("protocolVersion", "2025-03-26")
    send(READY)
    response = send(LIST)
    if "result" not in response:
        return {"status": "tools-list-failed"}
    return {"status": "verified", "tool_count": len(response["result"].get("tools", [])),
            "check": "initialize-and-tools-list-only"}


def probe_stdio(root: Path, tool: dict, record: dict) -> dict:
    npm = record.get("npm", {})
    node = shutil.which("node")
    if not npm.get("entrypoint") or not node:
        return {"status": "runtime-missing"}
    entry = safe_path(root, npm["entrypoint"])
    try:
        env = mcp_environment(tool["mcp"])
    except RuntimeError:
        return {"status": "credentials-missing"}
    child = subprocess.Popen([node, str(entry)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, cwd=root, env=env, text=True, encoding="utf-8")
    messages = queue.Queue()
    def reader():
        for line in child.stdout:
            try:
                messages.put(json.loads(line))
            except json.JSONDecodeError:
                pass
    worker = threading.Thread(target=reader, daemon=True)
    worker.start()
    def send(message):
        child.stdin.write(json.dumps(message) + "\n")
        child.stdin.flush()
    def receive(identifier):
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            try:
                message = messages.get(timeout=max(0.01, deadline - time.monotonic()))
                if message.get("id") == identifier:
                    return message
            except queue.Empty:
                break
        raise TimeoutError("MCP response timeout")
    try:
        send(INIT)
        if "result" not in receive(1):
            return {"status": "initialization-failed"}
        send(READY)
        send(LIST)
        response = receive(2)
        if "result" not in response:
            return {"status": "tools-list-failed"}
        return {"status": "verified", "tool_count": len(response["result"].get("tools", [])),
                "check": "initialize-and-tools-list-only"}
    finally:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
        for stream in [child.stdin, child.stdout]:
            stream.close()
        worker.join(timeout=1)


def probe_mcps(root: Path, tools: list[dict], state: dict) -> dict:
    provider = read_json(safe_path(root, ".agent-toolkit/project.json"), {}).get("provider")
    if provider == "codex":
        configured = toml_data(safe_path(root, ".codex/config.toml")).get("mcp_servers", {})
    elif provider == "claude":
        configured = read_json(safe_path(root, ".mcp.json"), {}).get("mcpServers", {})
    elif provider == "opencode":
        configured = read_json(safe_path(root, "opencode.json"), {}).get("mcp", {})
    else:
        return {tool["id"]: {"status": "provider-not-selected"} for tool in tools if "mcp" in tool}
    results = {}
    for tool in tools:
        if "mcp" not in tool or tool.get("enabled", True) is False:
            continue
        name = tool["id"]
        config = configured.get(name, {})
        if not config.get("enabled", True):
            results[name] = {"status": "disabled"}
            continue
        # Probe only the declared managed endpoint/runtime, never arbitrary customized commands.
        if tool["mcp"]["transport"] == "http" and config.get("url") != tool["mcp"]["url"]:
            results[name] = {"status": "custom-config-not-probed"}
            continue
        if tool["mcp"]["transport"] == "stdio":
            expected = state["tools"].get(name, {}).get("npm", {}).get("entrypoint")
            args = config.get("command", []) if provider == "opencode" else config.get("args", [])
            matching = ("mcp_launch.py" in " ".join(args) if provider == "codex" else
                        expected and str(safe_path(root, expected)) in args)
            if not matching:
                results[name] = {"status": "custom-config-not-probed"}
                continue
        if provider != "codex" and tool["mcp"]["transport"] == "http":
            variable = tool["mcp"].get("credential_env")
            config = {"url": tool["mcp"]["url"]}
            if variable:
                if name == "context7":
                    config["env_http_headers"] = {"CONTEXT7_API_KEY": variable}
                else:
                    config["bearer_token_env_var"] = variable
        try:
            results[name] = probe_http(config) if tool["mcp"]["transport"] == "http" else probe_stdio(
                root, tool, state["tools"].get(name, {}))
        except (OSError, ValueError, TimeoutError):
            results[name] = {"status": "probe-failed", "detail": "Check network, credentials and server prerequisites; secret-bearing output suppressed."}
    return results
