"""Runtime configuration, loaded from environment / .env."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor .env to the project root, not the client's cwd. MCP clients (Claude Code,
# Cursor, Codex) spawn the server from *their* working directory, so a relative
# "./.env" would never be found and settings would silently fall back to stub.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WATCH_",
        env_file=_PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # VLM backend (OpenAI-compatible vision endpoint)
    vlm_base_url: str = "http://localhost:8000/v1"
    vlm_model: str = "stub"
    vlm_api_key: str = ""
    vlm_timeout: float = 120.0
    vlm_max_tokens: int = 4096

    # Sampling / cost controls
    max_frames: int = 32
    frame_max_edge: int = 768
    scene_threshold: float = 27.0
    fallback_interval: float = 5.0
    max_duration: float = 1800.0  # reject inputs longer than this (seconds); 0 disables.

    # Misc
    temp_dir: str = ""
    ocr: bool = False  # Phase 2 hook; unused in Phase 1.

    @property
    def use_stub(self) -> bool:
        return self.vlm_model.strip().lower() == "stub"


def get_settings() -> Settings:
    """Fresh Settings read (kept a function so tests can patch env)."""
    return Settings()
