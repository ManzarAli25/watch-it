"""Tests for the update checker (no network — sources are monkeypatched)."""

from watch_mcp import update


def test_version_compare():
    assert update._is_newer("0.3.0", "0.2.0")
    assert update._is_newer("0.10.0", "0.2.0")   # numeric, not lexical
    assert update._is_newer("1.0.0", "0.9.9")
    assert not update._is_newer("0.2.0", "0.2.0")
    assert not update._is_newer("0.1.0", "0.2.0")


def test_check_reports_newer(monkeypatch):
    monkeypatch.setattr(update, "_cached_latest", lambda: "9.9.9")
    notice = update.check()
    assert notice and "Update available" in notice
    assert "uv tool upgrade" in notice


def test_check_silent_when_current(monkeypatch):
    monkeypatch.setattr(update, "_cached_latest", lambda: update.__version__)
    assert update.check() is None


def test_check_silent_when_offline(monkeypatch):
    def boom():
        raise RuntimeError("no network")
    monkeypatch.setattr(update, "_cached_latest", boom)
    assert update.check() is None
