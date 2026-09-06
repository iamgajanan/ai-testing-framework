from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Step:
    action: str
    selector: Optional[str] = None
    value: Any = None
    description: str = ""
    timeout: int = 30000


@dataclass
class Validation:
    type: str
    prompt: str = ""
    expected: Any = None
    selector: Optional[str] = None
    pattern: Optional[str] = None
    expected_columns: List[str] = field(default_factory=list)
    row_condition: Optional[str] = None
    api_url: Optional[str] = None
    api_method: Optional[str] = None
    api_status: Optional[int] = None
    api_request_headers: Dict[str, str] = field(default_factory=dict)
    api_response_headers: Dict[str, str] = field(default_factory=dict)
    api_request_body: Any = None
    api_response_body: Any = None
    api_json_schema: Optional[Dict[str, Any]] = None
    api_response_time_ms: Optional[float] = None
    json_path: Optional[str] = None
    body_contains: Optional[str] = None
    file_path: Optional[str] = None
    expected_filename: Optional[str] = None
    expected_extension: Optional[str] = None
    expected_mime: Optional[str] = None
    min_size: Optional[int] = None
    max_size: Optional[int] = None
    file_type: Optional[str] = None
    file_text_contains: Optional[str] = None
    file_pattern: Optional[str] = None
    timeout: int = 5000
    min_confidence: Optional[float] = None


@dataclass
class TestCase:
    id: str
    name: str
    url: str
    steps: List[Step] = field(default_factory=list)
    validations: List[Validation] = field(default_factory=list)
    error_checks: List[str] = field(default_factory=list)
    expected: str = ""


@dataclass
class ValidationResult:
    type: str
    passed: bool
    reason: str = ""
    confidence: Optional[float] = None
    actual: Any = None


@dataclass
class TestResult:
    id: str
    name: str
    status: str
    duration: float
    response: str = ""
    error: str = ""
    screenshot: Optional[str] = None
    validations: List[ValidationResult] = field(default_factory=list)
    console_errors: List[str] = field(default_factory=list)
    api_errors: List[str] = field(default_factory=list)
    healed_selectors: List[Dict[str, Any]] = field(default_factory=list)
    failure_analysis: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TestSuite:
    name: str
    tests: List[TestCase]

    def to_dict(self) -> Dict[str, Any]:
        return {"test_suite": self.name, "tests": [asdict(test) for test in self.tests]}
