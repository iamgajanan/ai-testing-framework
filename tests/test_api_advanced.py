import json

from ai_testing_framework.validators.api_validator import validate_api_response


def _response():
    return [{
        "url": "http://localhost/api/echo",
        "method": "POST",
        "status": 200,
        "body": json.dumps({"success": True, "message": "hello"}),
        "json": {"success": True, "message": "hello"},
        "request_headers": {"X-Test-Header": "framework"},
        "response_headers": {"X-Demo-Response": "echo"},
        "request_body": {"message": "hello"},
        "response_time_ms": 12.5,
    }]


def test_advanced_api_assertions_pass():
    ok, reason, actual = validate_api_response(
        _response(), url="/api/echo", method="POST", status=200,
        request_headers={"x-test-header": "framework"},
        response_headers={"x-demo-response": "echo"},
        request_body={"message": "hello"},
        response_body={"success": True, "message": "hello"},
        json_schema={"type": "object", "required": ["success", "message"], "properties": {"success": {"type": "boolean"}}},
        response_time_ms=100,
    )
    assert ok, reason
    assert actual["status"] == 200


def test_api_schema_failure():
    ok, reason, _ = validate_api_response(_response(), url="/api/echo", json_schema={"type": "object", "required": ["missing"]})
    assert not ok
    assert "schema" in reason.lower()


def test_api_response_time_failure():
    ok, reason, _ = validate_api_response(_response(), url="/api/echo", response_time_ms=5)
    assert not ok
    assert "exceeds" in reason
