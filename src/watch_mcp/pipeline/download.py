"""Resolve an input (local path or URL) to a playable local video file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}


@dataclass
class ResolvedSource:
    path: Path
    is_temp: bool  # True when we downloaded it and should delete afterwards.


def resolve_source(
    *,
    path: str | None = None,
    url: str | None = None,
    temp_dir: Path,
    max_duration: float = 0.0,
) -> ResolvedSource:
    """Return a local file for either a path or a URL.

    Exactly one of `path` / `url` must be provided. `max_duration` (seconds, 0 =
    off) rejects over-long hosted videos before the full download completes.
    """
    if bool(path) == bool(url):
        raise ValueError("Provide exactly one of `path` or `url`.")

    if path:
        p = Path(path).expanduser()
        if not p.is_file():
            raise FileNotFoundError(f"Video not found: {p}")
        if p.suffix.lower() not in VIDEO_EXTS:
            raise ValueError(
                f"Unsupported extension {p.suffix!r}. Expected one of {sorted(VIDEO_EXTS)}."
            )
        return ResolvedSource(path=p, is_temp=False)

    return ResolvedSource(path=_download(url, temp_dir, max_duration), is_temp=True)


def _download(url: str, temp_dir: Path, max_duration: float) -> Path:
    """Download a hosted video (Loom / ScreenPal / Vimeo / direct MP4) via yt-dlp."""
    import yt_dlp

    temp_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(temp_dir / "%(id)s.%(ext)s")
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
    if not p.is_file():
        # merge_output_format may have changed the extension.
        stem = p.with_suffix("")
        for cand in temp_dir.glob(f"{stem.name}.*"):
            if cand.suffix.lower() in VIDEO_EXTS:
                return cand
        raise RuntimeError(f"Download reported success but file missing: {p}")
    return p


def cleanup(source: ResolvedSource) -> None:
    """Delete a downloaded temp file. No-op for user-supplied local files."""
    if source.is_temp:
        try:
            os.remove(source.path)
        except OSError:
            pass
