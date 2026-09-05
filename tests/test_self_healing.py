"""Unit tests for self_healing.py and the _try_heal integration in PlaywrightEngine.

All tests run without a live browser by using mocks for the Playwright Page.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch, call

import pytest

from ai_testing_framework.automation.self_healing import SelfHealing
from ai_testing_framework.automation.playwright_engine import PlaywrightEngine


# ---------------------------------------------------------------------------
# Helpers: build fake candidate lists the same shape as evaluate_all returns
# ---------------------------------------------------------------------------

def _cand(index=0, tag="button", id_="", name="", role="", type_="",
          aria_label="", placeholder="", text=""):
    return dict(index=index, tag=tag, id=id_, name=name, role=role,
                type=type_, aria_label=aria_label, placeholder=placeholder,
                text=text)


CANDS_SEARCH_FORM = [
    _cand(0, "input",  id_="query",  type_="text",   placeholder="Search"),
    _cand(1, "button", id_="submit", text="Search"),
]

CANDS_LOGIN_FORM = [
    _cand(0, "input",  name="email",    type_="email",    placeholder="Enter email"),
    _cand(1, "input",  name="password", type_="password", placeholder="Password"),
    _cand(2, "button", id_="login",     text="Login"),
    _cand(3, "a",      id_="forgot",    text="Forgot password?"),
]


# ---------------------------------------------------------------------------
# _stable_selector
# ---------------------------------------------------------------------------

class TestStableSelector:
    def test_id_takes_priority(self):
        c = _cand(id_="submit")
        assert SelfHealing._stable_selector(c) == "#submit"

    def test_name_when_no_id(self):
        c = _cand(name="email")
        sel = SelfHealing._stable_selector(c)
        assert "email" in sel
        assert sel.startswith("[name=")

    def test_aria_label_fallback(self):
        c = _cand(aria_label="Close dialog")
        sel = SelfHealing._stable_selector(c)
        assert "Close dialog" in sel

    def test_role_and_text_fallback(self):
        c = _cand(role="button", text="Submit form")
        sel = SelfHealing._stable_selector(c)
        assert "Submit form" in sel

    def test_tag_and_text_last_resort(self):
        c = _cand(tag="button", text="Go")
        sel = SelfHealing._stable_selector(c)
        assert "Go" in sel

    def test_empty_candidate_returns_empty(self):
        c = _cand()
        assert SelfHealing._stable_selector(c) == ""


# ---------------------------------------------------------------------------
# _confidence
# ---------------------------------------------------------------------------

class TestConfidence:
    def test_clamps_above_one(self):
        assert SelfHealing._confidence(1.5) == 1.0

    def test_clamps_below_zero(self):
        assert SelfHealing._confidence(-0.3) == 0.0

    def test_valid_value(self):
        assert SelfHealing._confidence(0.85) == pytest.approx(0.85)

    def test_none_returns_zero(self):
        assert SelfHealing._confidence(None) == 0.0

    def test_string_number(self):
        assert SelfHealing._confidence("0.9") == pytest.approx(0.9)

    def test_bad_string_returns_zero(self):
        assert SelfHealing._confidence("not-a-number") == 0.0


# ---------------------------------------------------------------------------
# _heuristic — search form
# ---------------------------------------------------------------------------

class TestHeuristicSearchForm:
    def _make_page(self, candidates):
        """Return a mock Page whose locator().count() == 1 for known selectors."""
        page = Mock()
        def unique_count(sel):
            mock_loc = Mock()
            # Both #query and #submit are "unique" in this fake page
            mock_loc.count.return_value = 1
            return mock_loc
        page.locator.side_effect = unique_count
        return page

    def test_submit_button_resolves_to_button(self):
        page = self._make_page(CANDS_SEARCH_FORM)
        sel, reason = SelfHealing._heuristic(
            page, "#wrong-submit", "the Search button", CANDS_SEARCH_FORM
        )
        assert sel == "#submit", f"Expected #submit, got {sel!r}"
        assert "Self-healed" in reason

    def test_query_input_resolves_to_input(self):
        page = self._make_page(CANDS_SEARCH_FORM)
        sel, reason = SelfHealing._heuristic(
            page, "#wrong-query", "the search query field", CANDS_SEARCH_FORM
        )
        assert sel == "#query", f"Expected #query, got {sel!r}"

    def test_button_intent_beats_input_placeholder_match(self):
        """'Search button' must not resolve to the input that has placeholder='Search'."""
        page = self._make_page(CANDS_SEARCH_FORM)
        sel, _ = SelfHealing._heuristic(
            page, "#broken-btn", "the Search submit button", CANDS_SEARCH_FORM
        )
        assert sel == "#submit"

    def test_empty_candidates_returns_none(self):
        page = Mock()
        sel, reason = SelfHealing._heuristic(page, "#x", "anything", [])
        assert sel is None
        assert "No semantically similar" in reason

    def test_no_matching_words_returns_none(self):
        page = Mock()
        sel, reason = SelfHealing._heuristic(
            page, "#zzz", "xylophone blargh quux", CANDS_SEARCH_FORM
        )
        assert sel is None


# ---------------------------------------------------------------------------
# _heuristic — login form
# ---------------------------------------------------------------------------

class TestHeuristicLoginForm:
    def _make_page(self):
        page = Mock()
        page.locator.return_value.count.return_value = 1
        return page

    def test_email_resolves_to_email_input(self):
        page = self._make_page()
        sel, _ = SelfHealing._heuristic(
            page, "#bad-email", "email address input", CANDS_LOGIN_FORM
        )
        assert "email" in sel

    def test_password_resolves_to_password_input(self):
        page = self._make_page()
        sel, _ = SelfHealing._heuristic(
            page, "#bad-pass", "password field", CANDS_LOGIN_FORM
        )
        assert "password" in sel

    def test_login_button_resolves_to_button_not_link(self):
        page = self._make_page()
        sel, _ = SelfHealing._heuristic(
            page, "#bad-btn", "the Login submit button", CANDS_LOGIN_FORM
        )
        assert sel == "#login"

    def test_forgot_link_resolves_to_anchor(self):
        page = self._make_page()
        sel, _ = SelfHealing._heuristic(
            page, "#bad-link", "forgot password link", CANDS_LOGIN_FORM
        )
        assert sel == "#forgot"


# ---------------------------------------------------------------------------
# SelfHealing.heal_selector — integration (mocked page)
# ---------------------------------------------------------------------------

class TestHealSelector:
    def _healer(self):
        return SelfHealing(provider="none")

    def _page_with_candidates(self, candidates):
        page = Mock()
        page.locator.return_value.evaluate_all.return_value = candidates
        page.locator.return_value.count.return_value = 1
        return page

    def test_returns_selector_when_match_found(self):
        page = self._page_with_candidates(CANDS_SEARCH_FORM)
        healer = self._healer()
        result = healer.heal_selector(page, "#broken-submit", "the Search button")
        assert result == "#submit"
        assert healer.last_confidence == 0.75
        assert "Self-healed" in healer.last_reason

    def test_returns_none_when_no_candidates(self):
        page = self._page_with_candidates([])
        result = self._healer().heal_selector(page, "#x", "anything")
        assert result is None

    def test_returns_none_when_no_match(self):
        page = self._page_with_candidates(CANDS_SEARCH_FORM)
        result = self._healer().heal_selector(page, "#zzz", "zzzzz quux blargh")
        assert result is None
        assert self._healer().last_confidence == 0.0

    def test_no_api_key_means_no_ai_client(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        healer = SelfHealing(provider="openai")
        assert healer.client is None

    def test_ai_result_used_when_confidence_sufficient(self):
        """When AI returns a valid index with high confidence, use that candidate."""
        page = Mock()
        page.locator.return_value.evaluate_all.return_value = CANDS_SEARCH_FORM
        page.locator.return_value.count.return_value = 1

        healer = SelfHealing(provider="openai", min_confidence=0.70)
        healer.client = Mock()
        healer.client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(
                content=json.dumps({"index": 1, "reason": "Submit button", "confidence": 0.95})
            ))]
        )
        result = healer.heal_selector(page, "#broken", "the Search button")
        assert result == "#submit"
        assert healer.last_reason == "Submit button"
        assert healer.last_confidence == pytest.approx(0.95)

    def test_ai_low_confidence_falls_back_to_heuristic(self):
        """When AI confidence is below threshold, fall back to heuristic."""
        page = Mock()
        page.locator.return_value.evaluate_all.return_value = CANDS_SEARCH_FORM
        page.locator.return_value.count.return_value = 1

        healer = SelfHealing(provider="openai", min_confidence=0.90)
        healer.client = Mock()
        healer.client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(
                content=json.dumps({"index": 1, "reason": "uncertain", "confidence": 0.50})
            ))]
        )
        result = healer.heal_selector(page, "#broken-submit", "the Search button")
        # Falls back to heuristic which should still find #submit
        assert result == "#submit"

    def test_ai_exception_falls_back_to_heuristic(self):
        page = Mock()
        page.locator.return_value.evaluate_all.return_value = CANDS_SEARCH_FORM
        page.locator.return_value.count.return_value = 1

        healer = SelfHealing(provider="openai")
        healer.client = Mock()
        healer.client.chat.completions.create.side_effect = RuntimeError("network error")
        result = healer.heal_selector(page, "#broken-submit", "the Search button")
        # Heuristic fallback
        assert result == "#submit"


# ---------------------------------------------------------------------------
# PlaywrightEngine._try_heal integration
# ---------------------------------------------------------------------------

class TestTryHeal:
    def _engine_with_mock_page(self):
        engine = PlaywrightEngine(self_healing=True)
        engine.page = Mock()
        return engine

    def test_try_heal_succeeds_on_first_attempt(self):
        """When the first action call succeeds, healing is not triggered."""
        engine = self._engine_with_mock_page()
        called = []
        def action(loc):
            called.append(loc)
            return "ok"
        engine._try_heal("#submit", "submit button", action, timeout=1000)
        assert len(called) == 1
        assert engine.healed_selectors == []

    def test_try_heal_records_event_on_recovery(self):
        """When action fails, healer finds a replacement, retry succeeds, event is recorded."""
        engine = self._engine_with_mock_page()

        # Mock the self_healing object
        engine.self_healing = Mock()
        engine.self_healing.heal_selector.return_value = "#submit"
        engine.self_healing.last_reason = "Recovered via heuristic"
        engine.self_healing.last_confidence = 0.75

        call_count = [0]
        def action(loc):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Element not found")
            return "recovered"

        result = engine._try_heal("#wrong-selector", "submit button", action, timeout=1000)
        assert result == "recovered"
        assert len(engine.healed_selectors) == 1
        event = engine.healed_selectors[0]
        assert event["failed_selector"] == "#wrong-selector"
        assert event["healed_selector"] == "#submit"
        assert event["reason"] == "Recovered via heuristic"
        assert event["confidence"] == 0.75

    def test_try_heal_reraises_when_no_healed_selector(self):
        """When healer returns None, the original exception propagates."""
        engine = self._engine_with_mock_page()
        engine.self_healing = Mock()
        engine.self_healing.heal_selector.return_value = None

        def action(loc):
            raise RuntimeError("original error")

        with pytest.raises(RuntimeError, match="original error"):
            engine._try_heal("#bad", "", action, timeout=1000)

        assert engine.healed_selectors == []

    def test_try_heal_reraises_when_healing_disabled(self):
        """When self_healing=False on the engine, exceptions propagate immediately."""
        engine = PlaywrightEngine(self_healing=False)
        engine.page = Mock()

        def action(loc):
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            engine._try_heal("#bad", "", action, timeout=1000)


# ---------------------------------------------------------------------------
# TestResult includes healed_selectors
# ---------------------------------------------------------------------------

class TestResultHealedSelectors:
    def test_healed_selectors_in_testresult(self):
        from ai_testing_framework.core.models import TestResult
        r = TestResult(
            id="T1", name="test", status="PASS", duration=1.0,
            healed_selectors=[
                {"failed_selector": "#a", "healed_selector": "#b",
                 "reason": "x", "confidence": 0.8}
            ],
        )
        d = r.to_dict()
        assert len(d["healed_selectors"]) == 1
        assert d["healed_selectors"][0]["healed_selector"] == "#b"

    def test_healed_selectors_empty_by_default(self):
        from ai_testing_framework.core.models import TestResult
        r = TestResult(id="T1", name="test", status="PASS", duration=0.5)
        assert r.healed_selectors == []
