"""Unit tests for AIElementLocator (element_locator.py).

All tests run without a live browser using lightweight page mocks.
"""
from __future__ import annotations

import json
from unittest.mock import Mock

import pytest

from ai_testing_framework.automation.element_locator import AIElementLocator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _button_page(count=1):
    """Mock page with a single button matching get_by_role('button')."""
    page = Mock()
    loc = Mock()
    loc.count.return_value = count
    page.get_by_role.return_value = loc
    page.locator.return_value.evaluate_all.return_value = []
    return page


def _input_page(selector_map: dict):
    """Mock page whose locator(sel).count() returns values from selector_map."""
    page = Mock()
    def side(sel):
        loc = Mock()
        loc.count.return_value = selector_map.get(sel, 0)
        return loc
    page.locator.side_effect = side
    page.get_by_role.return_value.count.return_value = 0
    page.get_by_text.return_value.count.return_value = 0
    return page


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_provider_none_has_no_client(self):
        loc = AIElementLocator(provider="none")
        assert loc.client is None

    def test_provider_openai_no_key_has_no_client(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        loc = AIElementLocator(provider="openai")
        assert loc.client is None

    def test_default_provider_is_none(self):
        loc = AIElementLocator()
        assert loc.provider == "none"


# ---------------------------------------------------------------------------
# find_element — ValueError on empty description
# ---------------------------------------------------------------------------

class TestFindElementValidation:
    def test_empty_string_raises(self):
        loc = AIElementLocator(provider="none")
        with pytest.raises(ValueError, match="description"):
            loc.find_element(Mock(), "")

    def test_whitespace_only_raises(self):
        loc = AIElementLocator(provider="none")
        with pytest.raises(ValueError, match="description"):
            loc.find_element(Mock(), "   ")


# ---------------------------------------------------------------------------
# _heuristic — button path
# ---------------------------------------------------------------------------

class TestHeuristicButton:
    def test_single_button_found_by_role_and_word(self):
        page = _button_page(count=1)
        result = AIElementLocator._heuristic(page, "click the Search button")
        assert result is not None
        page.get_by_role.assert_called()

    def test_no_unique_button_by_word_falls_through(self):
        """When get_by_role(word) returns 0 matches, tries bare button, then fallbacks."""
        page = Mock()
        page.get_by_role.return_value.count.return_value = 0
        page.get_by_text.return_value.count.return_value = 0
        page.locator.return_value.count.return_value = 0
        result = AIElementLocator._heuristic(page, "click the Search button")
        # Single bare button also returns 0 → tries other paths → None
        assert result is None

    def test_unique_bare_button_used_when_word_fails(self):
        """Falls back to bare get_by_role('button') when word-search gives 0."""
        page = Mock()
        call_count = [0]
        def role_side(role, name=None):
            loc = Mock()
            if name is None:
                # bare button call
                loc.count.return_value = 1
            else:
                loc.count.return_value = 0
            return loc
        page.get_by_role.side_effect = role_side
        page.locator.return_value.count.return_value = 0
        page.get_by_text.return_value.count.return_value = 0
        result = AIElementLocator._heuristic(page, "click the button")
        assert result is not None


# ---------------------------------------------------------------------------
# _heuristic — input-type paths
# ---------------------------------------------------------------------------

class TestHeuristicInputs:
    def test_email_input_found(self):
        page = _input_page({
            "input[type='email'], input[name*='email' i], input[placeholder*='email' i]": 1
        })
        result = AIElementLocator._heuristic(page, "enter your email address")
        assert result is not None

    def test_password_input_found(self):
        page = _input_page({"input[type='password']": 1})
        result = AIElementLocator._heuristic(page, "type your password here")
        assert result is not None

    def test_search_input_found(self):
        page = _input_page({
            "input[type='search'], input[placeholder*='search' i], input[name*='search' i]": 1
        })
        result = AIElementLocator._heuristic(page, "the search query box")
        assert result is not None

    def test_multiple_email_inputs_not_unique_returns_none(self):
        page = _input_page({
            "input[type='email'], input[name*='email' i], input[placeholder*='email' i]": 2
        })
        page.get_by_role.return_value.count.return_value = 0
        page.get_by_text.return_value.count.return_value = 0
        result = AIElementLocator._heuristic(page, "email field")
        assert result is None


# ---------------------------------------------------------------------------
# _heuristic — text fallback
# ---------------------------------------------------------------------------

class TestHeuristicTextFallback:
    def test_get_by_text_used_as_last_resort(self):
        page = Mock()
        page.get_by_role.return_value.count.return_value = 0
        page.locator.return_value.count.return_value = 0
        page.get_by_text.return_value.count.return_value = 1
        result = AIElementLocator._heuristic(page, "Something unrecognized with unique text")
        assert result is not None

    def test_returns_none_when_all_paths_fail(self):
        page = Mock()
        page.get_by_role.return_value.count.return_value = 0
        page.locator.return_value.count.return_value = 0
        page.get_by_text.return_value.count.return_value = 0
        result = AIElementLocator._heuristic(page, "xyzzy quux frobnitz")
        assert result is None

    def test_exception_in_heuristic_returns_none(self):
        page = Mock()
        page.get_by_role.side_effect = RuntimeError("playwright crashed")
        result = AIElementLocator._heuristic(page, "the submit button")
        assert result is None


# ---------------------------------------------------------------------------
# AI path (mocked OpenAI)
# ---------------------------------------------------------------------------

class TestAIPath:
    def _make_candidates(self):
        return [
            {"index": 0, "tag": "input",  "id": "query",  "text": "", "name": "", "role": "",
             "type": "text",  "aria_label": "", "placeholder": "Search"},
            {"index": 1, "tag": "button", "id": "submit", "text": "Search", "name": "", "role": "",
             "type": "submit", "aria_label": "", "placeholder": ""},
        ]

    def test_ai_index_returns_correct_candidate(self):
        locator = AIElementLocator(provider="openai")
        locator.client = Mock()
        locator.client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(
                content=json.dumps({"index": 1, "reason": "Submit button", "confidence": 0.95})
            ))]
        )
        idx = locator._ai_index("the Search button", self._make_candidates())
        assert idx == 1

    def test_ai_index_returns_none_on_invalid_json(self):
        locator = AIElementLocator(provider="openai")
        locator.client = Mock()
        locator.client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="not json at all"))]
        )
        idx = locator._ai_index("anything", self._make_candidates())
        assert idx is None

    def test_ai_index_returns_none_on_api_exception(self):
        locator = AIElementLocator(provider="openai")
        locator.client = Mock()
        locator.client.chat.completions.create.side_effect = RuntimeError("timeout")
        idx = locator._ai_index("anything", self._make_candidates())
        assert idx is None

    def test_ai_index_returns_none_on_missing_key(self):
        locator = AIElementLocator(provider="openai")
        locator.client = Mock()
        locator.client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content=json.dumps({"reason": "no index here"})))]
        )
        idx = locator._ai_index("anything", self._make_candidates())
        assert idx is None

    def test_find_element_uses_ai_when_client_present(self):
        """find_element prefers AI result over heuristic when client is set."""
        locator = AIElementLocator(provider="openai")
        locator.client = Mock()
        locator.client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(
                content=json.dumps({"index": 1, "reason": "button", "confidence": 0.9})
            ))]
        )

        # Build a page that has candidates and a unique nth(1) locator
        page = Mock()
        page.locator.return_value.evaluate_all.return_value = self._make_candidates()
        nth_locator = Mock()
        nth_locator.count.return_value = 1
        page.locator.return_value.nth.return_value = nth_locator

        result = locator.find_element(page, "the Search button")
        assert result is nth_locator

    def test_find_element_falls_back_to_heuristic_when_ai_returns_none(self):
        """When AI returns out-of-range index, heuristic runs."""
        locator = AIElementLocator(provider="openai")
        locator.client = Mock()
        locator.client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(
                content=json.dumps({"index": 99, "reason": "bad", "confidence": 0.9})
            ))]
        )
        page = Mock()
        page.locator.return_value.evaluate_all.return_value = self._make_candidates()
        page.locator.return_value.nth.return_value.count.return_value = 0
        # Heuristic path: no button match → None → ValueError
        page.get_by_role.return_value.count.return_value = 0
        page.get_by_text.return_value.count.return_value = 0

        with pytest.raises(ValueError, match="Could not locate"):
            locator.find_element(page, "xyzzy quux blargh")

    def test_find_element_raises_when_no_candidates_and_heuristic_fails(self):
        locator = AIElementLocator(provider="none")
        page = Mock()
        page.locator.return_value.evaluate_all.return_value = []
        page.get_by_role.return_value.count.return_value = 0
        page.get_by_text.return_value.count.return_value = 0
        page.locator.return_value.count.return_value = 0

        with pytest.raises(ValueError, match="Could not locate"):
            locator.find_element(page, "the submit button")
