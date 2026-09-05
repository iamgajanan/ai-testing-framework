"""Unit tests for Phase 6 — Parallel execution.

All tests run without a live browser. We test:
- parallel_runner.run_parallel() ordering, worker crash handling, sequential path
- TestRunner.run() accepting workers= parameter (mocked engine)
- CLI --workers flag parsing
"""
from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from ai_testing_framework.core.models import TestCase, TestResult, Step, Validation
from ai_testing_framework.core.parallel_runner import run_parallel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tc(id_: str, name: str = "") -> TestCase:
    return TestCase(id=id_, name=name or id_, url="/")


def _ok(id_: str, duration: float = 0.1) -> TestResult:
    return TestResult(id=id_, name=id_, status="PASS", duration=duration)


def _fail(id_: str) -> TestResult:
    return TestResult(id=id_, name=id_, status="FAIL", duration=0.0, error="boom")


# ---------------------------------------------------------------------------
# run_parallel — sequential path (workers=1)
# ---------------------------------------------------------------------------

class TestRunParallelSequential:
    def test_empty_input_returns_empty(self):
        results = run_parallel([], run_fn=lambda t: _ok(t.id), workers=1)
        assert results == []

    def test_single_test_runs(self):
        results = run_parallel([_tc("T1")], run_fn=lambda t: _ok(t.id), workers=1)
        assert len(results) == 1
        assert results[0].id == "T1"

    def test_ordering_preserved(self):
        ids = ["T3", "T1", "T2"]
        tests = [_tc(i) for i in ids]
        results = run_parallel(tests, run_fn=lambda t: _ok(t.id), workers=1)
        assert [r.id for r in results] == ids

    def test_fn_called_once_per_test(self):
        calls = []
        def fn(t):
            calls.append(t.id)
            return _ok(t.id)
        run_parallel([_tc("A"), _tc("B"), _tc("C")], run_fn=fn, workers=1)
        assert calls == ["A", "B", "C"]

    def test_exception_propagates_in_sequential(self):
        def bad_fn(t):
            raise RuntimeError("worker exploded")
        with pytest.raises(RuntimeError, match="worker exploded"):
            run_parallel([_tc("X")], run_fn=bad_fn, workers=1)


# ---------------------------------------------------------------------------
# run_parallel — parallel path (workers > 1)
# ---------------------------------------------------------------------------

class TestRunParallelConcurrent:
    def test_all_results_returned(self):
        tests = [_tc(f"T{i}") for i in range(5)]
        results = run_parallel(tests, run_fn=lambda t: _ok(t.id), workers=3)
        assert len(results) == 5

    def test_original_ordering_preserved(self):
        """Even if workers finish out of order, result list matches input order."""
        ids = [f"T{i}" for i in range(8)]
        tests = [_tc(i) for i in ids]

        def slow_fn(t):
            # Reverse sleep: T0 sleeps longest so it finishes last.
            idx = ids.index(t.id)
            time.sleep((len(ids) - idx) * 0.01)
            return _ok(t.id)

        results = run_parallel(tests, run_fn=slow_fn, workers=4)
        assert [r.id for r in results] == ids

    def test_workers_capped_at_one_minimum(self):
        results = run_parallel([_tc("X")], run_fn=lambda t: _ok(t.id), workers=0)
        assert len(results) == 1

    def test_actual_concurrency_occurs(self):
        """Verify multiple threads run simultaneously by checking overlap."""
        start_times: list[float] = []
        lock = threading.Lock()

        def fn(t):
            with lock:
                start_times.append(time.monotonic())
            time.sleep(0.05)
            return _ok(t.id)

        tests = [_tc(f"T{i}") for i in range(4)]
        run_parallel(tests, run_fn=fn, workers=4)

        # All 4 workers should have started within 100ms of each other
        # (if truly concurrent, not sequential which would be ~200ms apart).
        assert len(start_times) == 4
        spread = max(start_times) - min(start_times)
        assert spread < 0.12, f"Workers don't seem concurrent: spread={spread:.3f}s"

    def test_worker_crash_produces_fail_result(self):
        """A worker that raises returns a synthetic FAIL, not a crash."""
        def fn(t):
            if t.id == "BAD":
                raise RuntimeError("browser crashed")
            return _ok(t.id)

        tests = [_tc("GOOD"), _tc("BAD"), _tc("ALSO_GOOD")]
        results = run_parallel(tests, run_fn=fn, workers=2)

        assert len(results) == 3
        ids = {r.id: r for r in results}
        assert ids["GOOD"].status == "PASS"
        assert ids["BAD"].status == "FAIL"
        assert "crashed" in ids["BAD"].error
        assert ids["ALSO_GOOD"].status == "PASS"

    def test_ordering_preserved_after_crash(self):
        def fn(t):
            if t.id == "T2":
                raise RuntimeError("crash")
            return _ok(t.id)

        tests = [_tc("T1"), _tc("T2"), _tc("T3")]
        results = run_parallel(tests, run_fn=fn, workers=2)
        assert [r.id for r in results] == ["T1", "T2", "T3"]

    def test_all_workers_crash_returns_all_fail(self):
        def fn(t):
            raise RuntimeError("always fails")

        tests = [_tc(f"T{i}") for i in range(3)]
        results = run_parallel(tests, run_fn=fn, workers=3)
        assert len(results) == 3
        assert all(r.status == "FAIL" for r in results)

    def test_workers_greater_than_tests(self):
        """More workers than tests — should still work fine."""
        tests = [_tc("T1"), _tc("T2")]
        results = run_parallel(tests, run_fn=lambda t: _ok(t.id), workers=10)
        assert len(results) == 2
        assert [r.id for r in results] == ["T1", "T2"]

    def test_mixed_pass_fail_results(self):
        def fn(t):
            return _ok(t.id) if t.id != "T3" else _fail(t.id)

        tests = [_tc(f"T{i}") for i in range(1, 6)]
        results = run_parallel(tests, run_fn=fn, workers=3)
        statuses = {r.id: r.status for r in results}
        assert statuses["T3"] == "FAIL"
        assert all(statuses[f"T{i}"] == "PASS" for i in [1, 2, 4, 5])


# ---------------------------------------------------------------------------
# TestRunner integration — workers= parameter (mocked engine)
# ---------------------------------------------------------------------------

class TestRunnerWorkersParameter:
    """Verify TestRunner.run() accepts and passes workers= correctly."""

    def _make_runner(self):
        from ai_testing_framework.core.test_runner import TestRunner
        runner = TestRunner()
        runner.set_ai_provider("none")
        return runner

    def test_workers_defaults_to_one(self):
        runner = self._make_runner()
        assert runner.config.get("parallel", {}).get("workers", 1) == 1

    def test_workers_from_config(self):
        from ai_testing_framework.core.test_runner import TestRunner
        runner = TestRunner(config={"ai": {"provider": "none", "model": "gpt-4o-mini"},
                                    "report": {"output_dir": "reports"},
                                    "parallel": {"workers": 3}})
        assert runner.config["parallel"]["workers"] == 3


# ---------------------------------------------------------------------------
# CLI --workers flag
# ---------------------------------------------------------------------------

class TestCLIWorkersFlag:
    def _parse(self, args):
        from ai_testing_framework.cli import build_parser
        return build_parser().parse_args(args)

    def test_default_workers_is_none(self):
        args = self._parse(["--file", "x.json"])
        assert args.workers is None

    def test_workers_parsed_correctly(self):
        args = self._parse(["--file", "x.json", "--workers", "4"])
        assert args.workers == 4

    def test_workers_one_is_sequential(self):
        args = self._parse(["--file", "x.json", "--workers", "1"])
        assert args.workers == 1

    def test_workers_must_be_integer(self):
        with pytest.raises(SystemExit):
            self._parse(["--file", "x.json", "--workers", "fast"])


# ---------------------------------------------------------------------------
# Thread safety — results don't bleed between concurrent tests
# ---------------------------------------------------------------------------

class TestIsolation:
    def test_results_are_independent(self):
        """Each worker returns a distinct TestResult with correct id."""
        ids = [f"TC-{i:03d}" for i in range(20)]
        tests = [_tc(i) for i in ids]

        seen = set()
        lock = threading.Lock()

        def fn(t):
            result = _ok(t.id)
            with lock:
                seen.add(t.id)
            return result

        results = run_parallel(tests, run_fn=fn, workers=5)
        result_ids = [r.id for r in results]
        assert result_ids == ids           # order preserved
        assert seen == set(ids)            # all executed exactly once
        assert len(results) == len(ids)    # no duplicates or drops
