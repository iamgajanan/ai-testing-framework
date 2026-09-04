from __future__ import annotations

import json
import os
import re
from typing import Any, Dict

from openai import OpenAI


class AIValidator:
    def __init__(self, provider: str = "openai", model: str = "gpt-4o-mini") -> None:
        self.provider = provider
        self.model = model
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if provider == "openai" and os.getenv("OPENAI_API_KEY") else None

    def validate_response(self, response: str, expected: str, context: str = "") -> Dict[str, Any]:
        if not self.client:
            return self._heuristic(response, expected)
        result = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You are a strict software-test oracle. Decide whether the actual response satisfies the expected condition. Return JSON with pass:boolean, reason:string, confidence:number from 0 to 1.",
                },
                {
                    "role": "user",
                    "content": json.dumps({"actual": response, "expected": expected, "context": context}, ensure_ascii=False),
                },
            ],
        )
        return json.loads(result.choices[0].message.content or "{}")

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
