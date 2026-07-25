"""Best-effort update check: tell the user when a newer version exists.

Fetches the latest version from PyPI (falls back to the GitHub repo's pyproject),
caches the answer for a day, and fails silently when offline. Never called from
`serve` — the MCP stdio channel must stay clean.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import platformdirs

from . import __version__

_CACHE = Path(platformdirs.user_cache_dir("watch-mcp")) / "update-check.json"
_TTL = 86400  # re-check at most once a day
_TIMEOUT = 2.5
_PYPI = "https://pypi.org/pypi/watch-mcp/json"
_GH_PYPROJECT = "https://raw.githubusercontent.com/ManzarAli25/watch-it/main/pyproject.toml"

UPGRADE_HINT = "uv tool upgrade watch-mcp   (or: pipx upgrade watch-mcp)"


def _parse(v: str) -> tuple:
    parts = re.findall(r"\d+", v)
    return tuple(int(p) for p in parts) or (0,)


def _is_newer(latest: str, current: str) -> bool:
    return _parse(latest) > _parse(current)


def _fetch_latest() -> str | None:
    import httpx

    try:
        r = httpx.get(_PYPI, timeout=_TIMEOUT)
        if r.status_code == 200:
            return r.json()["info"]["version"]
    except Exception:  # noqa: BLE001
        pass
    try:
        r = httpx.get(_GH_PYPROJECT, timeout=_TIMEOUT)
        if r.status_code == 200:
            m = re.search(r'^\s*version\s*=\s*"([^"]+)"', r.text, re.MULTILINE)
            if m:
                return m.group(1)
    except Exception:  # noqa: BLE001
        pass
    return None


def _cached_latest() -> str | None:
    now = time.time()
    if _CACHE.is_file():
        try:
            data = json.loads(_CACHE.read_text())
            if now - data.get("checked_at", 0) < _TTL:
                return data.get("latest")
        except Exception:  # noqa: BLE001
            pass
    latest = _fetch_latest()
    try:
        _CACHE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE.write_text(json.dumps({"checked_at": now, "latest": latest}))
    except Exception:  # noqa: BLE001
        pass
    return latest


def check() -> str | None:
    """Return a one-line notice if a newer version exists, else None."""
    try:
        latest = _cached_latest()
    except Exception:  # noqa: BLE001
        return None
    if latest and _is_newer(latest, __version__):
        return f"Update available: {__version__} -> {latest}. Run: {UPGRADE_HINT}"
    return None
