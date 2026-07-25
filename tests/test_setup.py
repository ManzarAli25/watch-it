"""Tests for the setup layer: ffmpeg locate, config file, client detection."""

from pathlib import Path

from watch_mcp import clients, config
from watch_mcp.ffmpeg import ffmpeg_path


def test_ffmpeg_path_exists():
    p = ffmpeg_path()
    assert p
    assert Path(p).exists() or Path(p).name.lower().startswith("ffmpeg")


def test_config_roundtrip(tmp_path, monkeypatch):
    cfg = tmp_path / "config.env"
    monkeypatch.setattr(config, "CONFIG_FILE", cfg)
    config.write_config_file({"VLM_MODEL": "qwen/x", "FULL_MODEL": "qwen/y", "VLM_API_KEY": "sk-1"})
    got = config.read_config_file()
    assert got["VLM_MODEL"] == "qwen/x"
    assert got["FULL_MODEL"] == "qwen/y"
    assert got["VLM_API_KEY"] == "sk-1"
    # merge, not clobber
    config.write_config_file({"VLM_MODEL": "qwen/z"})
    got = config.read_config_file()
    assert got["VLM_MODEL"] == "qwen/z"
    assert got["FULL_MODEL"] == "qwen/y"


def test_server_command():
    cmd, args = clients.server_command()
    assert isinstance(cmd, str) and cmd
    assert "serve" in args


def test_detect_returns_three_clients():
    names = {c.name for c in clients.detect()}
    assert names == {"Claude Code", "Cursor", "Codex"}
