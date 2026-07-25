"""Primitives for turning an input (local path or URL) into a local video file.

Orchestration (caching, video_id, reference-vs-copy) lives in ``watch_mcp.cache``;
this module only knows how to validate a local file and how to fetch a URL.
"""

from __future__ import annotations

import re
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def is_url(s: str) -> bool:
    return bool(_URL_RE.match(s.strip()))


def validate_local(path: str) -> Path:
    """Resolve + validate a user-supplied local video path."""
    p = Path(path).expanduser()
    if not p.is_file():
        raise FileNotFoundError(f"Video not found: {p}")
    if p.suffix.lower() not in VIDEO_EXTS:
        raise ValueError(
            f"Unsupported extension {p.suffix!r}. Expected one of {sorted(VIDEO_EXTS)}."
        )
    return p.resolve()


def download_url(url: str, dest_dir: Path, max_duration: float = 0.0) -> Path:
    """Download a hosted video (Loom / ScreenPal / Vimeo / direct MP4) via yt-dlp.

    Returns the path to the downloaded file inside ``dest_dir``. ``max_duration``
    (seconds, 0 = off) rejects over-long videos before the bytes are fetched.
    """
    import yt_dlp

    dest_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(dest_dir / "video.%(ext)s")
    opts = {
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        # Video only — Watch never uses audio, so skip fetching/muxing it. Prefer a
        # single already-muxed mp4 to avoid an ffmpeg merge; fall back to best.
        "format": "bestvideo[ext=mp4]/best[ext=mp4]/best",
    }
    if max_duration and max_duration > 0:
        # Reject over-long videos up front (before downloading the bytes).
        opts["match_filter"] = yt_dlp.utils.match_filter_func(f"duration <= {int(max_duration)}")

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if info is None:
            raise ValueError(
                f"Video rejected (likely longer than the {int(max_duration)}s limit): {url}"
            )
        filename = ydl.prepare_filename(info)

    p = Path(filename)
    if p.is_file():
        return p
    # Extension may differ from what prepare_filename guessed.
    for cand in dest_dir.glob("video.*"):
        if cand.suffix.lower() in VIDEO_EXTS:
            return cand
    raise RuntimeError(f"Download reported success but file missing: {p}")
