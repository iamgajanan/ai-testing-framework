"""AI-powered test generation — Phase 7.

Given a live URL, this module:
1. Uses Playwright to load the page
2. Extracts interactive elements (inputs, buttons, links, selects, tables)
   and page structure (title, headings, forms)
3. Prompts OpenAI to write a complete JSON test suite covering the page
4. Validates and writes the generated suite to disk

Without OpenAI it produces a deterministic baseline suite: element-presence
checks for every interactive element found, plus a page-load assertion.

CLI usage (added in cli.py):
    ai-test generate --url http://127.0.0.1:8000 \\
                     --output tests/generated_suite.json \\
                     --browser chromium \\
                     --ai-provider openai

Public API
----------
    generator = TestGenerator(provider="openai")
    suite_path = generator.generate(url, output_path, browser, base_url)
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


_DOM_EXTRACT_JS = """
(function() {
    var info = {
        title: document.title,
        headings: Array.from(document.querySelectorAll('h1,h2,h3'))
                       .slice(0, 6).map(h => h.innerText.trim()).filter(Boolean),
        forms: Array.from(document.querySelectorAll('form')).map(f => ({
            id: f.id || '',
            action: f.action || '',
            method: f.method || 'get'
        })),
        inputs: Array.from(document.querySelectorAll('input,textarea,select'))
                     .slice(0, 20).map(el => ({
            tag:         el.tagName.toLowerCase(),
            id:          el.id || '',
            name:        el.getAttribute('name') || '',
            type:        el.getAttribute('type') || '',
            placeholder: el.getAttribute('placeholder') || '',
            label:       (document.querySelector('label[for="' + el.id + '"]') || {}).innerText || ''
        })),
        buttons: Array.from(document.querySelectorAll('button,input[type=submit],input[type=button]'))
                      .slice(0, 10).map(b => ({
            tag:  b.tagName.toLowerCase(),
            id:   b.id || '',
            text: (b.innerText || b.value || '').trim(),
            type: b.getAttribute('type') || ''
        })),
        links: Array.from(document.querySelectorAll('a[href]'))
                    .slice(0, 10).map(a => ({
            text: a.innerText.trim(),
            href: a.getAttribute('href') || ''
        })),
        tables: Array.from(document.querySelectorAll('table')).slice(0, 3).map(t => ({
            id:      t.id || '',
            headers: Array.from(t.querySelectorAll('th')).map(th => th.innerText.trim())
        }))
    };
    return info;
})()
"""

_SYSTEM_PROMPT = """\
You are an expert QA engineer. Given page structure extracted from a live web page,
write a complete JSON test suite that thoroughly tests the page's functionality.

The suite must use this exact JSON format:
{
  "test_suite": "<descriptive suite name>",
  "tests": [
    {
      "id": "GEN-001",
      "name": "<test name>",
      "url": "<relative URL like / or /table>",
      "steps": [
        {"action": "type",  "selector": "<css>", "value": "<value>"},
        {"action": "click", "selector": "<css>"},
        {"action": "wait",  "selector": "<css>", "timeout": 5000}
      ],
      "validations": [
        {"type": "element_present", "selector": "<css>"},
        {"type": "text_contains",   "selector": "<css>", "expected": "<text>"},
        {"type": "table_validation","selector": "table",
         "expected_columns": ["Col1","Col2"], "row_condition": "..."}
      ],
      "error_checks": ["console_errors"]
    }
  ]
}

Rules:
- Use real CSS selectors inferred from the element id/name/type shown.
  Prefer #id > [name=x] > [type=x] > tag.
- Cover: page load, form submission with valid data, table validation if present,
  key link navigation.
- Keep tests independent (each starts from a URL, no shared state).
- Return ONLY the JSON object, no markdown fences, no explanation.
"""


class TestGenerator:
    """Generate a JSON test suite for a given URL."""

    def __init__(self, provider: str = "none", model: str = "gpt-4o-mini") -> None:
        self.provider = provider.lower()
        self.model = model
        self.client = None
        if self.provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                from openai import OpenAI
                self.client = OpenAI(api_key=api_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        url: str,
        output_path: str,
        browser: str = "chromium",
        base_url: str = "",
    ) -> str:
        """Generate a test suite for *url* and write it to *output_path*.

        Returns the absolute path of the written file.
        """
        page_info = self._extract_page_info(url, browser, base_url)
        relative_url = self._relative(url, base_url)

        if self.client is not None:
            suite = self._ai_generate(page_info, relative_url)
        else:
            suite = self._heuristic_generate(page_info, relative_url)

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(suite, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(out.resolve())

    # ------------------------------------------------------------------
    # Page info extraction
    # ------------------------------------------------------------------

    def _extract_page_info(self, url: str, browser: str, base_url: str) -> dict[str, Any]:
        from playwright.sync_api import sync_playwright
        target = f"{base_url.rstrip('/')}/{url.lstrip('/')}" if base_url and url.startswith("/") else url
        with sync_playwright() as p:
            b = getattr(p, browser).launch(headless=True)
            page = b.new_page()
            try:
                page.goto(target, wait_until="domcontentloaded", timeout=15000)
                info = page.evaluate(_DOM_EXTRACT_JS)
                info["url"] = url
                info["target_url"] = target
                return info
            finally:
                b.close()

    # ------------------------------------------------------------------
    # AI generation
    # ------------------------------------------------------------------

    def _ai_generate(self, page_info: dict[str, Any], relative_url: str) -> dict[str, Any]:
        prompt = json.dumps({
            "url": relative_url,
            "page_info": page_info,
        }, ensure_ascii=False)

        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
        )
        raw = resp.choices[0].message.content or "{}"
        # Strip accidental markdown fences
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]

        suite = json.loads(raw)
        # Ensure required top-level keys
        if "test_suite" not in suite:
            suite["test_suite"] = page_info.get("title") or "Generated Suite"
        if "tests" not in suite:
            suite["tests"] = []
        return suite

    # ------------------------------------------------------------------
    # Deterministic heuristic generation
    # ------------------------------------------------------------------

    def _heuristic_generate(
        self, page_info: dict[str, Any], relative_url: str
    ) -> dict[str, Any]:
        """Produce a baseline suite without AI: page-load + element presence + table."""
        title = page_info.get("title") or "Generated Suite"
        tests: list[dict[str, Any]] = []

        # Test 1: page loads and key elements are present
        validations: list[dict[str, Any]] = []
        steps: list[dict[str, Any]] = []

        for inp in page_info.get("inputs", [])[:4]:
            sel = self._selector(inp)
            if sel:
                validations.append({"type": "element_present", "selector": sel})

        for btn in page_info.get("buttons", [])[:2]:
            sel = self._selector(btn)
            if sel:
                validations.append({"type": "element_present", "selector": sel})

        for h in page_info.get("headings", [])[:1]:
            validations.append({"type": "text_contains", "selector": "body", "expected": h})

        if validations:
            tests.append({
                "id":   "GEN-001",
                "name": "Page loads with expected elements",
                "url":  relative_url,
                "steps": steps,
                "validations": validations,
                "error_checks": ["console_errors"],
            })

        # Test 2: form submission (if inputs + button found)
        inputs  = page_info.get("inputs", [])
        buttons = page_info.get("buttons", [])
        text_inputs = [i for i in inputs if i.get("type", "text") in ("", "text", "search")]
        if text_inputs and buttons:
            form_steps: list[dict[str, Any]] = []
            form_validations: list[dict[str, Any]] = []
            for inp in text_inputs[:2]:
                sel = self._selector(inp)
                if sel:
                    form_steps.append({"action": "type", "selector": sel, "value": "test"})
            btn_sel = self._selector(buttons[0])
            if btn_sel:
                form_steps.append({"action": "click", "selector": btn_sel})
            if form_steps:
                tests.append({
                    "id":   "GEN-002",
                    "name": "Form submission",
                    "url":  relative_url,
                    "steps": form_steps,
                    "validations": form_validations,
                    "error_checks": ["console_errors"],
                })

        # Test 3: table validation (if table found)
        for i, tbl in enumerate(page_info.get("tables", [])[:1]):
            if tbl.get("headers"):
                sel = f"#{tbl['id']}" if tbl.get("id") else "table"
                tests.append({
                    "id":   f"GEN-{len(tests)+1:03d}",
                    "name": "Table structure validation",
                    "url":  relative_url,
                    "steps": [{"action": "wait", "selector": sel, "timeout": 5000}],
                    "validations": [{
                        "type":             "table_validation",
                        "selector":         sel,
                        "expected_columns": tbl["headers"],
                        "row_condition":    "",
                    }],
                    "error_checks": [],
                })

        if not tests:
            tests.append({
                "id":   "GEN-001",
                "name": "Page loads successfully",
                "url":  relative_url,
                "steps": [],
                "validations": [{"type": "text_contains", "selector": "body", "expected": ""}],
                "error_checks": ["console_errors"],
            })

        return {"test_suite": f"{title} — Generated Tests", "tests": tests}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _selector(element: dict[str, Any]) -> str:
        if element.get("id"):
            return f"#{element['id']}"
        if element.get("name"):
            return f"[name=\"{element['name']}\"]"
        t = element.get("type", "")
        tag = element.get("tag", "input")
        if t:
            return f"{tag}[type=\"{t}\"]"
        return ""

    @staticmethod
    def _relative(url: str, base_url: str) -> str:
        if not base_url or not url.startswith(base_url):
            return url
        rel = url[len(base_url):]
        return rel or "/"
