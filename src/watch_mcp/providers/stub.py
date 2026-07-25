"""Deterministic fake provider — for tests and no-key smoke runs.

Emits a valid Timeline JSON derived from the frame timestamps, so the whole
pipeline (download → scenes → frames → parse) can be exercised offline.
"""

from __future__ import annotations

import json

from .base import Frame, VLMProvider

_TYPES = ["navigation", "interaction", "ui_change", "error", "terminal"]


class StubProvider(VLMProvider):
    async def describe(self, frames: list[Frame], system: str, user: str) -> str:
        duration = frames[-1].timestamp if frames else "00:00"
        events = [
            {
                "timestamp": f.timestamp,
                "type": _TYPES[i % len(_TYPES)],
                "description": f"Stub event at frame {i} ({f.timestamp}).",
            }
            for i, f in enumerate(frames)
        ]
        return json.dumps({"duration": duration, "events": events})

    async def describe_video(self, video: bytes, mime: str, system: str, user: str) -> str:
        # No frames to key off — emit a couple deterministic events.
        events = [
            {"timestamp": "00:00", "type": "navigation", "description": "Stub video event (start)."},
            {"timestamp": "00:01", "type": "interaction", "description": "Stub video event."},
        ]
        return json.dumps({"duration": "00:00", "events": events})
