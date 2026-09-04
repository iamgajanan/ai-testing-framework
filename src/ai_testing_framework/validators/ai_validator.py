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

    _GENERIC_TERMS = {
        "a", "an", "the", "and", "or", "is", "are", "be", "this", "that",
        "response", "result", "page", "text", "content", "should", "mention",
        "mentions", "mentioning", "relevant", "relevance", "search", "check",
        "whether", "expected", "condition", "valid", "validates", "validation",
        "contains", "containing", "include", "includes", "including",
    }

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

    @classmethod
    def _heuristic(cls, response: str, expected: str) -> Dict[str, Any]:
        """Provide a deterministic, conservative fallback when no AI provider is available."""
        actual = response or ""
        exp = expected or ""
        dollar = re.search(r"\$\s*[\d,]+(?:\.\d{2})?", actual)
        if any(word in exp.lower() for word in ("monetary", "dollar amount", "money")):
            passed = bool(dollar) and float(dollar.group(0).replace("$", "").replace(",", "")) > 0
            return {
                "pass": passed,
                "reason": "Found a positive monetary value" if passed else "No positive monetary value found",
                "confidence": 0.82,
            }
        if not exp:
            return {
                "pass": bool(actual.strip()),
                "reason": "Response is non-empty" if actual.strip() else "Response is empty",
                "confidence": 0.60,
            }

        # Ignore generic test-language words and match the meaningful terms in
        # the expected condition. This makes phrases such as "A response
        # mentioning OpenAI" evaluate against the meaningful term "OpenAI".
        terms = [
            term for term in re.findall(r"[A-Za-z0-9@.$-]{3,}", exp.lower())
            if term not in cls._GENERIC_TERMS
        ]
        if not terms:
            return {
                "pass": bool(actual.strip()),
                "reason": "Expected condition has no specific terms; response is non-empty" if actual.strip() else "Response is empty",
                "confidence": 0.60,
            }

        actual_lower = actual.lower()
        hits = sum(1 for term in terms if term in actual_lower)
        required = max(1, (len(terms) + 1) // 2)
        passed = hits >= required
        return {
            "pass": passed,
            "reason": f"Matched {hits}/{len(terms)} meaningful expected terms",
            "confidence": 0.70 if passed else 0.40,
        }
