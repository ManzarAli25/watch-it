"""End-to-end pipeline tests with the stub provider on a tiny generated clip.

Skipped when ffmpeg is not on PATH.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from watch_mcp.config import Settings
from watch_mcp.models import Mode
from watch_mcp.pipeline import analyze, fetch_frames

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


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # Isolated cache per test so entries don't leak between runs.
    return Settings(vlm_model="stub", max_frames=4, temp_dir=str(tmp_path / "watch"))


async def test_sample_mode_end_to_end(tiny_video: Path, settings: Settings):
    result = await analyze(str(tiny_video), mode=Mode.SAMPLE, settings=settings)
    assert result.video_id
    assert result.events, "expected at least one event"
    assert all(":" in e.timestamp for e in result.events)
    assert result.cost is not None and result.cost.calls >= 1


async def test_manual_mode_skips_ai(tiny_video: Path, settings: Settings):
    result = await analyze(str(tiny_video), mode=Mode.MANUAL, settings=settings)
    assert result.video_id
    assert result.events == []
    assert result.duration != "00:00"
    assert result.cost is None  # no model call, no cost


async def test_full_mode_native_video(tiny_video: Path, settings: Settings):
    result = await analyze(str(tiny_video), mode=Mode.FULL, settings=settings)
    assert result.video_id
    assert result.events, "stub video provider should return events"


async def test_full_mode_windowed(tiny_video: Path, settings: Settings):
    # start/end triggers an ffmpeg trim before sending; should still succeed.
    result = await analyze(
        str(tiny_video), mode=Mode.FULL, start="00:00", end="00:02", settings=settings
    )
    assert result.events


async def test_get_frames_after_watch(tiny_video: Path, settings: Settings):
    watched = await analyze(str(tiny_video), mode=Mode.MANUAL, settings=settings)
    frames = await fetch_frames(watched.video_id, "00:00", "00:02", max_frames=3, settings=settings)
    assert 1 <= len(frames) <= 3
    assert all(f.jpeg[:2] == b"\xff\xd8" for f in frames)  # JPEG magic bytes


async def test_get_frames_cache_miss(settings: Settings):
    with pytest.raises(LookupError):
        await fetch_frames("deadbeefdeadbeef", "00:00", settings=settings)
