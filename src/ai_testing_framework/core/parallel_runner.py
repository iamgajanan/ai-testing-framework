"""Parallel test execution for the Universal AI Testing Framework — Phase 6.

Each worker thread creates its own isolated PlaywrightEngine (= its own
browser process + context + page).  No shared mutable state exists between
workers: every thread receives a plain-data copy of the config dict and a
single TestCase, runs the full test lifecycle, and returns a TestResult.

This module is intentionally thin.  All validation and reporting logic stays
in test_runner.py; this module only handles the concurrency layer.

Public API
----------
run_parallel(tests, run_fn, workers) -> list[TestResult]
    Run *tests* concurrently using *workers* threads.
    *run_fn* is a callable(TestCase) -> TestResult supplied by TestRunner.
    Results are returned in the original *tests* order.
"""
from __future__ import annotations

import sys
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Callable, Iterable

from ..core.models import TestCase, TestResult


def run_parallel(
    tests: list[TestCase],
    run_fn: Callable[[TestCase], TestResult],
    workers: int = 1,
) -> list[TestResult]:
    """Execute *tests* in parallel using *workers* threads.

    When ``workers == 1`` no thread pool is created; tests run sequentially
    in the calling thread (identical behaviour to Phase 1-5, zero overhead).

    The original test ordering is preserved in the returned list regardless
    of which worker finishes first.
    """
    if not tests:
        return []

    workers = max(1, workers)

    if workers == 1:
        # Sequential path — identical to old behaviour, no thread overhead.
        return [run_fn(t) for t in tests]

    # Map: future → original index so we can restore ordering.
    index_map: dict[Future[TestResult], int] = {}
    results: list[TestResult | None] = [None] * len(tests)
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ai-test") as pool:
        for i, test in enumerate(tests):
            future = pool.submit(run_fn, test)
            index_map[future] = i

        for future in as_completed(index_map):
            idx = index_map[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                # A worker crashed entirely (engine startup failure, etc.).
                # Record a synthetic FAIL result so the suite still completes.
                test = tests[idx]
                results[idx] = TestResult(
                    id=test.id,
                    name=test.name,
                    status="FAIL",
                    duration=0.0,
                    error=f"Worker crashed: {exc}",
                )
                errors.append(f"[{test.id}] {exc}")

    if errors:
        print(
            f"WARNING: {len(errors)} worker(s) crashed:\n"
            + "\n".join(f"  {e}" for e in errors),
            file=sys.stderr,
        )

    # Filter out any None slots (should never happen, but be safe).
    return [r for r in results if r is not None]
