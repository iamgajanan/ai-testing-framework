# Universal AI Testing Framework

A generic Python + Playwright framework for testing arbitrary web applications from **JSON, Markdown, CSV, or XLSX** test definitions. It combines deterministic browser assertions with optional OpenAI semantic validation, AI element location, self-healing selectors, diagnostics, reporting, parallel execution, multi-page generation, Phase C agentic capabilities, and Phase D autonomous testing.

## SaaS foundation

The framework now includes a thin SaaS API boundary without changing the existing testing engine. The API lives under `ai_testing_framework.server`, while `ai_testing_framework.cloud` contains engine-neutral execution contracts and an adapter around the existing `TestRunner`.

Phase 1A Step 2 adds the multi-tenant identity and persistence foundation:

- Supabase Auth JWT verification for protected API routes.
- PostgreSQL organizations, organization memberships, and projects.
- Owner membership is created automatically when a user creates an organization.
- Row Level Security (RLS) isolates organizations, memberships, and projects by authenticated tenant membership.
- Tenant API endpoints for the current user, organizations, and projects.
- Publishable-key + user-token access to Supabase Data API; no service-role/secret key is used by the API layer.

Configure these server-side environment variables before using tenant endpoints:

```text
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_PUBLISHABLE_KEY=<publishable-key>
```

Run the API locally with:

```bash
uvicorn ai_testing_framework.server.app:app --host 127.0.0.1 --port 8001
```

Health endpoints:

```text
GET /health
GET /ready
```

Authenticated endpoints:

```text
GET  /v1/me
GET  /v1/organizations
POST /v1/organizations
GET  /v1/projects?organization_id=<uuid>
POST /v1/projects
POST /v1/executions
```

The execution endpoint is now authenticated, but queue-backed execution and persistent execution records remain the next Phase 1A step.

## Phase D — Autonomous testing

Phase D adds the first autonomous end-to-end workflow. Instead of starting with a hand-authored test file, the framework can explore a live application, discover same-origin pages, generate executable tests from observed UI state, optionally plan against a testing goal, execute the generated suite, and produce the normal HTML/JSON reports.

```bash
ai-test autonomous \
  --url http://127.0.0.1:8000 \
  --output reports/autonomous \
  --max-pages 5 \
  --goal "Explore the application and verify its primary user-facing workflows" \
  --ai-provider none
```

The autonomous command can also reuse the authenticated crawler contract:

```bash
ai-test autonomous --url http://127.0.0.1:8000/auth \
  --login-json login.json --max-pages 5 --ai-provider none
```

The run writes:

- `generated_suite.json` — executable tests discovered from the application.
- `autonomous_run.json` — exploration/goal manifest and generated test count.
- `test_report.html` / `test_report.json` — standard framework results.

`--ai-provider none` remains fully deterministic. OpenAI is optional and can be used for the workflow-planning portion of an autonomous run.

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
- Autonomous exploration, test generation and execution
- Agentic workflow planning and realistic test-data generation
- Parallel isolated browser workers
- CI matrix: Python 3.10/3.11/3.12 × Chromium/Firefox/WebKit

## Installation

Python 3.10+ is required. Install dependencies and the Playwright browser(s), then run `python examples/demo_app.py` and an `ai-test` suite.

OpenAI is optional; deterministic tests and agentic fallbacks work with `--ai-provider none`.

## Roadmap

Phase 1A progressively adds the SaaS foundation around the existing engine: authentication, organizations/workspaces, projects, API keys, persistent execution records and queue-backed cloud execution. Later phases add the dashboard, usage/billing, GitHub integration and enterprise controls.

License: MIT
