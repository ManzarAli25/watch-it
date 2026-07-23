"""End-to-end pipeline test with the stub provider on a tiny generated clip.

Skipped when ffmpeg is not on PATH.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from watch_mcp.config import Settings
from watch_mcp.pipeline import analyze

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


@pytest.fixture
def tiny_video(tmp_path: Path) -> Path:
    out = tmp_path / "clip.mp4"
    # 3s test pattern; two distinct scenes via a color change.
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=3:size=320x240:rate=10",
            "-pix_fmt", "yuv420p", str(out),
        ],
        check=True,
        capture_output=True,
    )
    return out


async def test_analyze_stub_end_to_end(tiny_video: Path):
    settings = Settings(vlm_model="stub", max_frames=4)
    tl = await analyze(path=str(tiny_video), settings=settings)
    assert tl.events, "expected at least one event"
    assert all(":" in e.timestamp for e in tl.events)
