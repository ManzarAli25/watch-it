"""Structured timeline data models — the contract returned to the agent."""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, Field, field_validator

_TS_RE = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")


class EventType(str, Enum):
    NAVIGATION = "navigation"
    INTERACTION = "interaction"
    ERROR = "error"
    UI_CHANGE = "ui_change"
    TERMINAL = "terminal"
    NETWORK = "network"
    LOADING = "loading"
    DIALOG = "dialog"
    CODE_EDIT = "code_edit"
    OTHER = "other"

    @classmethod
    def _missing_(cls, value: object) -> "EventType":
        # Be lenient with model output: unknown/None types collapse to OTHER.
        return cls.OTHER


class Event(BaseModel):
    timestamp: str = Field(description="Event time as MM:SS or HH:MM:SS.")
    type: EventType = EventType.OTHER
    description: str = Field(description="Semantic description of what happened.")

    @field_validator("timestamp")
    @classmethod
    def _check_ts(cls, v: str) -> str:
        v = v.strip()
        if not _TS_RE.match(v):
            raise ValueError(f"timestamp must be MM:SS or HH:MM:SS, got {v!r}")
        return v


class Timeline(BaseModel):
    duration: str = Field(description="Total video duration as MM:SS or HH:MM:SS.")
    events: list[Event] = Field(default_factory=list)


class Mode(str, Enum):
    """How `watch` perceives the video."""

    SAMPLE = "sample"  # scene-detect + frame sampling + VLM → timeline (default, cheap).
    FULL = "full"      # native-video model (scales with duration).
    MANUAL = "manual"  # no AI: resolve + cache only; Claude drives via get_frames.


class WatchResult(BaseModel):
    """What the `watch` tool returns."""

    video_id: str = Field(description="Handle for get_frames; content-addressed cache key.")
    duration: str = Field(description="Total video duration as MM:SS or HH:MM:SS.")
    events: list[Event] = Field(
        default_factory=list,
        description="Semantic timeline; empty when mode=manual.",
    )


def seconds_to_ts(seconds: float) -> str:
    """Format seconds as MM:SS (or HH:MM:SS past an hour)."""
    seconds = max(0, int(round(seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def ts_to_seconds(ts: str | float | int) -> float:
    """Parse MM:SS / HH:MM:SS (or a raw seconds number) into float seconds."""
    if isinstance(ts, (int, float)):
        return float(ts)
    parts = ts.strip().split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError as e:
        raise ValueError(f"Bad timestamp {ts!r}; expected MM:SS or HH:MM:SS.") from e
    if len(nums) == 1:
        return nums[0]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    raise ValueError(f"Bad timestamp {ts!r}; expected MM:SS or HH:MM:SS.")
