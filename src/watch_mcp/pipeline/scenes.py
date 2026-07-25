"""Scene detection — find meaningful cut points so we sample only what matters."""

from __future__ import annotations

from pathlib import Path

from scenedetect import ContentDetector, SceneManager, open_video


def detect_scene_times(
    video_path: Path,
    *,
    threshold: float,
    fallback_interval: float,
    start_s: float | None = None,
    end_s: float | None = None,
) -> tuple[list[float], float]:
    """Return (sample timestamps in seconds, video duration in seconds).

    Timestamps are one point near the middle of each detected scene. Falls back
    to fixed-interval sampling when the detector finds 0/1 scenes (e.g. a static
    screen recording with no hard cuts). When `start_s`/`end_s` are given, sampling
    is restricted to that window.
    """
    video = open_video(str(video_path))
    duration_s = video.duration.seconds if video.duration else 0.0

    lo = start_s if start_s is not None else 0.0
    hi = end_s if end_s is not None else (duration_s or float("inf"))

    manager = SceneManager()
    manager.add_detector(ContentDetector(threshold=threshold))
    manager.detect_scenes(video, show_progress=False)
    scenes = manager.get_scene_list()

    if len(scenes) >= 2:
        times = [(s.seconds + e.seconds) / 2.0 for s, e in scenes]
        windowed = [t for t in times if lo <= t <= hi]
        if windowed:
            return windowed, duration_s
        # Window fell between cuts — fall through to interval sampling within it.

    span_end = hi if hi != float("inf") else duration_s
    return _interval_times(lo, span_end, fallback_interval), duration_s


def _interval_times(start_s: float, end_s: float, interval: float) -> list[float]:
    if end_s <= 0 or end_s <= start_s:
        return [max(0.0, start_s)]
    interval = max(0.5, interval)
    times: list[float] = []
    t = start_s + interval / 2.0
    while t < end_s:
        times.append(t)
        t += interval
    return times or [(start_s + end_s) / 2.0]
