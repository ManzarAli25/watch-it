"""End-to-end video analysis orchestrator."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from ..config import Settings, get_settings
from ..models import Timeline, seconds_to_ts
from ..providers import build_provider
from .events import extract_timeline


async def analyze(
    *,
    path: str | None = None,
    url: str | None = None,
    prompt: str | None = None,
    settings: Settings | None = None,
) -> Timeline:
    """Resolve → detect scenes → sample frames → VLM → validated Timeline.

    The decode/download/sampling stages are synchronous (yt-dlp, PySceneDetect,
    OpenCV), so they run in worker threads to keep the MCP event loop responsive.
    Temp downloads are always cleaned up.
    """
    # Heavy video deps (OpenCV, PySceneDetect, yt-dlp) are imported here, not at
    # module load, so lightweight consumers (e.g. importing `extract_timeline`)
    # don't pay for them.
    from .download import cleanup, resolve_source
    from .frames import sample_frames
    from .scenes import detect_scene_times

    settings = settings or get_settings()
    temp_root = Path(settings.temp_dir) if settings.temp_dir else Path(tempfile.gettempdir())
    temp_dir = temp_root / "watch-mcp"

    source = await asyncio.to_thread(
        resolve_source,
        path=path,
        url=url,
        temp_dir=temp_dir,
        max_duration=settings.max_duration,
    )
    try:
        times, duration_s = await asyncio.to_thread(
            detect_scene_times,
            source.path,
            threshold=settings.scene_threshold,
            fallback_interval=settings.fallback_interval,
        )

        # Guard local files too (the yt-dlp filter only covers URLs).
        if settings.max_duration and duration_s > settings.max_duration:
            raise ValueError(
                f"Video is {seconds_to_ts(duration_s)}, longer than the "
                f"{seconds_to_ts(settings.max_duration)} limit (WATCH_MAX_DURATION)."
            )

        frames = await asyncio.to_thread(
            sample_frames,
            source.path,
            times,
            max_frames=settings.max_frames,
            max_edge=settings.frame_max_edge,
        )
        if not frames:
            raise RuntimeError("No frames could be extracted from the video.")

        provider = build_provider(settings)
        duration = seconds_to_ts(duration_s) if duration_s else None
        return await extract_timeline(provider, frames, prompt=prompt, duration=duration)
    finally:
        await asyncio.to_thread(cleanup, source)


__all__ = ["analyze"]
