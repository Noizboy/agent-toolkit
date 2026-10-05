"""Bounded MCP initialize/tools-list probes. Never call tests, scans or domain tools."""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import re
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


def initialized_result(message):
    if (not isinstance(message, dict) or not isinstance(message.get('result'), dict) or
            not isinstance(message['result'].get('protocolVersion'), str) or
            not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', message['result']['protocolVersion'])):
        raise ValueError('Invalid MCP initialization response')
    return message['result']


def tools_count(message):
    result = message.get('result') if isinstance(message, dict) else None
    tools = result.get('tools') if isinstance(result, dict) else None
    if (not isinstance(tools, list) or len(tools) > 2000 or
            any(not isinstance(tool, dict) or not isinstance(tool.get('name'), str) or
                not tool['name'] or len(tool['name']) > 256 for tool in tools)):
        raise ValueError('Invalid MCP tools response')
    return len(tools)
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
    class NoRedirects(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise ValueError("MCP redirects are not permitted during authenticated probes")
    opener = urllib.request.build_opener(NoRedirects())
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
        with opener.open(request, timeout=20) as response:
            session = response.headers.get("Mcp-Session-Id")
            if session:
                headers["Mcp-Session-Id"] = session
            body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise ValueError("MCP response exceeds the probe limit")
            return decoded(body) if body else {}
    initialized = send(INIT)
    headers["MCP-Protocol-Version"] = initialized_result(initialized)['protocolVersion']
    send(READY)
    response = send(LIST)
    return {"status": "verified", "tool_count": tools_count(response),
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
    messages = queue.Queue(maxsize=200)
    def reader():
        while True:
            line = child.stdout.readline(2_000_001)
            if not line or len(line) > 2_000_000:
                break
            try:
                messages.put_nowait(json.loads(line))
            except json.JSONDecodeError:
                pass
            except queue.Full:
                break
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
                if isinstance(message, dict) and message.get("id") == identifier:
                    return message
            except queue.Empty:
                break
        raise TimeoutError("MCP response timeout")
    try:
        send(INIT)
        initialized_result(receive(1))
        send(READY)
        send(LIST)
        response = receive(2)
        return {"status": "verified", "tool_count": tools_count(response),
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
        if name not in {'context7', 'testsprite'}:
            results[name] = {'status': 'custom-config-not-probed'}
            continue
        if name in {'context7', 'testsprite'}:
            fixed = {'context7': {'transport': 'http', 'url': 'https://mcp.context7.com/mcp', 'credential_env': 'CONTEXT7_API_KEY'},
                     'testsprite': {'transport': 'stdio', 'package': '@testsprite/testsprite-mcp',
                                   'credential_env': 'TESTSPRITE_API_KEY', 'server_env': 'API_KEY'}}
            declared = dict(tool['mcp'])
            declared.pop('version', None)
            if declared != fixed[name]:
                results[name] = {'status': 'custom-config-not-probed'}
                continue
        config = configured.get(name, {})
        if not config.get("enabled", True):
            results[name] = {"status": "disabled"}
            continue
        # Probe only the declared managed endpoint/runtime, never arbitrary customized commands.
        if tool["mcp"]["transport"] == "http" and config.get("url") != tool["mcp"]["url"]:
            results[name] = {"status": "custom-config-not-probed"}
            continue
        if name == 'context7' and provider == 'codex':
            if (config.get('bearer_token_env_var') not in (None, 'CONTEXT7_API_KEY') or
                    config.get('env_http_headers', {}) not in ({}, {'CONTEXT7_API_KEY': 'CONTEXT7_API_KEY'}) or
                    config.get('http_headers')):
                results[name] = {'status': 'custom-config-not-probed'}
                continue
        if tool["mcp"]["transport"] == "stdio":
            npm = state.get('tools', {}).get(name, {}).get('npm', {})
            version = npm.get('version', '')
            expected = npm.get('entrypoint')
            if (npm.get('package') != '@testsprite/testsprite-mcp' or not isinstance(version, str) or
                    not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?', version) or
                    expected != '.agent-toolkit/runtime/testsprite/' + version + '/node_modules/@testsprite/testsprite-mcp/dist/index.js'):
                results[name] = {'status': 'custom-config-not-probed'}
                continue
            args = config.get("command", []) if provider == "opencode" else config.get("args", [])
            node = shutil.which('node') or 'node'
            matching = (config.get('command') == 'python' and args == [str(root / '.agent-toolkit/mcp_launch.py'), name] if provider == 'codex' else
                        args == [str(safe_path(root, expected))] and config.get('command') in {'node', node} if provider == 'claude' else
                        args in (['node', str(safe_path(root, expected))], [node, str(safe_path(root, expected))]))
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
