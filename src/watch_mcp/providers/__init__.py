"""VLM provider factory."""

from __future__ import annotations

from ..config import Settings
from .base import Frame, VLMProvider

__all__ = ["Frame", "VLMProvider", "build_provider"]


def build_provider(settings: Settings, model: str | None = None) -> VLMProvider:
    """Pick a provider from config. WATCH_VLM_MODEL=stub → StubProvider.

    `model` overrides the configured model (used so mode='full' can target a
    video-capable model different from the sample/image model).
    """
    resolved = model or settings.vlm_model
    if resolved.strip().lower() == "stub":
        from .stub import StubProvider

        return StubProvider()

    from .openai_compat import OpenAICompatProvider

    return OpenAICompatProvider(settings, model=resolved)
