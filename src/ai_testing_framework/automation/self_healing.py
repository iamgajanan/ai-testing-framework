from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

from playwright.sync_api import Page


class SelfHealing:
    """Recover from broken selectors by finding a semantically similar DOM element.

    Resolution order
    ----------------
    1. AI (OpenAI) – when provider=openai and OPENAI_API_KEY is set.
    2. Deterministic heuristic – always available as fallback.

    The heuristic scores candidates using:
    * words extracted from the failed selector (id fragments, class names)
    * words extracted from the natural-language description
    * tag-type penalties/boosts (a description mentioning "button" should not
      resolve to an <input>; a description mentioning "input"/"field" should
      not resolve to a <button>)
    * uniqueness check via Playwright
    """

    SYSTEM_PROMPT = (
        "You are a web test self-healing agent. A CSS selector failed on a live page. "
        "Choose exactly one candidate that most likely represents the SAME element. "
        "Return JSON only: {\"index\": integer, \"reason\": string, \"confidence\": number}. "
        "Never invent an index outside the list. Prefer stable identity evidence: "
        "id, name, aria-label, role, placeholder, type, visible text."
    )

    def __init__(
        self,
        provider: str = "none",
        model: str = "gpt-4o-mini",
        min_confidence: float = 0.70,
    ) -> None:
        self.provider = provider.lower()
        self.model = model
        self.min_confidence = min_confidence
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = None
        if self.provider == "openai" and api_key:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
        self.last_reason = ""
        self.last_confidence = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def heal_selector(
        self, page: Page, failed_selector: str, description: str = ""
    ) -> Optional[str]:
        """Return a replacement selector, or None when healing is not possible."""
        candidates = self._collect_candidates(page)
        if not candidates:
            return None

        if self.client:
            result = self._ai_select(failed_selector, description, candidates)
            index = result.get("index")
            confidence = self._confidence(result.get("confidence"))
            self.last_reason = str(result.get("reason", ""))
            self.last_confidence = confidence
            if (
                isinstance(index, int)
                and 0 <= index < len(candidates)
                and confidence >= self.min_confidence
            ):
                selector = self._stable_selector(candidates[index])
                if selector and self._unique(page, selector):
                    return selector

        # Deterministic fallback
        selector, reason = self._heuristic(page, failed_selector, description, candidates)
        self.last_reason = reason
        self.last_confidence = 0.75 if selector else 0.0
        return selector

    # ------------------------------------------------------------------
    # AI selection
    # ------------------------------------------------------------------

    def _ai_select(
        self,
        failed_selector: str,
        description: str,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
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
                            {
                                "failed_selector": failed_selector,
                                "description": description,
                                "candidates": candidates[:80],
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
            return json.loads(response.choices[0].message.content or "{}")
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Heuristic selection
    # ------------------------------------------------------------------

    # Stop-words that add noise rather than signal
    _STOP = frozenset(
        {"the", "click", "type", "fill", "enter", "press", "find", "get",
         "using", "with", "for", "and", "or", "a", "an", "of", "in", "on"}
    )

    # Tag categories for type-penalty
    _INPUT_TAGS = frozenset({"input", "textarea"})
    _BUTTON_TAGS = frozenset({"button", "a"})
    _SELECT_TAGS = frozenset({"select"})

    @classmethod
    def _heuristic(
        cls,
        page: Page,
        failed_selector: str,
        description: str,
        candidates: list[dict[str, Any]],
    ) -> tuple[Optional[str], str]:
        """Score each candidate and return the best unique match."""

        # --- build search tokens ---
        # From the failed selector: strip CSS syntax, keep meaningful fragments
        sel_words = set(re.findall(r"[a-z0-9_-]{2,}", failed_selector.lower()))
        sel_words -= cls._STOP

        # From the description
        desc_words = set(re.findall(r"[a-z0-9_-]{2,}", description.lower()))
        desc_words -= cls._STOP

        all_words = sel_words | desc_words

        # Infer expected element type from description / selector words
        wants_button = bool({"button", "submit", "btn", "link"} & (desc_words | sel_words))
        wants_input  = bool({"input", "field", "query", "text", "search", "email",
                              "password", "username", "name"} & (desc_words | sel_words))
        wants_select = bool({"select", "dropdown", "option"} & (desc_words | sel_words))

        # When description says "button" but also "search": the button intent wins
        # over the "search" text match against an input's placeholder.
        if wants_button:
            wants_input = False

        scored: list[tuple[float, dict[str, Any]]] = []
        for candidate in candidates:
            tag = candidate.get("tag", "")
            haystack = " ".join(
                str(candidate.get(k, ""))
                for k in ("text", "id", "name", "role", "type", "aria_label", "placeholder")
            ).lower()

            # Base score: word overlap
            score = sum(1.0 for w in all_words if w in haystack)

            # Tag-type boost/penalty
            if wants_button and tag in cls._BUTTON_TAGS:
                score += 2.0
            elif wants_button and tag in cls._INPUT_TAGS:
                score -= 2.0   # strongly penalise picking an input when we want a button

            if wants_input and tag in cls._INPUT_TAGS:
                score += 1.5
            elif wants_input and tag in cls._BUTTON_TAGS:
                score -= 1.5

            if wants_select and tag in cls._SELECT_TAGS:
                score += 2.0

            scored.append((score, candidate))

        scored.sort(key=lambda x: x[0], reverse=True)

        if not scored or scored[0][0] <= 0:
            return None, "No semantically similar candidate found"

        for score, candidate in scored:
            if score <= 0:
                break
            selector = cls._stable_selector(candidate)
            if selector and cls._unique(page, selector):
                return selector, (
                    f"Self-healed: matched {score:.1f} semantic term(s) "
                    f"[{candidate.get('tag')}#{candidate.get('id') or candidate.get('name') or '?'}]"
                )

        return None, "Best healing candidate did not produce a unique stable selector"

    # ------------------------------------------------------------------
    # DOM candidate collection
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_candidates(page: Page) -> list[dict[str, Any]]:
        return page.locator(
            "button, input, textarea, select, a, [role]"
        ).evaluate_all(
            """els => els.slice(0, 100).map((e, i) => ({
                index: i,
                tag: e.tagName.toLowerCase(),
                text: (e.innerText || e.textContent || '').trim().slice(0, 160),
                id: e.id || '',
                name: e.getAttribute('name') || '',
                role: e.getAttribute('role') || '',
                type: e.getAttribute('type') || '',
                aria_label: e.getAttribute('aria-label') || '',
                placeholder: e.getAttribute('placeholder') || ''
            }))"""
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _stable_selector(candidate: dict[str, Any]) -> str:
        if candidate.get("id"):
            return "#" + candidate["id"]
        if candidate.get("name"):
            return f"[name={json.dumps(candidate['name'])}]"
        if candidate.get("aria_label"):
            return f"[aria-label={json.dumps(candidate['aria_label'])}]"
        tag = candidate.get("tag", "")
        role = candidate.get("role", "")
        text = candidate.get("text", "")
        if role and text:
            return f"[role={json.dumps(role)}]:has-text({json.dumps(text[:60])})"
        if tag and text:
            return f"{tag}:has-text({json.dumps(text[:60])})"
        return ""

    @staticmethod
    def _unique(page: Page, selector: str) -> bool:
        try:
            return page.locator(selector).count() == 1
        except Exception:
            return False

    @staticmethod
    def _confidence(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0
