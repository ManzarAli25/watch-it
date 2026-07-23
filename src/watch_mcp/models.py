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


def seconds_to_ts(seconds: float) -> str:
    """Format seconds as MM:SS (or HH:MM:SS past an hour)."""
    seconds = max(0, int(round(seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
