"""End-to-end video analysis orchestrator."""

from __future__ import annotations

import asyncio

from ..config import Settings, get_settings
from ..models import Mode, WatchResult, seconds_to_ts, ts_to_seconds
from ..providers import build_provider
from .events import extract_timeline


async def analyze(
    video_path: str,
    *,
    query: str | None = None,
    mode: Mode = Mode.SAMPLE,
    start: str | None = None,
    end: str | None = None,
    settings: Settings | None = None,
) -> WatchResult:
    """Resolve+cache → (mode) → WatchResult{video_id, duration, events}.

    `video_path` is a local path or a hosted URL (auto-detected). The synchronous
    stages (yt-dlp, PySceneDetect, OpenCV) run in worker threads so the MCP event
    loop stays responsive. The resolved video is cached (see `watch_mcp.cache`) so
    `fetch_frames` can reuse it without re-downloading.
    """
    from .. import cache  # lazy: pulls OpenCV/yt-dlp only on the video path.
    from .frames import sample_frames
    from .scenes import detect_scene_times

    settings = settings or get_settings()

    entry = await asyncio.to_thread(cache.resolve, path=video_path, settings=settings)
    duration_s = entry.duration_s

    if settings.max_duration and duration_s > settings.max_duration:
        raise ValueError(
            f"Video is {seconds_to_ts(duration_s)}, longer than the "
            f"{seconds_to_ts(settings.max_duration)} limit (WATCH_MAX_DURATION)."
        )
    duration = seconds_to_ts(duration_s) if duration_s else "00:00"

    if mode is Mode.MANUAL:
        # No AI — just hand back the handle so Claude drives via get_frames.
        return WatchResult(video_id=entry.video_id, duration=duration, events=[])

    if mode is Mode.FULL:
        raise NotImplementedError(
            "mode='full' (native video) is not wired yet; use 'sample' or 'manual'."
        )

    # mode == SAMPLE
    start_s = ts_to_seconds(start) if start is not None else None
    end_s = ts_to_seconds(end) if end is not None else None

    times, _ = await asyncio.to_thread(
        detect_scene_times,
        entry.path,
        threshold=settings.scene_threshold,
        fallback_interval=settings.fallback_interval,
        start_s=start_s,
        end_s=end_s,
    )
    frames = await asyncio.to_thread(
        sample_frames,
        entry.path,
        times,
        max_frames=settings.max_frames,
        max_edge=settings.frame_max_edge,
    )
    if not frames:
        raise RuntimeError("No frames could be extracted from the video.")

    provider = build_provider(settings)
    timeline = await extract_timeline(provider, frames, prompt=query, duration=duration)
    return WatchResult(video_id=entry.video_id, duration=duration, events=timeline.events)


async def fetch_frames(
    video_id: str,
    start: str,
    end: str | None = None,
    *,
    max_frames: int | None = None,
    settings: Settings | None = None,
):
    """Pull raw frames from a cached video for get_frames (Claude's own eyes).

    Returns a list of `GrabbedFrame`. Raises LookupError on a cache miss so the
    caller can tell Claude to re-`watch`.
    """
    from .. import cache
    from .frames import even_times, grab_frames

    settings = settings or get_settings()

    entry = await asyncio.to_thread(cache.get, video_id, settings)
    if entry is None:
        raise LookupError(f"video_id {video_id!r} expired or was evicted — call watch() again.")

    cap = settings.get_frames_max
    if max_frames is not None:
        cap = max(1, min(max_frames, settings.get_frames_max))

    start_s = ts_to_seconds(start)
    end_s = ts_to_seconds(end) if end is not None else None
    times = even_times(start_s, end_s, cap)

    return await asyncio.to_thread(
        grab_frames, entry.path, times, max_edge=settings.frame_max_edge
    )


__all__ = ["analyze", "fetch_frames"]
