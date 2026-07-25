"""Deterministic fake provider — for tests and no-key smoke runs.

Emits a valid Timeline JSON derived from the frame timestamps, so the whole
pipeline (download → scenes → frames → parse) can be exercised offline.
"""

from __future__ import annotations

import json

from .base import Completion, Frame, VLMProvider

_TYPES = ["navigation", "interaction", "ui_change", "error", "terminal"]


class StubProvider(VLMProvider):
    async def describe(self, frames: list[Frame], system: str, user: str) -> Completion:
        duration = frames[-1].timestamp if frames else "00:00"
        events = [
            {
                "timestamp": f.timestamp,
                "type": _TYPES[i % len(_TYPES)],
                "description": f"Stub event at frame {i} ({f.timestamp}).",
            }
            for i, f in enumerate(frames)
        ]
        return Completion(
            text=json.dumps({"duration": duration, "events": events}),
            cost_usd=0.0,
            prompt_tokens=0,
            completion_tokens=0,
        )

    async def describe_video(self, video: bytes, mime: str, system: str, user: str) -> Completion:
        # No frames to key off — emit a couple deterministic events.
        events = [
            {"timestamp": "00:00", "type": "navigation", "description": "Stub video event (start)."},
            {"timestamp": "00:01", "type": "interaction", "description": "Stub video event."},
        ]
        return Completion(
            text=json.dumps({"duration": "00:00", "events": events}),
            cost_usd=0.0,
            prompt_tokens=0,
            completion_tokens=0,
        )
