from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

from playwright.sync_api import Page


class AIElementLocator:
    """Resolve natural-language element descriptions to unique Playwright selectors."""

    SYSTEM_PROMPT = (
        "You map a natural-language web element description to one candidate from a live DOM. "
        "Return JSON only: {\"index\": integer, \"reason\": string, \"confidence\": number}. "
        "Never invent an index. Prefer the candidate whose accessible name, role, placeholder, "
        "name, id, or visible text best matches the description."
    )

    def __init__(self, provider: str = "none", model: str = "gpt-4o-mini") -> None:
        self.provider = provider.lower()
        self.model = model
        self.client = None
        api_key = os.getenv("OPENAI_API_KEY")
        if self.provider == "openai" and api_key:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)

    def find_element(self, page: Page, description: str):
        """Return a unique Playwright Locator for a natural-language description."""
        if not description or not description.strip():
            raise ValueError("Element description cannot be empty")

        candidates = self._collect_candidates(page)
        if self.client and candidates:
            index = self._ai_index(description, candidates)
            if index is not None and 0 <= index < len(candidates):
                locator = self._locator_for_candidate(page, candidates[index])
                if locator is not None:
                    return locator

        locator = self._heuristic(page, description)
        if locator is not None:
            return locator
        raise ValueError(f"Could not locate element from description: {description}")

    def _ai_index(self, description: str, candidates: list[dict[str, Any]]) -> Optional[int]:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"description": description, "candidates": candidates[:100]},
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
            data = json.loads(response.choices[0].message.content or "{}")
            return int(data["index"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, IndexError):
            return None
        except Exception:
            return None

    @staticmethod
    def _collect_candidates(page: Page) -> list[dict[str, Any]]:
        return page.locator("button, input, textarea, select, a, [role]").evaluate_all(
            """els => els.slice(0, 100).map((e, i) => ({
                index:i,
                tag:e.tagName.toLowerCase(),
                text:(e.innerText || e.textContent || '').trim().slice(0, 160),
                id:e.id || '',
                name:e.getAttribute('name') || '',
                role:e.getAttribute('role') || '',
                type:e.getAttribute('type') || '',
                aria_label:e.getAttribute('aria-label') || '',
                placeholder:e.getAttribute('placeholder') || ''
            }))"""
        )

    @staticmethod
    def _locator_for_candidate(page: Page, candidate: dict[str, Any]):
        index = int(candidate["index"])
        base = page.locator("button, input, textarea, select, a, [role]").nth(index)
        try:
            if base.count() == 1:
                return base
        except Exception:
            pass
        return None

    @classmethod
    def _heuristic(cls, page: Page, description: str):
        d = description.lower().strip()
        try:
            if "button" in d or "submit" in d:
                words = [w for w in re.findall(r"[a-z0-9_-]+", d) if w not in {"the", "a", "an", "button", "submit"}]
                for word in words:
                    locator = page.get_by_role("button", name=re.compile(re.escape(word), re.I))
                    if locator.count() == 1:
                        return locator
                locator = page.get_by_role("button")
                if locator.count() == 1:
                    return locator

            if "email" in d:
                locator = page.locator("input[type='email'], input[name*='email' i], input[placeholder*='email' i]")
                if locator.count() == 1:
                    return locator
            if "password" in d:
                locator = page.locator("input[type='password']")
                if locator.count() == 1:
                    return locator
            if "search" in d:
                locator = page.locator("input[type='search'], input[placeholder*='search' i], input[name*='search' i]")
                if locator.count() == 1:
                    return locator

            locator = page.get_by_text(re.compile(re.escape(description), re.I))
            if locator.count() == 1:
                return locator
        except Exception:
            return None
        return None
