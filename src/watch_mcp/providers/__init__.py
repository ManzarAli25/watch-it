"""VLM provider factory."""

from __future__ import annotations

from ..config import Settings
from .base import Frame, VLMProvider

__all__ = ["Frame", "VLMProvider", "build_provider"]


def build_provider(settings: Settings) -> VLMProvider:
    """Pick a provider from config. WATCH_VLM_MODEL=stub → StubProvider."""
    if settings.use_stub:
        from .stub import StubProvider

        return StubProvider()

    from .openai_compat import OpenAICompatProvider

    return OpenAICompatProvider(settings)
