"""OpenAI-compatible vision provider.

Works against any server exposing POST {base_url}/chat/completions with the
OpenAI multimodal message schema: local vLLM (Qwen2.5-VL), DashScope compat
mode, OpenRouter, etc. Model-agnostic per the project scope.
"""

from __future__ import annotations

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
