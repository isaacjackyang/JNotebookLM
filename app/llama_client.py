from __future__ import annotations

from typing import Any

import requests

from app.config import Settings


class LlamaClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def health(self) -> dict[str, Any]:
        try:
            response = requests.get(
                f"{self.settings.llama_base_url.rstrip('/')}/v1/models",
                headers={"Authorization": f"Bearer {self.settings.llama_api_key}"},
                timeout=8,
            )
            response.raise_for_status()
            payload = response.json()
            models = [item.get("id", "") for item in payload.get("data", [])]
            return {
                "configured": True,
                "reachable": True,
                "models": models,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "configured": bool(self.settings.llama_base_url),
                "reachable": False,
                "models": [],
                "error": str(exc),
            }

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        payload: dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
        }
        if self.settings.llama_model:
            payload["model"] = self.settings.llama_model

        response = requests.post(
            f"{self.settings.llama_base_url.rstrip('/')}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.settings.llama_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.settings.llama_timeout,
        )
        response.raise_for_status()
        body = response.json()
        choices = body.get("choices", [])
        if not choices:
            raise RuntimeError("llama.cpp returned no choices")
        return choices[0]["message"]["content"].strip()

