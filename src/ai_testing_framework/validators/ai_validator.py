from __future__ import annotations

import json
import os
import re
from typing import Any, Dict

from openai import OpenAI


class AIValidator:
    """Semantic test oracle with OpenAI and deterministic fallback support."""

    SYSTEM_PROMPT = (
        "You are a strict software-test oracle. Decide whether the actual web "
        "response satisfies the expected condition. Treat the expected condition "
        "as the acceptance criterion, not as a request to perform an action. "
        "Return only JSON with: pass (boolean), reason (short string), and "
        "confidence (number from 0 to 1)."
    )

    def __init__(self, provider: str = "openai", model: str = "gpt-4o-mini") -> None:
        self.provider = provider.lower()
        self.model = model
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if self.provider == "openai" and api_key else None

    def validate_response(self, response: str, expected: str, context: str = "") -> Dict[str, Any]:
        if self.provider == "none" or self.client is None:
            return self._heuristic(response, expected)

        try:
            result = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "actual_response": response or "",
                                "expected_condition": expected or "",
                                "validation_instruction": context or "",
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
            content = result.choices[0].message.content or "{}"
            return self._normalize_result(json.loads(self._extract_json(content)))
        except Exception as exc:
            return {
                "pass": False,
                "reason": f"AI validation failed: {exc}",
                "confidence": 0.0,
            }

    @staticmethod
    def _extract_json(content: str) -> str:
        """Accept normal JSON as well as JSON wrapped in a markdown code fence."""
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
            text = re.sub(r"\s*```$", "", text)
        return text.strip()

    @staticmethod
    def _normalize_result(result: Dict[str, Any]) -> Dict[str, Any]:
        passed = result.get("pass", result.get("passed", False))
        if isinstance(passed, str):
            passed = passed.strip().lower() in {"true", "yes", "pass", "passed"}

        confidence = result.get("confidence", 0.0)
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            confidence = 0.0

        return {
            "pass": bool(passed),
            "reason": str(result.get("reason", "No explanation returned by AI.")),
            "confidence": confidence,
        }

    @staticmethod
    def _heuristic(response: str, expected: str) -> Dict[str, Any]:
        actual = response or ""
        exp = expected or ""
        dollar = re.search(r"\$\s*[\d,]+(?:\.\d{2})?", actual)
        if any(word in exp.lower() for word in ("monetary", "dollar amount", "money")):
            passed = bool(dollar) and float(dollar.group(0).replace("$", "").replace(",", "")) > 0
            return {"pass": passed, "reason": "Found a positive monetary value" if passed else "No positive monetary value found", "confidence": 0.82}
        if not exp:
            return {"pass": bool(actual.strip()), "reason": "Response is non-empty" if actual.strip() else "Response is empty", "confidence": 0.60}
        key_terms = re.findall(r"[A-Za-z0-9@.$-]{3,}", exp.lower())
        hits = sum(1 for term in key_terms if term in actual.lower())
        passed = hits >= max(1, min(2, len(key_terms)))
        return {"pass": passed, "reason": f"Matched {hits}/{len(key_terms)} expected terms", "confidence": 0.65 if passed else 0.40}
