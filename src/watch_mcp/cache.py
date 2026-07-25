"""Content-addressed video cache — backs `video_id` and get_frames.

An entry is a directory named by a short content hash of the source:

    <cache_dir>/<video_id>/
        video.<ext>   (downloads only — local files are referenced, not copied)
        meta.json     { source, duration_s, created_at, is_ref, ref_path?, video_name? }

Local files are *referenced* (hashed by path+mtime, re-read in place). Downloads
are *copied* into the entry (they were temp anyway) and count against the LRU
size cap. Entries are content-addressed so they survive a server restart, dedupe
repeat watches, and need no in-memory session table.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .pipeline.download import download_url, is_url, validate_local
from .pipeline.frames import probe_duration


@dataclass
class CacheEntry:
    video_id: str
    path: Path  # actual file to read frames from
    duration_s: float
    source: str
    is_ref: bool


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _meta_path(entry_dir: Path) -> Path:
    return entry_dir / "meta.json"


def _touch(entry_dir: Path) -> None:
    """Bump mtime so TTL/LRU treat this as recently used."""
    try:
        entry_dir.touch()
    except OSError:
        pass


def resolve(
    *,
    path: str | None = None,
    url: str | None = None,
    settings: Settings,
    progress_cb=None,
) -> CacheEntry:
    """Resolve a local path or URL into a cached entry, creating it if absent.

    Exactly one of `path` / `url`. A bare `path` that looks like an http(s) URL is
    treated as a URL, so callers can pass either through one argument.
    """
    if bool(path) == bool(url):
        raise ValueError("Provide exactly one of `path` or `url`.")

    if path and is_url(path):
        url, path = path, None

    cache_dir = settings.cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)

    if path:
        return _resolve_local(path, cache_dir)
    return _resolve_url(url, cache_dir, settings, progress_cb=progress_cb)


def cached_url(url: str, settings: Settings) -> CacheEntry | None:
    """Return an existing entry for `url` without touching the network."""
    entry_dir = settings.cache_dir / _hash(url)
    if not _meta_path(entry_dir).is_file():
        return None
    meta = json.loads(_meta_path(entry_dir).read_text())
    video = entry_dir / meta.get("video_name", "")
    if not video.is_file():
        return None
    _touch(entry_dir)
    return CacheEntry(_hash(url), video, meta["duration_s"], url, False)


def _resolve_local(path: str, cache_dir: Path) -> CacheEntry:
    p = validate_local(path)
    key = f"{p}|{p.stat().st_mtime_ns}"
    vid = _hash(key)
    entry_dir = cache_dir / vid

    if _meta_path(entry_dir).is_file():
        _touch(entry_dir)
        meta = json.loads(_meta_path(entry_dir).read_text())
        return CacheEntry(vid, p, meta["duration_s"], str(p), True)

    entry_dir.mkdir(parents=True, exist_ok=True)
    dur = probe_duration(p)
    _write_meta(
        entry_dir,
        source=str(p),
        duration_s=dur,
        is_ref=True,
        ref_path=str(p),
        mtime_ns=p.stat().st_mtime_ns,
    )
    return CacheEntry(vid, p, dur, str(p), True)


def _resolve_url(url: str, cache_dir: Path, settings: Settings, progress_cb=None) -> CacheEntry:
    vid = _hash(url)
    entry_dir = cache_dir / vid

    if _meta_path(entry_dir).is_file():
        meta = json.loads(_meta_path(entry_dir).read_text())
        video = entry_dir / meta.get("video_name", "")
        if video.is_file():
            _touch(entry_dir)
            return CacheEntry(vid, video, meta["duration_s"], url, False)
        shutil.rmtree(entry_dir, ignore_errors=True)  # stale meta, no file — rebuild

    sweep(settings)  # make room before adding a copied download
    entry_dir.mkdir(parents=True, exist_ok=True)
    dl = download_url(url, entry_dir, settings.max_duration, progress_cb=progress_cb)
    dur = probe_duration(dl)
    _write_meta(entry_dir, source=url, duration_s=dur, is_ref=False, video_name=dl.name)
    return CacheEntry(vid, dl, dur, url, False)


def get(video_id: str, settings: Settings) -> CacheEntry | None:
    """Look up an existing entry by id. Returns None if expired/evicted/moved."""
    entry_dir = settings.cache_dir / video_id
    meta_path = _meta_path(entry_dir)
    if not meta_path.is_file():
        return None
    meta = json.loads(meta_path.read_text())

    if meta.get("is_ref"):
        p = Path(meta["ref_path"])
        if not p.is_file():
            return None  # user moved/deleted the original
        if "mtime_ns" in meta and p.stat().st_mtime_ns != meta["mtime_ns"]:
            return None  # file edited since caching — force a re-watch
        _touch(entry_dir)
        return CacheEntry(video_id, p, meta["duration_s"], meta["source"], True)

    video = entry_dir / meta.get("video_name", "")
    if not video.is_file():
        return None
    _touch(entry_dir)
    return CacheEntry(video_id, video, meta["duration_s"], meta["source"], False)


def sweep(settings: Settings) -> None:
    """Evict entries older than the TTL, then LRU-evict copied downloads over the cap."""
    cache_dir = settings.cache_dir
    if not cache_dir.exists():
        return

    now = time.time()
    if settings.cache_ttl and settings.cache_ttl > 0:
        for d in _entry_dirs(cache_dir):
            if now - d.stat().st_mtime > settings.cache_ttl:
                shutil.rmtree(d, ignore_errors=True)

    if settings.cache_max_bytes and settings.cache_max_bytes > 0:
        dirs = _entry_dirs(cache_dir)
        total = sum(_dir_bytes(d) for d in dirs)
        if total > settings.cache_max_bytes:
            for d in sorted(dirs, key=lambda d: d.stat().st_mtime):  # oldest first
                if total <= settings.cache_max_bytes:
                    break
                total -= _dir_bytes(d)
                shutil.rmtree(d, ignore_errors=True)


def _entry_dirs(cache_dir: Path) -> list[Path]:
    return [d for d in cache_dir.iterdir() if d.is_dir()]


def _dir_bytes(d: Path) -> int:
    return sum(f.stat().st_size for f in d.glob("*") if f.is_file())


def _write_meta(entry_dir: Path, **fields) -> None:
    fields["created_at"] = time.time()
    _meta_path(entry_dir).write_text(json.dumps(fields))
