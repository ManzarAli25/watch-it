"""Watch MCP server — exposes `watch` and `get_frames` over stdio."""

from __future__ import annotations

import asyncio

from mcp.server.fastmcp import Context, FastMCP, Image

from .config import get_settings
from .models import Mode
from .pipeline import analyze, fetch_frames
from .progress import ProgressState, heartbeat

mcp = FastMCP("watch-it")


def _warm_imports() -> None:
    """Load the native-extension stack (OpenCV/NumPy/yt-dlp) before serving.

    These imports are lazy so the CLI stays fast, but doing them inside a tool
    handler runs them on the event-loop thread — where a slow or wedged DLL load
    freezes the whole server: no progress, no ping response, no cancellation, and
    the client eventually aborts on its idle timeout with nothing to show. Paying
    the cost once at startup keeps request handling non-blocking.
    """
    from . import cache  # noqa: F401  (pulls cv2/numpy via pipeline.frames)
    from .pipeline import events, frames, scenes  # noqa: F401


@mcp.tool()
async def watch(
    video_path: str,
    query: str | None = None,
    mode: str = "sample",
    start: str | None = None,
    end: str | None = None,
    timeout: float | None = None,
    ctx: Context | None = None,
) -> str:
    """Watch a video and return a structured timeline of semantic events.

    Gives you "eyes": analyzes a screen recording (bug repro, feature demo,
    tutorial, UI walkthrough) and returns meaningful events (navigation,
    interaction, error, ui_change, ...) with timestamps — not a frame-by-frame
    dump. Returns a `video_id` you can pass to `get_frames` to inspect exact
    frames yourself.

    Args:
        video_path: Local file (.mp4/.mov/.webm/.mkv/.avi/.m4v) OR hosted URL.
            Hosted URLs are resolved with yt-dlp, so anything it supports works —
            Loom, ScreenPal, Vimeo (public), direct MP4, and HLS/DASH streams are
            the tested paths. Private, login-walled, or DRM'd links, and hosts
            with no extractor, fail fast with an explicit error rather than
            hanging. URLs are downloaded to a temporary cache.
        query: What to focus on, e.g. "Why does the modal disappear?". Optional.
        mode: "sample" (default) — AI scans scene-sampled frames into a timeline;
            cheap and flat-cost. "manual" — no AI: just cache the video and return
            its video_id + duration so you can look at frames yourself via
            get_frames (use when the user already pointed you at an exact moment).
            "full" — send the whole clip to a video-native model (costlier, scales
            with duration; requires a video-capable endpoint).
        start: Optional MM:SS — restrict analysis to from this time.
        end: Optional MM:SS — restrict analysis to up to this time.
        timeout: Optional seconds to bound the whole call (default WATCH_TOOL_TIMEOUT,
            900s). Pass 0 to disable. The server aborts itself with an error when
            exceeded, so a stuck stage never burns a client-side idle timeout.

    Returns:
        JSON: {"video_id": "...", "duration": "MM:SS",
               "events": [{timestamp, type, description}, ...],
               "cost": {"usd": ..., "prompt_tokens": ..., "completion_tokens": ...,
                        "model": ..., "calls": ...}}
        (events is empty and cost is null when mode="manual").
    """
    try:
        m = Mode(mode.strip().lower())
    except ValueError:
        raise ValueError(f"Unknown mode {mode!r}. Use one of: sample, manual, full.")

    settings = get_settings()
    budget = settings.tool_timeout if timeout is None else timeout
    state = ProgressState()

    async with heartbeat(ctx, state, interval=settings.progress_interval):
        try:
            result = await asyncio.wait_for(
                analyze(video_path, query=query, mode=m, start=start, end=end,
                        settings=settings, state=state),
                timeout=budget or None,
            )
        except TimeoutError as e:
            raise TimeoutError(
                f"watch timed out after {budget:.0f}s while {state.message!r} "
                f"({state.percent:.0f}% done). Raise the `timeout` argument or "
                f"WATCH_TOOL_TIMEOUT, or narrow the clip with start/end."
            ) from e

    return result.model_dump_json(indent=2)


@mcp.tool()
async def get_frames(
    video_id: str,
    start: str,
    end: str | None = None,
    max_frames: int = 8,
) -> list:
    """Pull actual frame images from a video you already watched — see for yourself.

    Use when you doubt the timeline's description of a moment, or the user pointed
    you at an exact span. Returns the real pixels so you can read UI text, console
    errors, or code directly.

    Args:
        video_id: The id returned by a prior `watch` call.
        start: MM:SS timestamp (copy one straight from a timeline event).
        end: Optional MM:SS. Omit for a single frame at `start`; provide it to get
            frames evenly spaced across [start, end].
        max_frames: Max frames to return (hard-capped by the server, default 8).

    Returns:
        A list of frame images with their timestamps.
    """
    frames = await fetch_frames(video_id, start, end, max_frames=max_frames)
    if not frames:
        return ["No frames could be extracted for that range."]

    out: list = []
    for f in frames:
        out.append(f"Frame at {f.timestamp}:")
        out.append(Image(data=f.jpeg, format="jpeg"))
    return out


def main() -> None:
    """Console-script / `python -m watch_mcp.server` entrypoint."""
    _warm_imports()
    mcp.run()


if __name__ == "__main__":
    main()
