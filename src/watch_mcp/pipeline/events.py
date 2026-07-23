"""Turn sampled frames into a validated Timeline via the VLM provider."""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from ..models import Timeline
from ..providers.base import Frame, VLMProvider

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
) -> Timeline:
    """Call the provider, parse its output, retry once on malformed JSON.

    `duration` (if given) is treated as ground truth and overwrites whatever the
    model reports — the model only sees sampled frames, not the video's true end.
    """
    user = _default_user_prompt(prompt, duration)

    raw = await provider.describe(frames, SYSTEM_PROMPT, user)
    timeline = _try_parse(raw)
    if timeline is None:
        # One repair attempt.
        raw = await provider.describe(frames, SYSTEM_PROMPT + _REPAIR_SUFFIX, user)
        timeline = _try_parse(raw)

    if timeline is None:
        raise ValueError(f"Model did not return valid timeline JSON.\nLast output:\n{raw[:1000]}")

    if duration:
        timeline.duration = duration
    return timeline


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
