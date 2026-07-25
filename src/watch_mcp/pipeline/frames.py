"""Grab frames at given timestamps: raw JPEG bytes, or base64-wrapped for the VLM."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import cv2
from PIL import Image

from ..models import seconds_to_ts
from ..providers.base import Frame


@dataclass
class GrabbedFrame:
    timestamp: str  # MM:SS / HH:MM:SS
    jpeg: bytes


def probe_duration(video_path: Path) -> float:
    """Cheap duration probe (seconds) from container metadata — no full decode."""
    cap = cv2.VideoCapture(str(video_path))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        n = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if fps and fps > 0 and n and n > 0:
            return n / fps
        return 0.0
    finally:
        cap.release()


def grab_frames(
    video_path: Path,
    times_s: list[float],
    *,
    max_edge: int,
) -> list[GrabbedFrame]:
    """Extract, downscale, and JPEG-encode frames at the given timestamps."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video (codec/ffmpeg issue?): {video_path}")

    out: list[GrabbedFrame] = []
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
            out.append(GrabbedFrame(timestamp=seconds_to_ts(t), jpeg=buf.getvalue()))
    finally:
        cap.release()

    return out


def sample_frames(
    video_path: Path,
    times_s: list[float],
    *,
    max_frames: int,
    max_edge: int,
) -> list[Frame]:
    """Extract up to `max_frames` evenly-selected frames, base64-wrapped for the VLM."""
    times_s = _cap(times_s, max_frames)
    grabbed = grab_frames(video_path, times_s, max_edge=max_edge)
    return [
        Frame(
            timestamp=g.timestamp,
            image_b64=base64.b64encode(g.jpeg).decode("ascii"),
            mime="image/jpeg",
        )
        for g in grabbed
    ]


def even_times(start_s: float, end_s: float | None, count: int) -> list[float]:
    """`count` evenly-spaced timestamps in [start, end]; single point when end is None."""
    if end_s is None or end_s <= start_s or count <= 1:
        return [start_s]
    step = (end_s - start_s) / (count - 1)
    return [start_s + i * step for i in range(count)]


def _cap(times: list[float], max_frames: int) -> list[float]:
    if max_frames <= 0 or len(times) <= max_frames:
        return times
    # Evenly subsample.
    step = len(times) / max_frames
    return [times[int(i * step)] for i in range(max_frames)]
