"""OCR seam — a no-op in Phase 1.

Left as an interface so Phase 2 can drop in PaddleOCR (or equivalent) to feed
on-screen text into event extraction without touching the pipeline shape.
"""

from __future__ import annotations

from ..providers.base import Frame


class OcrEngine:
    """No-op OCR. Returns empty text for every frame."""

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    def extract(self, frame: Frame) -> str:  # noqa: ARG002
        return ""
