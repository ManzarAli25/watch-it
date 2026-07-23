"""Watch MCP server — exposes the `watch_video` tool over stdio."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .pipeline import analyze

mcp = FastMCP("watch")


@mcp.tool()
async def watch_video(
    path: str | None = None,
    url: str | None = None,
    prompt: str | None = None,
) -> str:
    """Watch a video and return a structured timeline of semantic events.

    Give AI coding agents "eyes": analyzes a screen recording (bug repro,
    feature demo, tutorial, UI walkthrough) and returns meaningful events
    (navigation, interaction, error, ui_change, ...) with timestamps —
    not a frame-by-frame dump.

    Provide exactly one of `path` or `url`.

    Args:
        path: Local video file (.mp4, .mov, .webm, .mkv, .avi, .m4v).
        url: Hosted recording URL (Loom, ScreenPal, Vimeo public, direct MP4).
             Downloaded to a temp file and deleted after analysis.
        prompt: Optional question to focus the analysis
                (e.g. "Why does the modal disappear?").

    Returns:
        Timeline JSON: {"duration": "MM:SS", "events": [{timestamp, type, description}, ...]}.
    """
    if bool(path) == bool(url):
        raise ValueError("Provide exactly one of `path` or `url`.")

    timeline = await analyze(path=path, url=url, prompt=prompt)
    return timeline.model_dump_json(indent=2)


def main() -> None:
    """Console-script / `python -m watch_mcp.server` entrypoint."""
    mcp.run()


if __name__ == "__main__":
    main()
