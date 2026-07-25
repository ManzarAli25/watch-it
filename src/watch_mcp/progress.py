"""Progress plumbing for long-running tool calls.

The pipeline's heavy stages (yt-dlp, PySceneDetect, OpenCV) run in worker
threads, so they cannot await ``ctx.report_progress`` themselves. Instead they
write into a `ProgressState` and a heartbeat task on the event loop drains it at
a fixed interval. That keeps notifications flowing even while a stage is silent,
which is what stops MCP clients tripping their idle timeouts.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field

#: Stage name -> (start%, end%) of the overall progress bar. Rough but monotonic.
STAGE_SPAN: dict[str, tuple[float, float]] = {
    "starting": (0.0, 1.0),
    "resolving": (1.0, 5.0),
    "downloading": (5.0, 45.0),
    "probing": (45.0, 50.0),
    "detecting scenes": (50.0, 62.0),
    "extracting frames": (62.0, 70.0),
    "analyzing": (70.0, 99.0),
    "done": (100.0, 100.0),
}


@dataclass
class ProgressState:
    """Mutable stage/percent shared between worker threads and the heartbeat."""

    stage: str = "starting"
    percent: float = 0.0
    detail: str = ""
    _peak: float = field(default=0.0, repr=False)

    def set(self, stage: str, fraction: float = 0.0, detail: str = "") -> None:
        """Mark `stage` as `fraction` (0..1) complete."""
        lo, hi = STAGE_SPAN.get(stage, (self.percent, self.percent))
        pct = lo + (hi - lo) * max(0.0, min(1.0, fraction))
        self.stage = stage
        self.detail = detail
        # Never move backwards: clients render a bar, and a stage that finishes
        # early shouldn't rewind when the next one starts at a lower estimate.
        self._peak = max(self._peak, pct)
        self.percent = self._peak

    @property
    def message(self) -> str:
        return f"{self.stage} — {self.detail}" if self.detail else self.stage


@contextlib.asynccontextmanager
async def heartbeat(ctx, state: ProgressState, interval: float = 5.0):
    """Report `state` to the client every `interval` seconds until the block exits.

    `ctx` may be None (direct/CLI use), in which case this is a no-op.
    """
    if ctx is None:
        yield state
        return

    async def _pump() -> None:
        while True:
            await asyncio.sleep(interval)
            with contextlib.suppress(Exception):
                # A client that didn't send a progressToken makes this a no-op;
                # a disconnected one raises — neither should kill the analysis.
                await ctx.report_progress(
                    progress=state.percent, total=100.0, message=state.message
                )

    task = asyncio.create_task(_pump())
    try:
        yield state
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
