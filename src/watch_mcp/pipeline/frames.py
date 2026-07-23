"""Grab frames at given timestamps, downscale, and base64-encode for the VLM."""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import cv2
from PIL import Image

from ..models import seconds_to_ts
from ..providers.base import Frame


def sample_frames(
    video_path: Path,
    times_s: list[float],
    *,
    max_frames: int,
    max_edge: int,
) -> list[Frame]:
    """Extract up to `max_frames` evenly-selected frames from `times_s`."""
    times_s = _cap(times_s, max_frames)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video (codec/ffmpeg issue?): {video_path}")

    frames: list[Frame] = []
    try:
        for t in times_s:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
            ok, bgr = cap.read()
            if not ok or bgr is None:
                continue
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            img.thumbnail((max_edge, max_edge))
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=80)
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            frames.append(Frame(timestamp=seconds_to_ts(t), image_b64=b64, mime="image/jpeg"))
    finally:
        cap.release()

    return frames


def _cap(times: list[float], max_frames: int) -> list[float]:
    if max_frames <= 0 or len(times) <= max_frames:
        return times
    # Evenly subsample.
    step = len(times) / max_frames
    return [times[int(i * step)] for i in range(max_frames)]
