import pytest
from pydantic import ValidationError

from watch_mcp.models import (
    Event,
    EventType,
    Mode,
    Timeline,
    WatchResult,
    seconds_to_ts,
    ts_to_seconds,
)


def test_timeline_roundtrip():
    tl = Timeline(
        duration="02:13",
        events=[
            Event(timestamp="00:05", type=EventType.NAVIGATION, description="opens localhost"),
            Event(timestamp="00:22", type=EventType.ERROR, description="HTTP 500"),
        ],
    )
    dumped = tl.model_dump_json()
    back = Timeline.model_validate_json(dumped)
    assert back == tl
    assert back.events[1].type is EventType.ERROR


def test_unknown_type_collapses_to_other():
    ev = Event(timestamp="00:01", type="teleport", description="x")
    assert ev.type is EventType.OTHER


def test_bad_timestamp_rejected():
    with pytest.raises(ValidationError):
        Event(timestamp="5 seconds", type="other", description="x")


@pytest.mark.parametrize(
    "secs,expected",
    [(0, "00:00"), (5, "00:05"), (65, "01:05"), (3661, "01:01:01")],
)
def test_seconds_to_ts(secs, expected):
    assert seconds_to_ts(secs) == expected


@pytest.mark.parametrize(
    "ts,expected",
    [("00:05", 5), ("01:05", 65), ("01:01:01", 3661), ("90", 90), (12.5, 12.5)],
)
def test_ts_to_seconds(ts, expected):
    assert ts_to_seconds(ts) == expected


def test_ts_to_seconds_rejects_garbage():
    with pytest.raises(ValueError):
        ts_to_seconds("banana")


def test_mode_values():
    assert {m.value for m in Mode} == {"sample", "full", "manual"}


def test_watch_result_defaults_empty_events():
    r = WatchResult(video_id="abc", duration="00:10")
    assert r.events == []
