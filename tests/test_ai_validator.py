from unittest.mock import Mock, patch

from ai_testing_framework.validators.ai_validator import AIValidator


def test_heuristic_semantic_validation():
    validator = AIValidator(provider="none")
    result = validator.validate_response(
        "OpenAI is an AI research company.",
        "A response mentioning OpenAI",
        "Check relevance to an OpenAI search",
    )
    assert result["pass"] is True
    assert 0 <= result["confidence"] <= 1


def test_empty_expected_requires_non_empty_response():
    validator = AIValidator(provider="none")
    assert validator.validate_response("", "")["pass"] is False
    assert validator.validate_response("hello", "")["pass"] is True


def test_openai_result_is_normalized():
    fake_response = Mock()
    fake_response.choices = [
        Mock(message=Mock(content='{"passed":"true","reason":"Semantically relevant","confidence":1.7}'))
    ]
    validator = AIValidator(provider="openai")
    validator.client = Mock()
    validator.client.chat.completions.create.return_value = fake_response

    result = validator.validate_response("OpenAI result", "Relevant OpenAI result")

    assert result == {
        "pass": True,
        "reason": "Semantically relevant",
        "confidence": 1.0,
    }


def test_openai_markdown_json_is_supported():
    fake_response = Mock()
    fake_response.choices = [
        Mock(message=Mock(content='```json\n{"pass":false,"reason":"Not relevant","confidence":0.25}\n```'))
    ]
    validator = AIValidator(provider="openai")
    validator.client = Mock()
    validator.client.chat.completions.create.return_value = fake_response

    result = validator.validate_response("Other result", "OpenAI result")

    assert result["pass"] is False
    assert result["confidence"] == 0.25


def test_openai_error_returns_failed_validation():
    validator = AIValidator(provider="openai")
    validator.client = Mock()
    validator.client.chat.completions.create.side_effect = RuntimeError("API unavailable")

    result = validator.validate_response("response", "expected")

    assert result["pass"] is False
    assert result["confidence"] == 0.0
    assert "AI validation failed" in result["reason"]
