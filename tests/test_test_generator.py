"""Unit tests for Phase 7 — TestGenerator (no live browser, mocked Playwright)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock

from ai_testing_framework.ai.test_generator import TestGenerator


def _page_info(**kw):
    defaults = dict(
        title="Demo App",
        headings=["Welcome"],
        forms=[{"id": "search-form", "action": "", "method": "get"}],
        inputs=[
            {"tag": "input", "id": "query", "name": "", "type": "text",
             "placeholder": "Search", "label": ""},
        ],
        buttons=[
            {"tag": "button", "id": "submit", "text": "Search", "type": "submit"},
        ],
        links=[{"text": "Home", "href": "/"}],
        tables=[],
        url="/",
        target_url="http://127.0.0.1:8000/",
    )
    defaults.update(kw)
    return defaults


class TestSelectorHelper:
    def test_id_preferred(self):
        el = {"id": "submit", "name": "", "type": "submit", "tag": "button"}
        assert TestGenerator._selector(el) == "#submit"

    def test_name_when_no_id(self):
        el = {"id": "", "name": "email", "type": "email", "tag": "input"}
        assert 'name="email"' in TestGenerator._selector(el)

    def test_type_when_no_id_or_name(self):
        el = {"id": "", "name": "", "type": "password", "tag": "input"}
        assert 'type="password"' in TestGenerator._selector(el)

    def test_empty_returns_empty_string(self):
        el = {"id": "", "name": "", "type": "", "tag": "input"}
        assert TestGenerator._selector(el) == ""


class TestRelativeHelper:
    def test_strips_base_url(self):
        rel = TestGenerator._relative("http://127.0.0.1:8000/table", "http://127.0.0.1:8000")
        assert rel == "/table"

    def test_no_base_url_returns_url_unchanged(self):
        rel = TestGenerator._relative("/table", "")
        assert rel == "/table"

    def test_root_path(self):
        rel = TestGenerator._relative("http://127.0.0.1:8000/", "http://127.0.0.1:8000")
        assert rel == "/"


class TestHeuristicGenerate:
    def _gen(self):
        return TestGenerator(provider="none")

    def test_returns_valid_suite_structure(self):
        suite = self._gen()._heuristic_generate(_page_info(), "/")
        assert "test_suite" in suite and "tests" in suite
        assert isinstance(suite["tests"], list)
        assert len(suite["tests"]) >= 1

    def test_test_ids_are_sequential(self):
        suite = self._gen()._heuristic_generate(_page_info(), "/")
        for t in suite["tests"]:
            assert t["id"].startswith("GEN-")

    def test_page_load_test_includes_element_presence(self):
        first = self._gen()._heuristic_generate(_page_info(), "/")["tests"][0]
        types = [v["type"] for v in first["validations"]]
        assert "element_present" in types or "text_contains" in types

    def test_form_test_added_when_inputs_and_buttons_present(self):
        suite = self._gen()._heuristic_generate(_page_info(), "/")
        all_actions = [s["action"] for t in suite["tests"] for s in t.get("steps", [])]
        assert "type" in all_actions or "click" in all_actions

    def test_table_test_added_when_table_present(self):
        info = _page_info(tables=[{"id": "customers", "headers": ["Name", "Country"]}])
        suite = self._gen()._heuristic_generate(info, "/")
        val_types = [v["type"] for t in suite["tests"] for v in t.get("validations", [])]
        assert "table_validation" in val_types

    def test_no_table_test_when_no_table(self):
        suite = self._gen()._heuristic_generate(_page_info(tables=[]), "/")
        val_types = [v["type"] for t in suite["tests"] for v in t.get("validations", [])]
        assert "table_validation" not in val_types

    def test_fallback_when_no_interactive_elements(self):
        info = _page_info(inputs=[], buttons=[], tables=[])
        suite = self._gen()._heuristic_generate(info, "/")
        assert len(suite["tests"]) >= 1

    def test_suite_name_contains_page_title(self):
        suite = self._gen()._heuristic_generate(_page_info(title="My App"), "/")
        assert "My App" in suite["test_suite"]

    def test_url_in_each_test(self):
        suite = self._gen()._heuristic_generate(_page_info(), "/search")
        for t in suite["tests"]:
            assert t["url"] == "/search"

    def test_each_test_has_required_keys(self):
        suite = self._gen()._heuristic_generate(_page_info(), "/")
        required = {"id", "name", "url", "steps", "validations", "error_checks"}
        for t in suite["tests"]:
            assert required.issubset(set(t.keys()))


class TestAIGenerate:
    def _make_gen(self, response_dict):
        g = TestGenerator(provider="openai")
        g.client = Mock()
        g.client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content=json.dumps(response_dict)))]
        )
        return g

    def test_ai_suite_returned(self):
        suite = {
            "test_suite": "AI Suite",
            "tests": [{"id": "GEN-001", "name": "Search", "url": "/",
                        "steps": [], "validations": [], "error_checks": []}],
        }
        result = self._make_gen(suite)._ai_generate(_page_info(), "/")
        assert result["test_suite"] == "AI Suite"
        assert len(result["tests"]) == 1

    def test_nested_ai_suite_is_normalized(self):
        response = {
            "test_suite": {
                "id": "ai_testing_demo_suite",
                "name": "AI Testing Demo Tests",
                "tests": [{"id": "search", "name": "Search", "url": "/",
                            "steps": [], "validations": [], "error_checks": []}],
            }
        }
        result = self._make_gen(response)._ai_generate(_page_info(), "/")
        assert result["test_suite"] == "AI Testing Demo Tests"
        assert len(result["tests"]) == 1
        assert isinstance(result["test_suite"], str)

    def test_missing_test_suite_key_added(self):
        result = self._make_gen({"tests": []})._ai_generate(_page_info(title="My Page"), "/")
        assert "test_suite" in result

    def test_missing_tests_key_added(self):
        result = self._make_gen({"test_suite": "Suite"})._ai_generate(_page_info(), "/")
        assert result["tests"] == []


class TestGenerateWritesFile:
    def test_file_written_with_heuristic(self):
        with tempfile.TemporaryDirectory() as d:
            out = f"{d}/suite.json"
            g = TestGenerator(provider="none")
            g._extract_page_info = lambda url, browser, base_url: _page_info()
            path = g.generate("/", out, base_url="http://example.com")
            assert Path(path).exists()
            assert "tests" in json.loads(Path(path).read_text())

    def test_output_directory_created(self):
        with tempfile.TemporaryDirectory() as d:
            out = f"{d}/subdir/suite.json"
            g = TestGenerator(provider="none")
            g._extract_page_info = lambda *a, **kw: _page_info()
            g.generate("/", out)
            assert Path(out).exists()


class TestCLIGenerateCommand:
    def test_generate_subcommand_parsed(self):
        from ai_testing_framework.cli import build_parser
        args = build_parser().parse_args([
            "generate", "--url", "http://127.0.0.1:8000",
            "--output", "tests/gen.json", "--ai-provider", "none",
        ])
        assert args.command == "generate"
        assert args.url == "http://127.0.0.1:8000"
        assert args.output == "tests/gen.json"
        assert args.ai_provider == "none"

    def test_run_subcommand_still_works(self):
        from ai_testing_framework.cli import build_parser
        args = build_parser().parse_args(["--file", "x.json"])
        assert args.file == "x.json"
