from __future__ import annotations

import json

from ai_testing_framework.ai.autonomous import AutonomousTester


class _Result:
    def __init__(self, status):
        self.status = status
        self.duration = 0.01


def test_autonomous_run_orchestrates_generation_and_execution(monkeypatch, tmp_path):
    generated = tmp_path / "generated_suite.json"
    generated.write_text(json.dumps({"test_suite": "Auto", "tests": [{"id": "GEN-001"}]}), encoding="utf-8")

    class FakeGenerator:
        def __init__(self, provider, model):
            pass

        def generate(self, *args, **kwargs):
            return str(generated)

    class FakeRunner:
        def __init__(self, *args, **kwargs):
            pass

        def set_ai_provider(self, provider):
            assert provider == "none"

        def run(self, *args, **kwargs):
            return [_Result("PASS")]

    monkeypatch.setattr("ai_testing_framework.ai.autonomous.TestGenerator", FakeGenerator)
    monkeypatch.setattr("ai_testing_framework.ai.autonomous.TestRunner", FakeRunner)
    result = AutonomousTester("none").run("http://example.test", str(tmp_path), max_pages=3)

    assert result["total"] == 1
    assert result["passed"] == 1
    assert result["failed"] == 0
    manifest = json.loads((tmp_path / "autonomous_run.json").read_text(encoding="utf-8"))
    assert manifest["url"] == "http://example.test"
    assert manifest["test_count"] == 1
