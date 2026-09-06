# Universal AI Testing Framework

A generic Python + Playwright framework for testing arbitrary web applications from **JSON, Markdown, CSV, or XLSX** test definitions. It combines deterministic browser assertions with optional OpenAI semantic validation, AI element location, self-healing selectors, diagnostics, reporting, parallel execution, test generation, advanced API assertions, and file validation.

## What is implemented

- Playwright automation: Chromium, Firefox, WebKit
- Actions: click, type/fill, select, check/uncheck, hover, press, wait, wait-for-load-state, wait-for-response, upload, download
- AI semantic validation with local fallback when no API key is configured
- AI element locator from natural-language descriptions
- Self-healing selectors with confidence and healing history
- Deterministic validators: regex, element presence, text, URL, table
- API assertions against **real browser network traffic**
  - URL, method, status
  - request/response headers
  - request/response bodies
  - JSON path
  - lightweight JSON Schema validation
  - response-body substring
  - response-time limit
- File upload/download validation
  - existence, filename, extension, MIME, size
  - text/regex content
  - JSON structure/path
  - CSV/XLSX columns
  - PDF structure/header
- HTML, JSON and PDF reports
- Screenshots on failures
- Console/network error capture
- Failure analysis with heuristic or OpenAI diagnosis
- AI-assisted test generation from a live URL
- Confidence thresholds for AI assertions
- Parallel isolated browser workers
- Run history and flaky-test detection
- GitHub Actions CI with Python 3.10/3.11/3.12 × Chromium/Firefox/WebKit

## Installation

Python 3.10+ is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Install all browsers when needed:

```bash
playwright install chromium firefox webkit
```

## OpenAI configuration

The framework does **not** require an OpenAI key for deterministic tests. Set the key only when using OpenAI-backed semantic validation, AI element location, failure analysis, or AI test generation:

```bash
export OPENAI_API_KEY="your-api-key"
```

Never commit the key to the repository. A local environment variable or CI secret is the intended mechanism.

## Quick start

Start the included demo application:

```bash
python examples/demo_app.py
```

Run a suite:

```bash
ai-test --file tests/sample_tests/test_suite.json \
  --base-url http://127.0.0.1:8000 \
  --browser chromium \
  --ai-provider none
```

Reports are written to `reports/` by default.

## CLI

```text
ai-test --help
ai-test --file tests/sample_tests/test_suite.json
ai-test run --file tests/sample_tests/test_suite.json
ai-test --file suite.json --test TC-001
ai-test --file suite.json --workers 3
ai-test --file suite.json --format html json
ai-test --file suite.json --format all
ai-test generate --url http://127.0.0.1:8000 --output tests/generated_suite.json
```

`ai-test --file ...` remains supported for backward compatibility.

## Test definition

JSON is the canonical format. Example:

```json
{
  "test_suite": "Search",
  "tests": [
    {
      "id": "TC-001",
      "name": "Search OpenAI",
      "url": "/",
      "steps": [
        {"action": "type", "selector": "#query", "value": "OpenAI"},
        {"action": "click", "selector": "#submit"}
      ],
      "validations": [
        {"type": "text_contains", "selector": "#result", "expected": "OpenAI"},
        {"type": "api_response", "api_url": "/api/search", "api_method": "GET", "api_status": 200,
         "json_path": "success", "expected": true}
      ],
      "error_checks": ["console_errors", "api_errors"]
    }
  ]
}
```

Markdown, CSV and XLSX are also supported. CSV/XLSX group rows by `TestID` and use one row per action/validation.

## AI semantic validation

```json
{
  "type": "ai_semantic",
  "expected": "The page confirms the search was successful",
  "prompt": "Judge whether the response semantically confirms a successful search.",
  "min_confidence": 0.85
}
```

If `min_confidence` is set, an AI PASS below that threshold becomes a FAIL.

## AI element location

A step can use a natural-language description instead of a CSS selector:

```json
{"action": "click", "description": "the forgot password link"}
```

The framework tries deterministic selectors first and can use the configured AI provider when enabled.

## Self-healing selectors

For normal selector-based actions, a failed selector can be recovered using the page DOM and a heuristic/AI match. Successful recoveries are recorded in `healed_selectors` and shown in reports.

## Advanced API assertions

API validations inspect browser-generated network traffic; they do not create a separate HTTP client request.

```json
{
  "type": "api_response",
  "api_url": "/api/echo",
  "api_method": "POST",
  "api_status": 200,
  "api_request_headers": {"X-Test-Header": "framework"},
  "api_request_body": {"message": "hello"},
  "api_response_headers": {"X-Demo-Response": "echo"},
  "api_response_body": {"success": true, "message": "hello", "received": {"message": "hello"}},
  "api_json_schema": {
    "type": "object",
    "required": ["success", "message"],
    "properties": {"success": {"type": "boolean"}}
  },
  "api_response_time_ms": 2000
}
```

Existing `json_path`, `expected`, and `body_contains` assertions remain supported. JSON array paths such as `results.0` work as well.

## File upload/download validation

Upload:

```json
{
  "steps": [
    {"action": "upload", "selector": "#file", "value": "fixtures/sample.csv"}
  ],
  "validations": [
    {"type": "upload_validation", "file_path": "fixtures/sample.csv", "file_type": "csv",
     "expected_columns": ["First Name", "Last Name", "Country"]}
  ]
}
```

Download:

```json
{
  "steps": [{"action": "download", "selector": "#download"}],
  "validations": [
    {"type": "download_validation", "expected_filename": "sample.csv",
     "expected_extension": ".csv", "expected_mime": "text/csv",
     "expected_columns": ["First Name", "Last Name", "Country"]}
  ]
}
```

The download validator automatically uses the most recently captured download when `file_path` is omitted.

## Reports and diagnostics

- `reports/test_report.html` — interactive self-contained report
- `reports/test_report.json` — machine-readable results
- `reports/test_report.pdf` — PDF report when selected
- `reports/history.json` — rolling run history and flaky-test data
- `reports/screenshots/` — failure screenshots
- `reports/downloads/` — captured browser downloads

Failure analysis classifies failures such as selector, timeout, network, JavaScript, API, assertion, or unknown and provides an actionable suggestion. OpenAI analysis is optional and falls back to heuristics.

## Parallel execution

```bash
ai-test --file suite.json --workers 3
```

Each worker gets its own Playwright engine/browser. Results are restored to the original test order and reporting happens after all workers finish.

## Configuration

`config.yaml` supports browser, timeout, AI, reports, screenshots and parallel workers. Example:

```yaml
browser: chromium
headless: true
timeout: 30000
ai:
  provider: none
  model: gpt-4o-mini
  analyze_failures: true
report:
  output_dir: reports
  html: true
  json: true
  pdf: false
  formats: [html, json]
parallel:
  workers: 1
```

## CI/CD

GitHub Actions runs unit tests and browser E2E coverage across Python 3.10–3.12 and Chromium/Firefox/WebKit. It covers the core suite, AI locator, self-healing, parallel execution, advanced API/file assertions, and deterministic test generation. Reports are uploaded as workflow artifacts.

OpenAI is intentionally not required in CI; the deterministic fallback paths make the suite reproducible without secrets.

## Project structure

```text
ai-testing-framework/
├── src/ai_testing_framework/
│   ├── ai/                  # failure analysis + test generation
│   ├── automation/          # Playwright + network interception
│   ├── core/                # models, runner, config, parallel execution
│   ├── parsers/             # MD, JSON, CSV, XLSX
│   ├── reporters/            # HTML, JSON, PDF, history
│   └── validators/           # AI, UI, API, regex, table, file
├── tests/
├── examples/
├── reports/
├── config.yaml
├── requirements.txt
└── setup.py
```

## Roadmap / future work

The core framework is implemented through the current Phase 7 scope. Future enhancements can include richer autonomous exploration, visual regression, trace/video artifacts, broader JSON Schema support, authenticated-session management, and an agentic end-to-end test-planning layer.

License: MIT
