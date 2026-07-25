"""Turn sampled frames into a validated Timeline via the VLM provider."""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from ..models import Cost, Timeline
from ..providers.base import Completion, Frame, VLMProvider

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)

SYSTEM_PROMPT = """You are Watch, the visual perception layer for an AI coding agent.
You are given ordered, timestamped frames sampled from a screen recording.

Produce a STRUCTURED TIMELINE of meaningful, semantic events — not a description
of every frame. Merge redundant frames. Focus on things a developer cares about:
page navigation, user interactions (clicks/typing), UI changes, console/terminal
errors, network failures, loading states, dialogs opening/closing, code editing.

Respond with ONLY a JSON object, no prose, no markdown fences, in this exact shape:
{
  "duration": "MM:SS",
  "events": [
    {"timestamp": "MM:SS", "type": "<one of: navigation, interaction, error, ui_change, terminal, network, loading, dialog, code_edit, other>", "description": "..."}
  ]
}
Timestamps must be MM:SS (or HH:MM:SS). Use the frame timestamps provided."""

_REPAIR_SUFFIX = (
    "\n\nYour previous reply was not valid JSON matching the schema. "
    "Reply again with ONLY the JSON object, nothing else."
)


def _default_user_prompt(extra: str | None, duration: str | None) -> str:
    base = "Analyze these frames and return the timeline JSON."
    if duration:
        base += f" The full video is {duration} long."
    if extra:
        base += f" The developer specifically asks: {extra}"
    return base


async def extract_timeline(
    provider: VLMProvider,
    frames: list[Frame],
    *,
    prompt: str | None = None,
    duration: str | None = None,
    model: str | None = None,
) -> tuple[Timeline, Cost]:
    """Sampled-frames path: call `describe`, parse, retry once on bad JSON.

    `duration` (if given) is treated as ground truth and overwrites whatever the
    model reports — the model only sees sampled frames, not the video's true end.
    Returns the timeline plus aggregated usage/cost.
    """
    user = _default_user_prompt(prompt, duration)

    async def describe(system: str) -> Completion:
        return await provider.describe(frames, system, user)

    return await _parse_or_repair(describe, duration, model)


async def extract_timeline_from_video(
    provider: VLMProvider,
    video: bytes,
    mime: str,
    *,
    prompt: str | None = None,
    duration: str | None = None,
    model: str | None = None,
) -> tuple[Timeline, Cost]:
    """Native-video path (mode='full'): call `describe_video`, parse, retry once."""
    user = _default_user_prompt(prompt, duration)

    async def describe(system: str) -> Completion:
        return await provider.describe_video(video, mime, system, user)

    return await _parse_or_repair(describe, duration, model)


def _add(a: int | None, b: int | None) -> int | None:
    if a is None and b is None:
        return None
    return (a or 0) + (b or 0)


async def _parse_or_repair(describe, duration: str | None, model: str | None) -> tuple[Timeline, Cost]:
    """Run a describe-callable, parse the JSON, retry once with a stricter prompt.

    Accumulates cost/tokens across every call made (including the repair retry).
    """
    cost = Cost(model=model)

    def account(c: Completion) -> None:
        cost.calls += 1
        if c.cost_usd is not None:
            cost.usd = (cost.usd or 0.0) + c.cost_usd
        cost.prompt_tokens = _add(cost.prompt_tokens, c.prompt_tokens)
        cost.completion_tokens = _add(cost.completion_tokens, c.completion_tokens)

    completion = await describe(SYSTEM_PROMPT)
    account(completion)
    timeline = _try_parse(completion.text)
    if timeline is None:
        completion = await describe(SYSTEM_PROMPT + _REPAIR_SUFFIX)
        account(completion)
        timeline = _try_parse(completion.text)

    if timeline is None:
        raise ValueError(
            f"Model did not return valid timeline JSON.\nLast output:\n{completion.text[:1000]}"
        )

    if duration:
        timeline.duration = duration
    return timeline, cost


def _try_parse(raw: str) -> Timeline | None:
    text = raw.strip()
    # Strip markdown fences if present.
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
    match = _JSON_BLOCK.search(text)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return Timeline.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        return None
