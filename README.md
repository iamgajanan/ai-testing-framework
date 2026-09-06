# Universal AI Testing Framework

A generic Python + Playwright framework for testing arbitrary web applications from **JSON, Markdown, CSV, or XLSX** test definitions. It combines deterministic browser assertions with optional OpenAI semantic validation, AI element location, self-healing selectors, diagnostics, reporting, parallel execution, multi-page generation, and Phase C agentic capabilities.

## Phase C — Agentic capabilities

Phase C is implemented and CI-verified. It adds:

- **Network route mocking** with `mock_route` / `route_mock` steps for deterministic API success/error scenarios.
- **Authenticated crawling** that logs in with configured selectors and starts discovery from the authenticated success URL.
- **Workflow AI planner** via `ai-test plan`, with deterministic fallback when OpenAI is unavailable.
- **Realistic test data generation** via `ai-test data`, using field name/type/context-aware deterministic data or OpenAI.
- **Playwright traces and video artifacts on failure**, surfaced as links in the HTML report.
- **Visual regression** with screenshot comparison and configurable pixel-difference thresholds.

### Phase C examples

```bash
ai-test plan --description "A customer search application" --workflow "Search for a customer"
ai-test data --fields '[{"name":"email","type":"email"},{"name":"start_date","type":"date"}]' --count 5
ai-test generate --url http://127.0.0.1:8000/auth --output tests/auth_suite.json --max-pages 5 \
  --login-json login.json
ai-test --file tests/sample_tests/phase_c_suite.json --base-url http://127.0.0.1:8000 --ai-provider none
```

A login JSON object contains `url`, `username_selector`, `password_selector`, `submit_selector`, `username`, `password`, and optionally `success_url`.

## Current capabilities

- Playwright: Chromium, Firefox, WebKit
- Browser actions: click, type/fill, select, check/uncheck, hover, press, wait, navigation/load-state, response, upload, download, JavaScript evaluation
- Auth/session workflows: cookies, localStorage, reusable login form
- Browser UI workflows: alerts/dialogs, popups, tabs/pages
- Network route mocking/stubbing
- AI semantic validation and AI element location
- Self-healing selectors with confidence/history
- UI validators: presence, text, regex, URL, table, attribute, value, state, count
- API validation from real browser network traffic
- File upload/download validation for CSV, XLSX, JSON, PDF and common metadata
- Visual regression screenshot diff
- HTML/JSON/PDF reports, screenshots, step traces, failure trace/video artifacts and flaky-test history
- AI failure analysis and deterministic fallback paths
- AI test generation, authenticated crawling and same-origin multi-page discovery
- Agentic workflow planning and realistic test-data generation
- Parallel isolated browser workers
- CI matrix: Python 3.10/3.11/3.12 × Chromium/Firefox/WebKit

## Installation

Python 3.10+ is required. Install dependencies and the Playwright browser(s), then run `python examples/demo_app.py` and an `ai-test` suite.

OpenAI is optional; deterministic tests and agentic fallbacks work with `--ai-provider none`.

## Roadmap

Phase C completes the planned agentic foundation. Future enhancements can build on it with richer autonomous exploration, vision-based validation, broader JSON Schema support, and deeper workflow planning.

License: MIT
