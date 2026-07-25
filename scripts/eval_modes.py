"""Batch-evaluate Watch's `sample` vs `full` mode against QA ground truth.

Input CSV must have columns:
    video_url, reproduction_steps_ground_truth

For each row the script:
  1. Warms the cache once (mode=manual) so download time is excluded from timing.
  2. Runs `sample` and `full`, timing and costing each separately.
  3. Appends two columns, each a JSON object of shape:
         {"output": <timeline text>, "time_taken": <seconds>, "cost_of_call": <usd>}
     -> full_mode_result, sample_mode_result

A later step (Claude) reads the two `output` values, compares each to
`reproduction_steps_ground_truth`, and appends an accuracy_score column.

Usage:
    python scripts/eval_modes.py --input qa.csv --output qa_results.csv
    python scripts/eval_modes.py -i qa.csv -o out.csv --full-model xiaomi/mimo-v2.5

Env: reads .env for the sample model + OpenRouter key (see .env.example).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from watch_mcp.config import Settings, get_settings  # noqa: E402
from watch_mcp.models import Mode, WatchResult  # noqa: E402
from watch_mcp.pipeline import analyze  # noqa: E402

DEFAULT_QUERY = "Describe every user action and UI change as a reproduction timeline."


def _timeline_text(r: WatchResult) -> str:
    """Render events as a reproduction-style timeline for comparison."""
    return "\n".join(f"{e.timestamp} [{e.type.value}] {e.description}" for e in r.events)


def _cell(output: str, time_taken: float, cost: float | None, error: str | None = None) -> str:
    obj = {
        "output": output,
        "time_taken": round(time_taken, 2),
        "cost_of_call": cost,
    }
    if error:
        obj["error"] = error
    return json.dumps(obj, ensure_ascii=False)


async def _run_mode(url: str, mode: Mode, query: str, settings: Settings | None) -> str:
    start = time.perf_counter()
    try:
        r = await analyze(url, query=query, mode=mode, settings=settings)
        elapsed = time.perf_counter() - start
        cost = r.cost.usd if r.cost else None
        return _cell(_timeline_text(r), elapsed, cost)
    except Exception as e:  # noqa: BLE001 - per-row resilience
        elapsed = time.perf_counter() - start
        return _cell("", elapsed, None, error=f"{type(e).__name__}: {e}")


async def process_row(row: dict, query: str, full_settings: Settings) -> dict:
    url = (row.get("video_url") or "").strip()
    if not url:
        row["sample_mode_result"] = _cell("", 0.0, None, error="missing video_url")
        row["full_mode_result"] = _cell("", 0.0, None, error="missing video_url")
        return row

    # Warm the cache once so download time isn't charged to either mode's timing.
    try:
        await analyze(url, mode=Mode.MANUAL)
    except Exception as e:  # noqa: BLE001
        err = _cell("", 0.0, None, error=f"resolve failed: {type(e).__name__}: {e}")
        row["sample_mode_result"] = err
        row["full_mode_result"] = err
        return row

    row["sample_mode_result"] = await _run_mode(url, Mode.SAMPLE, query, None)
    row["full_mode_result"] = await _run_mode(url, Mode.FULL, query, full_settings)
    return row


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-i", "--input", required=True, help="Input CSV path.")
    ap.add_argument("-o", "--output", required=True, help="Output CSV path.")
    ap.add_argument("--query", default=DEFAULT_QUERY, help="Prompt sent to both modes.")
    ap.add_argument(
        "--full-model",
        default="qwen/qwen3.6-flash",
        help="Video-capable model for full mode (default qwen/qwen3.6-flash).",
    )
    args = ap.parse_args()

    base = get_settings()
    full_settings = Settings(vlm_model=args.full_model)
    print(f"sample model: {base.vlm_model}  |  full model: {args.full_model}")

    with open(args.input, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("No rows in input CSV.")
        return

    fieldnames = list(rows[0].keys())
    for col in ("sample_mode_result", "full_mode_result"):
        if col not in fieldnames:
            fieldnames.append(col)

    out_rows = []
    for i, row in enumerate(rows, 1):
        print(f"[{i}/{len(rows)}] {row.get('video_url', '')[:60]} ...", flush=True)
        out_rows.append(await process_row(row, args.query, full_settings))

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)

    print(f"\nWrote {len(out_rows)} rows -> {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
