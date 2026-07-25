"""Locate an ffmpeg binary.

Prefers a system ffmpeg on PATH; otherwise falls back to the static binary that
`imageio-ffmpeg` ships. This removes the manual ffmpeg install from setup.
"""

from __future__ import annotations

import functools
import shutil


@functools.lru_cache(maxsize=1)
def ffmpeg_path() -> str:
    """Return a path to an ffmpeg executable (system PATH first, else bundled)."""
    system = shutil.which("ffmpeg")
    if system:
        return system
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()
