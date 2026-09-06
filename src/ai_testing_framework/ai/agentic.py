from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from typing import Any


class AgenticAI:
    """Optional GPT-backed planning/data generation with deterministic fallback."""

    def __init__(self, provider: str = "none", model: str = "gpt-4o-mini") -> None:
        self.provider = provider.lower()
        self.model = model
        self.client = None
        if self.provider == "openai" and os.getenv("OPENAI_API_KEY"):
            from openai import OpenAI
            self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def _json(self, system: str, user: str) -> dict[str, Any] | list[Any]:
        if self.client is None:
            raise RuntimeError("OpenAI provider is unavailable")
        response = self.client.chat.completions.create(
            model=self.model, temperature=0.1,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        raw = (response.choices[0].message.content or "{}").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        return json.loads(raw)

    def plan(self, app_description: str, workflows: list[str] | None = None) -> dict[str, Any]:
        workflows = workflows or []
        if self.client:
            return self._json(
                "You are a senior QA architect. Return only JSON with key scenarios, an array of runnable browser scenarios. Each scenario has name, goal, steps and validations. Do not invent APIs or UI selectors; describe actions semantically.",
                json.dumps({"app_description": app_description, "known_workflows": workflows}, ensure_ascii=False),
            )
        scenarios = []
        for i, workflow in enumerate(workflows or ["Open the application and verify its primary content"], 1):
            scenarios.append({"name": f"Workflow {i}: {workflow}", "goal": workflow, "steps": [workflow], "validations": ["The workflow completes without an error"]})
        return {"scenarios": scenarios}

    def generate_data(self, fields: list[dict[str, Any]], count: int = 1) -> list[dict[str, Any]]:
        count = max(1, min(int(count), 100))
        if self.client:
            result = self._json(
                "Generate realistic but fictional test data. Return only JSON with key data containing an array. Match field names/types/context. Never use real people or secrets.",
                json.dumps({"fields": fields, "count": count}, ensure_ascii=False),
            )
            return list(result.get("data", [])) if isinstance(result, dict) else list(result)
        today = date.today()
        rows = []
        for i in range(count):
            row = {}
            for field in fields:
                name = str(field.get("name", "field")); kind = str(field.get("type", "text")).lower(); context = str(field.get("context", "")).lower()
                low = name.lower() + " " + context
                if "email" in low: value = f"test.user{i+1}@example.test"
                elif "date" in low: value = (today + timedelta(days=i + 1)).isoformat()
                elif kind in {"number", "integer"}: value = i + 1
                elif "name" in low: value = f"Test User {i+1}"
                elif "phone" in low: value = f"+1555000{1000+i:04d}"
                elif "url" in low: value = "https://example.test"
                else: value = f"Test value {i+1}"
                row[name] = value
            rows.append(row)
        return rows

    @staticmethod
    def extract_fields(page_info: dict[str, Any]) -> list[dict[str, Any]]:
        fields = []
        for item in page_info.get("inputs", []):
            fields.append({"name": item.get("name") or item.get("id") or item.get("placeholder") or "field", "type": item.get("type") or "text", "context": item.get("label") or item.get("placeholder") or ""})
        return fields
