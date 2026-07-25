# Watch — Phase 2 tool design (agreed)

Evolves the single `watch_video` tool into a small toolset: an AI perceptor with
an on-demand "Claude's own eyes" escape hatch, backed by a content-addressed video
cache so frames can be pulled without re-downloading/re-decoding.

## Tools

### `watch(video_path, query=None, mode="sample", start=None, end=None)`
Resolve + cache the video, optionally analyze it, return a handle.

- **query** — what to focus the analysis on (Claude extracts from the user's ask). Optional.
- **video_path** — local path OR hosted URL (Loom/ScreenPal/Vimeo/direct MP4). Resolved respectively.
- **mode** — enum (not bool), so it can grow:
  | mode | meaning | VLM cost |
  |------|---------|----------|
  | `sample` (default) | current pipeline: scene-detect → sample frames → VLM → timeline | cheap, flat |
  | `full` | native-video pipeline (send clip to a video-native model) | scales with duration |
  | `manual` | **no AI** — just resolve + cache, return `video_id` + `duration`, `events: []`. Claude/user drives via `get_frames`. | zero |
- **start / end** — `MM:SS`, optional. Both `None` = whole video. Named `start`/`end` (not `from` — reserved word). Same `MM:SS` format the timeline emits, so Claude copies a timestamp straight back.

Returns:
```json
{ "video_id": "a3f8c1...", "duration": "02:13", "events": [ /* [] when mode=manual */ ] }
```

### `get_frames(video_id, start, end=None, max_frames=8)`
Pull actual frame images — Claude's own eyes, for when it doubts the perceptor or
the user pinned an exact moment.

- **video_id** — handle from a prior `watch()` call.
- **start / end** — `MM:SS`. `end=None` = single frame at `start` (folds the old `get_frame` in — one tool, not two).
- **max_frames** — hard cap (~8) so Claude can't flood its own context.
- Returns image content blocks. **Cache miss** (expired/evicted id) → clean error `"video_id expired, call watch() again"`; never crash.

## Mode decision table (for Claude)

| Situation | Mode |
|---|---|
| User points to an exact moment ("bug at 0:02–0:22") | `manual` — Claude looks itself, no VLM |
| "Something's wrong somewhere" on a long video | `sample` — AI scans, Claude drills in with `get_frames` |
| Need fine temporal motion, short clip | `full` — native video |

## Video cache (`video_id`)

Content-addressed, disk-backed, no in-memory session table.

- `video_id = sha256(resolved_source_key)[:16]`
  - **local files:** key = `path + mtime` → **reference** in `meta.json`, do **not** copy (already on disk; re-read is cheap; re-hash catches edits).
  - **downloads:** **copy** into cache (they're temp anyway).
- Layout:
  ```
  temp/watch-mcp/<video_id>/
      video.mp4      (downloads only; local files referenced via meta.json)
      meta.json      { source, duration_s, created_at, is_ref }
  ```
- **Benefits:** survives server restart (Oracle free tier restarts), dedupes repeat watches, multi-user safe.

## Cache lifecycle (replaces current eager-delete)

- **Remove** the delete-after-`watch()` logic in `download.py`/`pipeline` — `get_frames` needs the file later.
- **TTL + LRU sweep** on each `watch()` call: evict dirs older than N minutes, and evict oldest when total cache exceeds a hard size cap (small — Oracle disk). Downloads count against the cap; referenced local files don't.
- Cache-miss on `get_frames` is expected and handled (re-watch).

## Open / deferred
- Size cap + TTL exact values — tune to Oracle disk.
- `full` (native-video) provider — separate provider class behind the existing `VLMProvider` seam; only wired when a video-native model is configured.
- Concurrency: two `watch()` calls on the same new URL — dedupe by `video_id` dir lock.
