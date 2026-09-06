# Universal AI Testing Framework

A generic Python + Playwright framework for testing arbitrary web applications from **JSON, Markdown, CSV, or XLSX** test definitions. It combines deterministic browser assertions with optional OpenAI semantic validation, AI element location, self-healing selectors, diagnostics, reporting, parallel execution, test generation, advanced API assertions, file validation, and Phase B real-world browser workflows.

## What is implemented

- Playwright automation: Chromium, Firefox, WebKit
- Actions: click, type/fill, select, check/uncheck, hover, press, wait, wait-for-load-state, wait-for-response, upload, download
- Phase B browser workflows: cookie/session injection, localStorage bootstrap, reusable login-form action, alert/dialog accept/dismiss, popup tabs, tab switching and tab closing
- AI semantic validation with local fallback when no API key is configured
- AI element locator from natural-language descriptions
- Self-healing selectors with confidence and healing history
- Deterministic validators: regex, element presence, text, URL, table, attribute, value, state and count
- API assertions against **real browser network traffic**
- File upload/download validation
- HTML, JSON and PDF reports with step execution trace and flaky-test history
- Screenshots on failures and console/network diagnostics
- Failure analysis with heuristic or OpenAI diagnosis
- AI-assisted test generation from a live URL
- Phase B same-origin multi-page discovery for generated suites (`--max-pages N`)
- Confidence thresholds for AI assertions
- Parallel isolated browser workers
- GitHub Actions CI with Python 3.10/3.11/3.12 × Chromium/Firefox/WebKit

## Phase B usage

Session bootstrap can be defined directly in JSON:

```json
{"action":"set_cookie","value":{"name":"session","value":"demo-session","path":"/"}}
{"action":"set_local_storage","value":{"role":"user"}}
```

A reusable login action accepts `username_selector`, `password_selector`, `submit_selector`, credentials, and an optional `success_url` to synchronize navigation:

```json
{"action":"login","value":{"username_selector":"#username","password_selector":"#password","submit_selector":"#login","username":"demo","password":"secret","success_url":"**/protected"}}
```

Dialogs can be configured before the triggering action:

```json
{"action":"accept_dialog"}
{"action":"click","selector":"#alert"}
```

Popup workflows use an explicit popup action:

```json
{"action":"open_popup","selector":"#popup"}
{"action":"switch_tab","value":"last"}
```

The included Phase B regression suite is `tests/sample_tests/phase_b_suite.json`.

## Multi-page test generation

Generation remains single-page by default. Discover same-origin links with:

```bash
ai-test generate \
  --url http://127.0.0.1:8000 \
  --output tests/generated_suite.json \
  --max-pages 5
```

The crawler stays on the starting origin, removes URL fragments, skips download links, caps discovery at 50 pages, and feeds each observed page independently into the existing heuristic or OpenAI generator. Generated test IDs are made unique across pages.

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
ai-test --file tests/sample_tests/test_suite.json --test TC-001
ai-test --file suite.json --workers 3
ai-test --file suite.json --format html json
ai-test --file suite.json --format all
ai-test generate --url http://127.0.0.1:8000 --output tests/generated_suite.json
ai-test generate --url http://127.0.0.1:8000 --output tests/generated_suite.json --max-pages 5
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

`config.yaml` supports browser, timeout, AI, reports, screenshots and parallel workers.

## CI/CD

GitHub Actions runs unit tests and browser E2E coverage across Python 3.10–3.12 and Chromium/Firefox/WebKit. It covers the core suite, AI locator, self-healing, parallel execution, advanced API/file assertions, **Phase B auth/session/dialog/tab workflows**, and deterministic **multi-page** test generation. Reports are uploaded as workflow artifacts.

OpenAI is intentionally not required in CI; deterministic fallback paths make the suite reproducible without secrets.

## Project structure

```text
ai-testing-framework/
├── src/ai_testing_framework/
│   ├── ai/                  # failure analysis + test generation/discovery
│   ├── automation/          # Playwright + network interception + browser workflows
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

The core framework is implemented through the current Phase B scope. Future enhancements can include richer autonomous exploration, visual regression, trace/video artifacts, broader JSON Schema support, and an agentic end-to-end test-planning layer.

License: MIT
