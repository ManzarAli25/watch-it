import pytest

from watch_mcp.pipeline.events import extract_timeline
from watch_mcp.providers.base import Completion, Frame, VLMProvider

FRAMES = [Frame(timestamp="00:01", image_b64="x"), Frame(timestamp="00:05", image_b64="y")]


class ScriptedProvider(VLMProvider):
    """Returns queued responses in order, one per describe() call."""

    def __init__(self, *responses: str, cost: float | None = None) -> None:
        self._responses = list(responses)
        self._cost = cost
        self.calls = 0

    async def describe(self, frames, system, user):
        self.calls += 1
        return Completion(
            text=self._responses.pop(0),
            cost_usd=self._cost,
            prompt_tokens=10,
            completion_tokens=5,
        )


async def test_parses_clean_json():
    good = '{"duration":"00:05","events":[{"timestamp":"00:01","type":"navigation","description":"a"}]}'
    p = ScriptedProvider(good)
    tl, cost = await extract_timeline(p, FRAMES)
    assert tl.duration == "00:05"
    assert p.calls == 1
    assert cost.calls == 1


async def test_strips_markdown_fence():
    fenced = '```json\n{"duration":"00:05","events":[]}\n```'
    tl, _ = await extract_timeline(ScriptedProvider(fenced), FRAMES)
    assert tl.events == []


async def test_repairs_on_second_try():
    bad = "sorry, here is your answer"
    good = '{"duration":"00:05","events":[]}'
    p = ScriptedProvider(bad, good)
    tl, cost = await extract_timeline(p, FRAMES)
    assert tl.duration == "00:05"
    assert p.calls == 2
    assert cost.calls == 2  # both attempts accounted for


async def test_cost_accumulates():
    good = '{"duration":"00:05","events":[]}'
    p = ScriptedProvider("bad", good, cost=0.001)
    _, cost = await extract_timeline(p, FRAMES, model="test/model")
    assert cost.usd == pytest.approx(0.002)  # two calls * 0.001
    assert cost.prompt_tokens == 20
    assert cost.model == "test/model"


async def test_raises_when_both_fail():
    p = ScriptedProvider("nope", "still nope")
    with pytest.raises(ValueError):
        await extract_timeline(p, FRAMES)
