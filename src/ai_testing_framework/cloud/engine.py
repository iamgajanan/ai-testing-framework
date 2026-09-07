from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .contracts import ExecutionRequest, ExecutionStatus


class EngineAdapter(ABC):
    """Boundary between SaaS orchestration and the existing test engine."""

    @abstractmethod
    def execute(self, request: ExecutionRequest) -> dict[str, Any]:
        """Execute a request and return a serializable execution result."""


class LocalEngineAdapter(EngineAdapter):
    """Adapter that invokes the existing TestRunner without changing it."""

    def execute(self, request: ExecutionRequest) -> dict[str, Any]:
        from ..core.test_runner import TestRunner

        spec = request.spec
        runner = TestRunner(config=spec.config, base_url=spec.base_url)
        if spec.ai_provider:
            runner.set_ai_provider(spec.ai_provider)

        results = runner.run(
            spec.suite_path,
            browser=spec.browser,
            test_id=spec.test_id,
            output_dir=spec.output_dir,
            formats=list(spec.formats),
            workers=spec.workers,
        )
        passed = sum(result.status == "PASS" for result in results)
        failed = len(results) - passed
        return {
            "status": ExecutionStatus.PASSED if failed == 0 else ExecutionStatus.FAILED,
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "results": [result.to_dict() for result in results],
            "output_dir": spec.output_dir,
        }
