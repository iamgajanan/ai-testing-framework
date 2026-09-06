# Universal AI Testing Framework

A generic Python + Playwright framework for testing arbitrary web applications from **JSON, Markdown, CSV, or XLSX** test definitions. It combines deterministic browser assertions with optional OpenAI semantic validation, AI element location, self-healing selectors, diagnostics, reporting, parallel execution, test generation, advanced API assertions, file validation, and Phase B real-world browser workflows.

## Phase B status

Phase B is implemented and verified in the repository source. It includes cookie/session injection, localStorage bootstrap, reusable login-form synchronization, alert/dialog handling, popup creation and tab switching/closing, and same-origin multi-page test discovery. The CI workflow includes the Phase B regression suite across Python 3.10/3.11/3.12 and Chromium/Firefox/WebKit.

Run the Phase B suite with `ai-test --file tests/sample_tests/phase_b_suite.json --base-url http://127.0.0.1:8000 --ai-provider none`.

Generate tests across multiple pages with `ai-test generate --url http://127.0.0.1:8000 --output tests/generated_suite.json --max-pages 5`.

## Current capabilities

- Playwright: Chromium, Firefox, WebKit
- Browser actions: click, type/fill, select, check/uncheck, hover, press, wait, navigation/load-state, response, upload, download
- Auth/session workflows: cookies, localStorage, reusable login form
- Browser UI workflows: alerts/dialogs, popups, tabs/pages
- AI semantic validation and AI element location
- Self-healing selectors with confidence/history
- UI validators: presence, text, regex, URL, table, attribute, value, state, count
- API validation from real browser network traffic
- File upload/download validation for CSV, XLSX, JSON, PDF and common metadata
- HTML/JSON/PDF reports, screenshots, step traces and flaky-test history
- Failure diagnostics and optional OpenAI analysis
- AI test generation with deterministic fallback and same-origin multi-page discovery
- Parallel isolated browser workers
- CI matrix: Python 3.10/3.11/3.12 × Chromium/Firefox/WebKit

## Installation

Python 3.10+ is required. Install dependencies and the Playwright browser(s), then run `python examples/demo_app.py` and an `ai-test` suite.

OpenAI is optional; deterministic tests and generation work with `--ai-provider none`.

## Future roadmap

Visual regression, richer autonomous exploration, trace/video artifacts, broader JSON Schema support, and an agentic end-to-end planning layer remain future enhancements.

License: MIT
