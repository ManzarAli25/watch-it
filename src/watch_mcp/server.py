"""Watch MCP server — exposes `watch` and `get_frames` over stdio."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP, Image

from .models import Mode
from .pipeline import analyze, fetch_frames

mcp = FastMCP("watch-it")


@mcp.tool()
async def watch(
    video_path: str,
    query: str | None = None,
    mode: str = "sample",
    start: str | None = None,
    end: str | None = None,
) -> str:
    """Watch a video and return a structured timeline of semantic events.

    Gives you "eyes": analyzes a screen recording (bug repro, feature demo,
    tutorial, UI walkthrough) and returns meaningful events (navigation,
    interaction, error, ui_change, ...) with timestamps — not a frame-by-frame
    dump. Returns a `video_id` you can pass to `get_frames` to inspect exact
    frames yourself.

    Args:
        video_path: Local file (.mp4/.mov/.webm/.mkv/.avi/.m4v) OR hosted URL
            (Loom, ScreenPal, Vimeo public, direct MP4). URLs are downloaded to a
            temporary cache.
        query: What to focus on, e.g. "Why does the modal disappear?". Optional.
        mode: "sample" (default) — AI scans scene-sampled frames into a timeline;
            cheap and flat-cost. "manual" — no AI: just cache the video and return
            its video_id + duration so you can look at frames yourself via
            get_frames (use when the user already pointed you at an exact moment).
            "full" — send the whole clip to a video-native model (costlier, scales
            with duration; requires a video-capable endpoint).
        start: Optional MM:SS — restrict analysis to from this time.
        end: Optional MM:SS — restrict analysis to up to this time.

    Returns:
        JSON: {"video_id": "...", "duration": "MM:SS", "events": [{timestamp, type, description}, ...]}
        (events is empty when mode="manual").
    """
    try:
        m = Mode(mode.strip().lower())
    except ValueError:
        raise ValueError(f"Unknown mode {mode!r}. Use one of: sample, manual, full.")

    result = await analyze(video_path, query=query, mode=m, start=start, end=end)
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
    mcp.run()


if __name__ == "__main__":
    main()
