"""Non-secret setup preferences and explicit, masked credential handling."""
from __future__ import annotations

import os
from pathlib import Path
import re
import sys

from sources import read_json, safe_path, save_json

CREDENTIALS = {"CONTEXT7_API_KEY", "TESTSPRITE_API_KEY", "LLM_API_KEY"}
MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.:/-]{0,160}\Z")


def strix_settings(root: Path) -> dict:
    settings = read_json(safe_path(root, ".agent-toolkit/runtime/optional/settings.json"), {})
    if not isinstance(settings, dict):
        raise ValueError("Invalid Strix preferences")
    if ('auth_mode' in settings and not isinstance(settings['auth_mode'], str)) or ('model' in settings and not isinstance(settings['model'], str)):
        raise ValueError("Invalid Strix preferences")
    if settings.get('auth_mode') == 'later':
        return {'auth_mode': 'later', 'model': ''}
    model = settings.get("model") or os.environ.get("STRIX_LLM", "")
    if not isinstance(model, str):
        raise ValueError("Invalid Strix preferences")
    mode = settings.get("auth_mode") or ("chatgpt" if model.startswith("chatgpt/") else "api" if model else "later")
    if not isinstance(mode, str) or mode not in {"later", "api", "chatgpt"} or (model and not MODEL.fullmatch(model)):
        raise ValueError("Invalid Strix preferences")
    if mode == "chatgpt" and not model.startswith("chatgpt/"):
        raise ValueError("ChatGPT authentication requires a chatgpt/model ID")
    if mode == "api" and model.startswith("chatgpt/"):
        raise ValueError("Choose ChatGPT authentication for this model")
    return {"auth_mode": mode, "model": model}


def save_strix_settings(root: Path, mode: str, model: str) -> None:
    if not isinstance(model, str) or not isinstance(mode, str):
        raise ValueError("Invalid Strix preferences")
    model = model.strip()
    if mode not in {"later", "api", "chatgpt"}:
        raise ValueError("Choose an authentication method")
    if mode != "later" and not MODEL.fullmatch(model):
        raise ValueError("Enter a provider/model ID")
    if mode == "chatgpt" and not model.startswith("chatgpt/"):
        raise ValueError("ChatGPT authentication requires a chatgpt/model ID")
    if mode == "api" and model.startswith("chatgpt/"):
        raise ValueError("Choose ChatGPT authentication for this model")
    save_json(safe_path(root, ".agent-toolkit/runtime/optional/settings.json"),
              {"auth_mode": mode, "model": model if mode != "later" else ""})


def set_credential(name: str, value: str, *, persist: bool = False) -> str:
    """No project secret files. Persistence is a separate, explicit Windows opt-in."""
    if name not in CREDENTIALS or not isinstance(value, str) or not value or len(value) > 8192 or any(c in value for c in "\x00\r\n"):
        raise ValueError("Invalid credential entry")
    if persist:
        if sys.platform != "win32":
            raise ValueError("Persistent configuration is manual on this platform")
        import winreg
        # An existing, different value is never overwritten by setup.
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, "Environment", 0,
                                winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as key:
            try:
                previous, _ = winreg.QueryValueEx(key, name)
            except FileNotFoundError:
                previous = None
            if previous is not None and previous != value:
                raise ValueError("Existing user credential differs; update it manually")
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        # Notify the shell without exposing values; already-running clients must reload.
        try:
            import ctypes
            result = ctypes.c_ulong()
            ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 2, 2000, ctypes.byref(result))
        except (AttributeError, OSError):
            pass  # The value was saved; restarting the client remains required.
    os.environ[name] = value
    return "user-environment-saved; restart client" if persist else "session-only; configure future client environment separately"
