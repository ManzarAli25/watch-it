"""Scene detection — find meaningful cut points so we sample only what matters."""

from __future__ import annotations

from pathlib import Path

from scenedetect import ContentDetector, SceneManager, open_video


def detect_scene_times(
    video_path: Path,
    *,
    threshold: float,
    fallback_interval: float,
) -> tuple[list[float], float]:
    """Return (sample timestamps in seconds, video duration in seconds).

    Timestamps are one point near the middle of each detected scene. Falls back
    to fixed-interval sampling when the detector finds 0/1 scenes (e.g. a static
    screen recording with no hard cuts).
    """
    video = open_video(str(video_path))
    duration_s = video.duration.get_seconds() if video.duration else 0.0

    manager = SceneManager()
    manager.add_detector(ContentDetector(threshold=threshold))
    manager.detect_scenes(video, show_progress=False)
    scenes = manager.get_scene_list()

    if len(scenes) >= 2:
        times = [(start.get_seconds() + end.get_seconds()) / 2.0 for start, end in scenes]
        return times, duration_s

    return _interval_times(duration_s, fallback_interval), duration_s


def _interval_times(duration_s: float, interval: float) -> list[float]:
    if duration_s <= 0:
        return [0.0]
    interval = max(0.5, interval)
    times: list[float] = []
    t = interval / 2.0
    while t < duration_s:
        times.append(t)
        t += interval
    return times or [duration_s / 2.0]
