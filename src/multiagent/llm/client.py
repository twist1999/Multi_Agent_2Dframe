from __future__ import annotations

import json
import re
import requests

from ..config import AgentModelConfig


class LLMClient:
    def _chat(self, prompt: str, model_config: AgentModelConfig) -> str:
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
        }
        response = requests.post(
            f"{model_config.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
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

    def run_structured(self, agent_name: str, prompt: str, model_config: AgentModelConfig) -> dict:
        text = self._chat(prompt, model_config)
        json_text = self._extract_json_text(text)
        return json.loads(json_text)

    def run_text(self, agent_name: str, prompt: str, model_config: AgentModelConfig) -> str:
        return self._chat(prompt, model_config)
