"""Detect and register Watch with MCP clients (Claude Code, Cursor, Codex)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path

SERVER_NAME = "watch-it"


def _console_script() -> str | None:
    """Locate the installed `watch-mcp` executable, on PATH or in a script dir.

    `shutil.which` alone misses installs whose bin dir isn't on the current
    PATH yet (uv tool ``~/.local/bin``, pip ``--user`` scripts, a venv that
    isn't active). Probing those dirs avoids registering a command that only
    works in the shell that happened to run setup.
    """
    exe = shutil.which("watch-mcp")
    if exe:
        return exe
    names = ["watch-mcp.exe", "watch-mcp"] if os.name == "nt" else ["watch-mcp"]
    dirs: list[Path] = [Path(sys.executable).parent]  # this venv's Scripts/bin
    for scheme in (sysconfig.get_default_scheme(), "nt_user", "posix_user"):
        try:
            dirs.append(Path(sysconfig.get_path("scripts", scheme)))
        except (KeyError, ValueError):
            pass
    dirs.append(Path.home() / ".local" / "bin")  # uv tool / pipx default
    for d in dirs:
        for n in names:
            cand = d / n
            if cand.is_file():
                return str(cand)
    return None


def _can_import(python: str) -> bool:
    """Whether `python` can actually import the package (persistently)."""
    try:
        r = subprocess.run(
            [python, "-c", "import watch_mcp"], capture_output=True, timeout=15)
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def server_command() -> tuple[str, list[str]]:
    """The command an MCP client should run to start the server.

    Prefers the installed `watch-mcp` console script (on PATH or in a known
    script dir after pipx/uv/pip). Falls back to the current interpreter running
    the module only if that interpreter can persistently import the package —
    otherwise we would register a command that fails to launch (e.g. when setup
    runs under an ephemeral `uvx`/`uv run` interpreter). Raises when no working
    command exists so callers surface an error instead of writing a broken entry.
    """
    exe = _console_script()
    if exe:
        return exe, ["serve"]
    if _can_import(sys.executable):
        return sys.executable, ["-m", "watch_mcp.cli", "serve"]
    raise RuntimeError(
        "Cannot find a persistent 'watch-mcp' command to register. Install Watch "
        "with 'uv tool install watch-mcp' or 'pipx install watch-mcp', then re-run "
        "'watch-mcp setup'."
    )


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
    try:
        cmd, args = server_command()
    except RuntimeError as e:
        return ClientStatus("Claude Code", True, False, str(e))
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
    try:
        cmd, args = server_command()
    except RuntimeError as e:
        return ClientStatus("Cursor", installed, False, str(e))
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
    try:
        cmd, args = server_command()
    except RuntimeError as e:
        return ClientStatus("Codex", installed, False, str(e))
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
