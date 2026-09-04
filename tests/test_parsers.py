from pathlib import Path

from ai_testing_framework.parsers.json_parser import JSONParser
from ai_testing_framework.parsers.md_parser import MarkdownParser


def test_json_parser():
    suite = JSONParser().parse(Path(__file__).parent / "sample_tests" / "test_suite.json")
    assert suite.name == "AI Testing Framework Demo"
    assert [t.id for t in suite.tests] == ["TC-001", "TC-002"]
    assert suite.tests[0].steps[0].action == "type"


def test_markdown_parser():
    suite = MarkdownParser().parse(Path(__file__).parent / "sample_tests" / "test_suite.md")
    assert suite.tests[0].id == "TC-001"
    assert suite.tests[0].steps[0].value == "OpenAI"
    assert any(v.type == "ai_semantic" for v in suite.tests[0].validations)
