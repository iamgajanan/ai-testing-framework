from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

from openai import OpenAI
from playwright.sync_api import Page


class SelfHealing:
    """Recover from broken selectors by finding a semantically similar DOM element."""

    SYSTEM_PROMPT = (
        "You are a web test self-healing agent. A selector failed on a live page. "
        "Choose exactly one candidate that most likely represents the same element. "
        "Return JSON only: {index: integer, reason: string, confidence: number}. "
        "Never invent an index. Prefer stable identity and semantic evidence: "
        "id, name, aria-label, role, placeholder, type, visible text, and nearby context."
    )

    def __init__(self, provider: str = "openai", model: str = "gpt-4o-mini", min_confidence: float = 0.70) -> None:
        self.provider = provider.lower()
        self.model = model
        self.min_confidence = min_confidence
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if self.provider == "openai" and api_key else None
        self.last_reason = ""
        self.last_confidence = 0.0

    def heal_selector(self, page: Page, failed_selector: str, description: str = "") -> Optional[str]:
        """Return a replacement selector when confidence is high enough."""
        candidates = self._collect_candidates(page)
        if not candidates:
            return None

        if self.client:
            result = self._ai_select(failed_selector, description, candidates)
            index = result.get("index")
            confidence = self._confidence(result.get("confidence"))
            self.last_reason = str(result.get("reason", ""))
            self.last_confidence = confidence
            if isinstance(index, int) and 0 <= index < len(candidates) and confidence >= self.min_confidence:
                selector = self._stable_selector(candidates[index])
                if selector and self._unique(page, selector):
                    return selector

        selector, reason = self._heuristic(page, failed_selector, description, candidates)
        self.last_reason = reason
        self.last_confidence = 0.75 if selector else 0.0
        return selector

    def _ai_select(self, failed_selector: str, description: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps({
                            "failed_selector": failed_selector,
                            "description": description,
                            "candidates": candidates[:100],
                        }, ensure_ascii=False),
                    },
                ],
            )
            return json.loads(response.choices[0].message.content or "{}")
        except Exception:
            return {}

    @staticmethod
    def _confidence(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _collect_candidates(page: Page) -> list[dict[str, Any]]:
        return page.locator("button, input, textarea, select, a, [role]").evaluate_all(
            """els => els.slice(0, 100).map((e, i) => ({
                index:i, tag:e.tagName.toLowerCase(), text:(e.innerText || e.textContent || '').trim().slice(0,160),
                id:e.id || '', name:e.getAttribute('name') || '', role:e.getAttribute('role') || '',
                type:e.getAttribute('type') || '', aria_label:e.getAttribute('aria-label') || '',
                placeholder:e.getAttribute('placeholder') || ''
            }))"""
        )

    @staticmethod
    def _stable_selector(candidate: dict[str, Any]) -> str:
        if candidate.get("id"):
            return "#" + candidate["id"]
        if candidate.get("name"):
            return f"[name={json.dumps(candidate['name'])}]"
        if candidate.get("aria_label"):
            return f"[aria-label={json.dumps(candidate['aria_label'])}]"
        if candidate.get("role") and candidate.get("text"):
            return f"[role={json.dumps(candidate['role'])}]:has-text({json.dumps(candidate['text'])})"
        return ""

    @staticmethod
    def _unique(page: Page, selector: str) -> bool:
        try:
            return page.locator(selector).count() == 1
        except Exception:
            return False

    @classmethod
    def _heuristic(cls, page: Page, failed_selector: str, description: str, candidates: list[dict[str, Any]]):
        text = f"{description} {failed_selector}".lower()
        words = [w for w in re.findall(r"[a-z0-9_-]+", text) if len(w) >= 3 and w not in {"the", "input", "button", "field"}]
        scored = []
        for candidate in candidates:
            haystack = " ".join(str(candidate.get(k, "")) for k in ("text", "id", "name", "role", "type", "aria_label", "placeholder")).lower()
            score = sum(1 for word in words if word in haystack)
            scored.append((score, candidate))
        scored.sort(key=lambda item: item[0], reverse=True)
        if not scored or scored[0][0] <= 0:
            return None, "No semantically similar candidate found"
        selector = cls._stable_selector(scored[0][1])
        if selector and cls._unique(page, selector):
            return selector, f"Recovered selector using {scored[0][0]} matching semantic term(s)"
        return None, "Best healing candidate did not produce a unique stable selector"
