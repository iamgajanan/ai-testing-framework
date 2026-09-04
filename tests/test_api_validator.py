from ai_testing_framework.validators.api_validator import validate_api_response


def response(url="http://127.0.0.1:8000/api/search", method="GET", status=200, body=None):
    return [{
        "url": url,
        "method": method,
        "status": status,
        "status_text": "OK",
        "content_type": "application/json",
        "body": '{"success": true, "results": ["OpenAI"]}',
        "json": body if body is not None else {"success": True, "results": ["OpenAI"]},
    }]


def test_api_status_and_url():
    passed, reason, actual = validate_api_response(response(), url="/api/search", method="GET", status=200)
    assert passed is True
    assert "API assertion passed" in reason
    assert actual["status"] == 200


def test_api_json_path():
    passed, _, _ = validate_api_response(response(), url="/api/search", json_path="success", expected=True)
    assert passed is True


def test_api_json_array_path():
    passed, _, _ = validate_api_response(response(), url="/api/search", json_path="results.0", expected="OpenAI")
    assert passed is True


def test_api_body_contains():
    passed, _, _ = validate_api_response(response(), url="/api/search", body_contains="OpenAI")
    assert passed is True


def test_api_missing_response_fails():
    passed, reason, _ = validate_api_response(response(), url="/api/missing", status=200)
    assert passed is False
    assert "No API response matched" in reason
