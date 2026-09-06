"""AI-powered test generation — Phase 7."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_DOM_EXTRACT_JS = """
(function() {
    return {
        title: document.title,
        body_text: (document.body.innerText || '').trim().slice(0, 12000),
        headings: Array.from(document.querySelectorAll('h1,h2,h3')).slice(0, 6).map(h => h.innerText.trim()).filter(Boolean),
        forms: Array.from(document.querySelectorAll('form')).map(f => ({id:f.id||'', action:f.action||'', method:f.method||'get'})),
        inputs: Array.from(document.querySelectorAll('input,textarea,select')).slice(0,20).map(el => ({tag:el.tagName.toLowerCase(),id:el.id||'',name:el.getAttribute('name')||'',type:el.getAttribute('type')||'',placeholder:el.getAttribute('placeholder')||'',label:(document.querySelector('label[for="'+el.id+'"]')||{}).innerText||''})),
        buttons: Array.from(document.querySelectorAll('button,input[type=submit],input[type=button]')).slice(0,10).map(b => ({tag:b.tagName.toLowerCase(),id:b.id||'',text:(b.innerText||b.value||'').trim(),type:b.getAttribute('type')||''})),
        links: Array.from(document.querySelectorAll('a[href]')).slice(0,10).map(a => ({id:a.id||'',text:a.innerText.trim(),href:a.getAttribute('href')||'',download:a.hasAttribute('download')})),
        tables: Array.from(document.querySelectorAll('table')).slice(0,3).map(t => ({id:t.id||'',headers:Array.from(t.querySelectorAll('th')).map(th => th.innerText.trim())}))
    };
})()
"""

_SYSTEM_PROMPT = """
You are an expert QA engineer generating runnable browser tests from OBSERVED page data.
Never invent behavior. The JSON is executed directly by Playwright.

Rules:
- Use only selectors, text, titles, headings, hrefs, attributes and element types present in page_info.
- NEVER invent success messages, confirmation messages, changed titles, result text, URLs or API responses.
- For forms, exercise observed text/search inputs and observed submit buttons, but do not invent the resulting message.
- NEVER use fill/type on input[type=file]. File inputs require upload/setInputFiles, but do not generate an upload action unless page_info contains a usable existing file path.
- Download is allowed only for an observed link with download=true or an href that clearly names a downloadable file. Never invent a post-download confirmation.
- Prefer element_present when behavior is not directly observable.
- Prefer stable #id, then [name=...], then type selectors.
- Keep tests independent.
- Return ONLY JSON using test_suite, tests, id, name, url, steps, validations and error_checks.
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

    def generate(self, url: str, output_path: str, browser: str = "chromium", base_url: str = "") -> str:
        page_info = self._extract_page_info(url, browser, base_url)
        relative_url = self._relative(url, base_url)
        suite = self._ai_generate(page_info, relative_url) if self.client is not None else self._heuristic_generate(page_info, relative_url)
        if self.client is not None:
            suite = self._sanitize_suite(suite, page_info, relative_url)
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(suite, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(out.resolve())

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

    def _ai_generate(self, page_info: dict[str, Any], relative_url: str) -> dict[str, Any]:
        prompt = json.dumps({"url": relative_url, "page_info": page_info}, ensure_ascii=False)
        resp = self.client.chat.completions.create(model=self.model, temperature=0.1, messages=[{"role":"system","content":_SYSTEM_PROMPT},{"role":"user","content":prompt}])
        raw = (resp.choices[0].message.content or "{}").strip()
        if raw.startswith("```"):
            raw = raw.split("\n",1)[-1].rsplit("```",1)[0]
        suite = json.loads(raw)
        suite.setdefault("test_suite", page_info.get("title") or "Generated Suite")
        if not isinstance(suite.get("tests"), list):
            suite["tests"] = []
        return suite

    def _sanitize_suite(self, suite: dict[str, Any], page_info: dict[str, Any], relative_url: str) -> dict[str, Any]:
        inputs, buttons, links = page_info.get("inputs", []), page_info.get("buttons", []), page_info.get("links", [])
        known = {self._selector(x) for x in inputs + buttons + links if self._selector(x)}
        file_selectors = {self._selector(x) for x in inputs if x.get("type") == "file"}
        download_selectors = {self._selector(x) for x in links if self._selector(x) and (x.get("download") or self._looks_downloadable(x.get("href", "")))}
        observed_text = set(page_info.get("headings", [])) | {x.get("text", "") for x in buttons + links if x.get("text")}
        observed_text |= set(page_info.get("body_text", "").splitlines())
        cleaned = []
        for index, test in enumerate(suite.get("tests", []), 1):
            if not isinstance(test, dict):
                continue
            test["id"] = test.get("id") or f"GEN-{index:03d}"
            test["url"] = test.get("url") or relative_url
            steps = []
            for step in test.get("steps", []) or []:
                if not isinstance(step, dict):
                    continue
                action, selector = str(step.get("action", "")).lower().strip(), step.get("selector")
                if action in {"fill", "type"} and selector in file_selectors:
                    continue
                if action in {"upload", "set_input_files"}:
                    value = step.get("value")
                    if selector not in file_selectors or not value or not Path(str(value)).expanduser().is_file():
                        continue
                    step["action"] = "upload"
                if action == "download" and selector not in download_selectors:
                    continue
                steps.append(step)
            test["steps"] = steps
            validations = []
            for validation in test.get("validations", []) or []:
                if not isinstance(validation, dict):
                    continue
                vtype, expected = validation.get("type"), validation.get("expected")
                if vtype == "text_contains" and expected and expected not in observed_text:
                    continue
                if vtype == "element_present" and validation.get("selector") not in known and validation.get("selector") not in {"body", "table"}:
                    continue
                validations.append(validation)
            test["validations"] = validations
            test["error_checks"] = ["console_errors"] if "console_errors" in (test.get("error_checks") or []) else []
            cleaned.append(test)
        return {"test_suite": suite.get("test_suite") or "Generated Suite", "tests": cleaned or self._heuristic_generate(page_info, relative_url)["tests"]}

    @staticmethod
    def _looks_downloadable(href: str) -> bool:
        path = str(href).lower().split("?",1)[0]
        return any(path.endswith(ext) for ext in (".csv", ".pdf", ".json", ".xlsx", ".zip", ".txt"))

    def _heuristic_generate(self, page_info: dict[str, Any], relative_url: str) -> dict[str, Any]:
        title = page_info.get("title") or "Generated Suite"
        validations = [{"type":"element_present","selector":self._selector(e)} for e in page_info.get("inputs", [])[:4] + page_info.get("buttons", [])[:2] if self._selector(e)]
        validations += [{"type":"text_contains","selector":"body","expected":h} for h in page_info.get("headings", [])[:1]]
        tests = [{"id":"GEN-001","name":"Page loads with expected elements","url":relative_url,"steps":[],"validations":validations,"error_checks":["console_errors"]}]
        text_inputs = [i for i in page_info.get("inputs", []) if i.get("type", "text") in ("", "text", "search")]
        buttons = page_info.get("buttons", [])
        if text_inputs and buttons:
            steps = [{"action":"type","selector":self._selector(i),"value":"test"} for i in text_inputs[:2] if self._selector(i)]
            if self._selector(buttons[0]):
                steps.append({"action":"click","selector":self._selector(buttons[0])})
            tests.append({"id":"GEN-002","name":"Form submission","url":relative_url,"steps":steps,"validations":[],"error_checks":["console_errors"]})

        # Keep table coverage deterministic when a real table is observed.
        for tbl in page_info.get("tables", [])[:1]:
            if tbl.get("headers"):
                sel = f"#{tbl['id']}" if tbl.get("id") else "table"
                tests.append({
                    "id": f"GEN-{len(tests)+1:03d}",
                    "name": "Table structure validation",
                    "url": relative_url,
                    "steps": [{"action":"wait", "selector":sel, "timeout":5000}],
                    "validations": [{
                        "type":"table_validation",
                        "selector":sel,
                        "expected_columns":tbl["headers"],
                        "row_condition":"",
                    }],
                    "error_checks":[],
                })
        return {"test_suite":f"{title} — Generated Tests","tests":tests}

    @staticmethod
    def _selector(element: dict[str, Any]) -> str:
        if element.get("id"):
            return f"#{element['id']}"
        if element.get("name"):
            return f"[name=\"{element['name']}\"]"
        if element.get("type"):
            return f"{element.get('tag','input')}[type=\"{element['type']}\"]"
        return ""

    @staticmethod
    def _relative(url: str, base_url: str) -> str:
        if not base_url or not url.startswith(base_url):
            return url
        rel = url[len(base_url):]
        return rel or "/"
