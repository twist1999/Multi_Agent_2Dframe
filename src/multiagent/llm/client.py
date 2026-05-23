from __future__ import annotations

import contextvars
import json
import re
import requests
from typing import Any, Callable

from ..config import AgentModelConfig


TokenUsageCallback = Callable[[dict[str, Any]], None]
_TOKEN_USAGE_CALLBACK: contextvars.ContextVar[TokenUsageCallback | None] = contextvars.ContextVar(
    "token_usage_callback",
    default=None,
)


def set_token_usage_callback(callback: TokenUsageCallback | None) -> contextvars.Token:
    return _TOKEN_USAGE_CALLBACK.set(callback)


def reset_token_usage_callback(token: contextvars.Token) -> None:
    _TOKEN_USAGE_CALLBACK.reset(token)


class LLMClient:
    def _chat(self, agent_name: str, prompt: str, model_config: AgentModelConfig, response_format: dict | None = None) -> str:
        headers = {
            "Authorization": f"Bearer {model_config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_config.model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": model_config.temperature,
            "max_tokens": 16384,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        response = requests.post(
            f"{model_config.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=300,
        )
        response.raise_for_status()
        try:
            data = response.json()
        except Exception:
            text_snippet = response.text[:500] if response.text else "(empty body)"
            raise RuntimeError(
                f"Failed to parse API response as JSON for agent '{agent_name}'. "
                f"Response status={response.status_code}, body preview: {text_snippet}"
            )
        usage = data.get("usage") or {}
        callback = _TOKEN_USAGE_CALLBACK.get()
        if callback:
            callback(
                {
                    "agent_name": agent_name,
                    "model": model_config.model_name,
                    "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                    "completion_tokens": int(usage.get("completion_tokens") or 0),
                    "total_tokens": int(usage.get("total_tokens") or 0),
                }
            )
        return data["choices"][0]["message"]["content"]

    def _extract_json_text(self, text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

        if cleaned.startswith("{") or cleaned.startswith("["):
            return cleaned

        match = re.search(r"(\{.*\}|\[.*\])", cleaned, flags=re.DOTALL)
        if match:
            return match.group(1).strip()
        return cleaned

    def _extract_code_text(self, text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:python|py)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()
        return cleaned

    def run_structured(self, agent_name: str, prompt: str, model_config: AgentModelConfig) -> dict:
        text = self._chat(agent_name, prompt, model_config)
        json_text = self._extract_json_text(text)
        return json.loads(json_text)

    def run_text(self, agent_name: str, prompt: str, model_config: AgentModelConfig) -> str:
        text = self._chat(agent_name, prompt, model_config)
        return self._extract_code_text(text)
