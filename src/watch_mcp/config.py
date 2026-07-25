"""Runtime configuration, loaded from environment / config file / .env."""

from __future__ import annotations

from pathlib import Path

import platformdirs
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor .env to the project root, not the client's cwd. MCP clients (Claude Code,
# Cursor, Codex) spawn the server from *their* working directory, so a relative
# "./.env" would never be found and settings would silently fall back to stub.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: Per-user config file written by `watch-mcp setup` / the UI. Works no matter
#: which directory an MCP client launches the server from.
CONFIG_FILE = Path(platformdirs.user_config_dir("watch-mcp")) / "config.env"


class Settings(BaseSettings):
    # Priority (low to high): user config file, then project .env, then real env
    # vars. Later files override earlier ones in pydantic-settings.
    model_config = SettingsConfigDict(
        env_prefix="WATCH_",
        env_file=(CONFIG_FILE, _PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # VLM backend (OpenAI-compatible vision endpoint)
    vlm_base_url: str = "http://localhost:8000/v1"
    vlm_model: str = "stub"
    full_model: str = ""  # video-capable model for mode='full'; falls back to vlm_model.
    vlm_api_key: str = ""
    vlm_timeout: float = 120.0
    vlm_max_tokens: int = 4096

    # Sampling / cost controls
    max_frames: int = 32
    frame_max_edge: int = 768
    scene_threshold: float = 27.0
    fallback_interval: float = 5.0
    max_duration: float = 1800.0  # reject inputs longer than this (seconds); 0 disables.

    # get_frames (Claude's own eyes)
    get_frames_max: int = 8  # hard cap on frames returned per call, protects context.

    # Video cache (content-addressed; backs video_id / get_frames)
    cache_ttl: float = 3600.0  # evict cache entries older than this (seconds); 0 disables.
    cache_max_bytes: int = 2 * 1024**3  # hard size cap for copied downloads (LRU evict).

    # Misc
    temp_dir: str = ""
    ocr: bool = False  # Phase 2 hook; unused in Phase 1.

    @property
    def cache_dir(self) -> Path:
        import tempfile

        root = Path(self.temp_dir) if self.temp_dir else Path(tempfile.gettempdir())
        return root / "watch-mcp" / "cache"

    @property
    def use_stub(self) -> bool:
        return self.vlm_model.strip().lower() == "stub"


def get_settings() -> Settings:
    """Fresh Settings read (kept a function so tests can patch env)."""
    return Settings()


# Keys the setup wizard / UI manage in the user config file.
_MANAGED_KEYS = [
    "VLM_BASE_URL", "VLM_MODEL", "FULL_MODEL", "VLM_API_KEY",
    "MAX_FRAMES", "MAX_DURATION",
]


def read_config_file() -> dict[str, str]:
    """Read the user config file into a plain {KEY: value} dict (no WATCH_ prefix)."""
    out: dict[str, str] = {}
    if not CONFIG_FILE.is_file():
        return out
    for line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        if k.startswith("WATCH_"):
            k = k[len("WATCH_"):]
        out[k] = v.strip()
    return out


def write_config_file(values: dict[str, str]) -> Path:
    """Merge `values` (keys without the WATCH_ prefix) into the user config file."""
    current = read_config_file()
    for k, v in values.items():
        if v is None:
            continue
        current[k.upper()] = str(v)
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Watch MCP config — written by `watch-mcp setup` / the UI.", ""]
    lines += [f"WATCH_{k}={v}" for k, v in current.items()]
    CONFIG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return CONFIG_FILE
