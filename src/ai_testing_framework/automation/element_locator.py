from __future__ import annotations

import json
import os
from typing import Optional

from openai import OpenAI
from playwright.sync_api import Page


class AIElementLocator:
    """Resolve natural-language element descriptions when no selector is supplied."""

    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self.model = model
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

    def find_element(self, page: Page, description: str) -> Optional[str]:
        if not description:
            return None
        if not self.client:
            return self._heuristic(page, description)

        candidates = page.locator("button, input, textarea, select, a, [role]").evaluate_all(
            """els => els.slice(0, 100).map((e, i) => ({
                i, tag:e.tagName, text:(e.innerText || e.value || e.getAttribute('aria-label') || '').trim(),
                id:e.id, name:e.getAttribute('name'), role:e.getAttribute('role'), type:e.getAttribute('type')
            }))"""
        )
        prompt = f"""Choose the best candidate index for this web element description: {description!r}.
Return JSON only: {{\"index\": number}}. Candidates: {json.dumps(candidates, ensure_ascii=False)}"""
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You map natural language to a DOM candidate. Never invent an index."},
                {"role": "user", "content": prompt},
            ],
        )
        index = int(json.loads(response.choices[0].message.content or "{}")['index'])
        if index < 0 or index >= len(candidates):
            return None
        candidate = candidates[index]
        if candidate.get("id"):
            return f"#{candidate['id']}"
        if candidate.get("role") and candidate.get("text"):
            return f"[role='{candidate['role']}']"
        return None

    @staticmethod
    def _heuristic(page: Page, description: str) -> Optional[str]:
        d = description.lower()
        if "button" in d:
            label = d.replace("button", "").strip()
            if label:
                return f"button:has-text(\"{label}\")"
            return "button"
        if "email" in d:
            return "input[type='email'], input[name*='email' i], input[placeholder*='email' i]"
        if "password" in d:
            return "input[type='password']"
        if "search" in d:
            return "input[type='search'], input[placeholder*='search' i]"
        return None
