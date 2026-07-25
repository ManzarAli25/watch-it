"""Primitives for turning an input (local path or URL) into a local video file.

Orchestration (caching, video_id, reference-vs-copy) lives in ``watch_mcp.cache``;
this module only knows how to validate a local file and how to fetch a URL.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}

_MIME_BY_EXT = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
}

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
        # Resilience on flaky networks / large files.
        "socket_timeout": 60,
        "retries": 5,
        "fragment_retries": 5,
        "extractor_retries": 3,
        # Prefer video-only mp4 (skip audio Watch never uses) when a site exposes
        # separate streams; otherwise fall back to the best single file. Broad
        # fallback matters for generic extractors (Loom/ScreenPal) with one muxed
        # format of unknown codec.
        "format": "bestvideo[ext=mp4]/best",
    }
    if max_duration and max_duration > 0:
        # Reject over-long videos up front. "<=?" allows through videos whose
        # duration is unknown pre-download (common with generic extractors) —
        # the pipeline re-checks the real duration after probing.
        opts["match_filter"] = yt_dlp.utils.match_filter_func(
            f"duration <=? {int(max_duration)}"
        )

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


def mime_for(path: Path) -> str:
    return _MIME_BY_EXT.get(path.suffix.lower(), "video/mp4")


def read_video_bytes(
    path: Path,
    start_s: float | None = None,
    end_s: float | None = None,
) -> tuple[bytes, str]:
    """Read a video as bytes for native-video input (mode='full').

    When `start_s`/`end_s` are given, ffmpeg trims to that window first (stream
    copy, no re-encode) so only the relevant span is sent to the model.
    """
    if start_s is None and end_s is None:
        return path.read_bytes(), mime_for(path)

    tmp = Path(tempfile.gettempdir()) / f"watch-clip-{path.stem}.mp4"
    cmd = ["ffmpeg", "-y"]
    if start_s is not None:
        cmd += ["-ss", str(start_s)]
    if end_s is not None:
        cmd += ["-to", str(end_s)]
    cmd += ["-i", str(path), "-an", "-c", "copy", str(tmp)]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return tmp.read_bytes(), "video/mp4"
    finally:
        tmp.unlink(missing_ok=True)
