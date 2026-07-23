"""VLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Frame:
    """One sampled video frame."""

    timestamp: str  # MM:SS / HH:MM:SS
    image_b64: str  # base64 PNG/JPEG bytes (no data: prefix)
    mime: str = "image/jpeg"


class VLMProvider(ABC):
    """Turns a batch of timestamped frames into raw model text.

    Event parsing lives in pipeline.events, not here — providers only
    speak to the model and return whatever string it produced.
    """

    @abstractmethod
    async def describe(self, frames: list[Frame], system: str, user: str) -> str:
        """Send frames + prompts to the model, return its text response."""
        raise NotImplementedError
