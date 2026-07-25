"""OpenAI-compatible vision provider.

Works against any server exposing POST {base_url}/chat/completions with the
OpenAI multimodal message schema: local vLLM (Qwen2.5-VL), DashScope compat
mode, OpenRouter, etc. Model-agnostic per the project scope.

Native video (mode='full') uses the `video_url` content type with a base64
data URI. On OpenRouter this needs a video-capable model — e.g. qwen/qwen3.5-*,
qwen/qwen3.6-*, or xiaomi/mimo-v2.5 (the qwen2.5-vl / qwen3-vl series are
image-only).
"""

from __future__ import annotations

import base64

import httpx

from ..config import Settings
from .base import Frame, VLMProvider


class OpenAICompatProvider(VLMProvider):
    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.vlm_base_url.rstrip("/")
        self._model = settings.vlm_model
        self._api_key = settings.vlm_api_key
        self._timeout = settings.vlm_timeout
        self._max_tokens = settings.vlm_max_tokens

    async def describe(self, frames: list[Frame], system: str, user: str) -> str:
        content: list[dict] = [{"type": "text", "text": user}]
        for f in frames:
            content.append(
                {
                    "type": "text",
                    "text": f"[frame @ {f.timestamp}]",
                }
            )
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{f.mime};base64,{f.image_b64}"},
                }
            )

        return await self._complete(system, content)

    async def describe_video(self, video: bytes, mime: str, system: str, user: str) -> str:
        b64 = base64.b64encode(video).decode("ascii")
        content = [
            {"type": "text", "text": user},
            {"type": "video_url", "video_url": {"url": f"data:{mime};base64,{b64}"}},
        ]
        return await self._complete(system, content)

    async def _complete(self, system: str, content: list[dict]) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "temperature": 0.0,
            "max_tokens": self._max_tokens,
        }
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        return data["choices"][0]["message"]["content"]
