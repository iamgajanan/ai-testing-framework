from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agentic import AgenticAI
from .test_generator import TestGenerator
from ..core.test_runner import TestRunner


class AutonomousTester:
    """Explore an application, generate executable tests, and run them."""

    def __init__(self, provider: str = "none", model: str = "gpt-4o-mini") -> None:
        self.provider = provider
        self.model = model

    def run(
        self,
        url: str,
        output_dir: str = "reports/autonomous",
        browser: str = "chromium",
        base_url: str = "",
        max_pages: int = 5,
        goal: str = "",
        login: dict[str, Any] | None = None,
        workers: int = 1,
        formats: list[str] | None = None,
    ) -> dict[str, Any]:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        suite_path = out / "generated_suite.json"
        manifest_path = out / "autonomous_run.json"

        generator = TestGenerator(self.provider, self.model)
        if login:
            generated = generator.generate_authenticated(
                url, str(suite_path), login, browser=browser,
                base_url=base_url, max_pages=max_pages,
            )
        else:
            generated = generator.generate(
                url, str(suite_path), browser=browser,
                base_url=base_url, max_pages=max_pages,
            )

        suite = json.loads(Path(generated).read_text(encoding="utf-8"))
        if goal:
            plan = AgenticAI(self.provider, self.model).plan(goal, [goal])
        else:
            plan = {"scenarios": []}

        manifest = {
            "url": url,
            "goal": goal,
            "browser": browser,
            "max_pages": max_pages,
            "generated_suite": str(suite_path),
            "test_count": len(suite.get("tests", [])),
            "plan": plan,
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        runner = TestRunner(base_url=base_url)
        runner.set_ai_provider(self.provider)
        results = runner.run(
            str(suite_path), browser=browser, output_dir=str(out),
            formats=formats or ["html", "json"], workers=workers,
        )
        passed = sum(result.status == "PASS" for result in results)
        return {
            "manifest": str(manifest_path),
            "suite": str(suite_path),
            "results": results,
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
        }
