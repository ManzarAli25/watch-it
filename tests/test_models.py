import pytest
from pydantic import ValidationError

from watch_mcp.models import Event, EventType, Timeline, seconds_to_ts


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
