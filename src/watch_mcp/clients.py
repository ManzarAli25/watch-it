"""Detect and register Watch with MCP clients (Claude Code, Cursor, Codex)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SERVER_NAME = "watch-it"


def server_command() -> tuple[str, list[str]]:
    """The command an MCP client should run to start the server.

    Prefers the installed `watch-mcp` console script (on PATH after pipx/uv/pip);
    falls back to the current interpreter running the module.
    """
    exe = shutil.which("watch-mcp")
    if exe:
        return exe, ["serve"]
    return sys.executable, ["-m", "watch_mcp.cli", "serve"]


@dataclass
class ClientStatus:
    name: str
    installed: bool
    registered: bool
    detail: str = ""


# --- Claude Code (via its CLI) ---------------------------------------------

def _claude_registered() -> bool:
    exe = shutil.which("claude")
    if not exe:
        return False
    try:
        out = subprocess.run([exe, "mcp", "list"], capture_output=True, text=True, timeout=20)
        return SERVER_NAME in (out.stdout + out.stderr)
    except Exception:
        return False


def register_claude() -> ClientStatus:
    exe = shutil.which("claude")
    if not exe:
        return ClientStatus("Claude Code", False, False, "claude CLI not found")
    cmd, args = server_command()
    try:
        subprocess.run(
            [exe, "mcp", "add", SERVER_NAME, "--", cmd, *args],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return ClientStatus("Claude Code", True, True, "registered")
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or e.stdout or "").strip()
        if "already exists" in msg.lower():
            return ClientStatus("Claude Code", True, True, "already registered")
        return ClientStatus("Claude Code", True, False, f"error: {msg[:120]}")
    except Exception as e:  # noqa: BLE001
        return ClientStatus("Claude Code", True, False, f"error: {e}")


# --- Cursor (~/.cursor/mcp.json) -------------------------------------------

def _cursor_path() -> Path:
    return Path.home() / ".cursor" / "mcp.json"


def register_cursor() -> ClientStatus:
    path = _cursor_path()
    installed = path.parent.exists()
    cmd, args = server_command()
    data = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return ClientStatus("Cursor", installed, False, "mcp.json is not valid JSON")
    servers = data.setdefault("mcpServers", {})
    servers[SERVER_NAME] = {"command": cmd, "args": args}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return ClientStatus("Cursor", True, True, f"written to {path}")


# --- Codex (~/.codex/config.toml) ------------------------------------------

def _codex_path() -> Path:
    return Path.home() / ".codex" / "config.toml"


def register_codex() -> ClientStatus:
    import tomli_w

    path = _codex_path()
    installed = path.parent.exists()
    cmd, args = server_command()
    data = {}
    if path.is_file():
        import tomllib
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError:
            return ClientStatus("Codex", installed, False, "config.toml is not valid TOML")
    data.setdefault("mcp_servers", {})[SERVER_NAME] = {"command": cmd, "args": args}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomli_w.dumps(data), encoding="utf-8")
    return ClientStatus("Codex", True, True, f"written to {path}")


def detect() -> list[ClientStatus]:
    """Report which clients are present and whether Watch is registered."""
    out: list[ClientStatus] = []

    out.append(ClientStatus(
        "Claude Code", shutil.which("claude") is not None, _claude_registered()))

    cur = _cursor_path()
    cur_reg = cur.is_file() and SERVER_NAME in cur.read_text(encoding="utf-8")
    out.append(ClientStatus("Cursor", cur.parent.exists(), bool(cur_reg)))

    cod = _codex_path()
    cod_reg = cod.is_file() and SERVER_NAME in cod.read_text(encoding="utf-8")
    out.append(ClientStatus("Codex", cod.parent.exists(), bool(cod_reg)))

    return out


def register_all(only_detected: bool = True) -> list[ClientStatus]:
    """Register with every client (or only those detected as installed)."""
    present = {c.name: c.installed for c in detect()}
    results: list[ClientStatus] = []
    for name, fn in (("Claude Code", register_claude), ("Cursor", register_cursor),
                     ("Codex", register_codex)):
        if only_detected and not present.get(name):
            results.append(ClientStatus(name, False, False, "not installed — skipped"))
            continue
        results.append(fn())
    return results
