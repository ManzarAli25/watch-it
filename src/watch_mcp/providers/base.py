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

    async def describe_video(
        self, video: bytes, mime: str, system: str, user: str
    ) -> str:
        """Send a whole video clip + prompts to a video-native model (mode='full').

        Optional: providers that can't ingest video leave this unimplemented.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support native video input (mode='full')."
        )
