# Universal AI Testing Framework

A production-oriented Python + Playwright framework for testing arbitrary web applications from JSON, Markdown, CSV, or XLSX test definitions. It combines deterministic browser automation with optional AI capabilities, self-healing, autonomous exploration, API/file validation, visual regression, diagnostics, reporting, and a SaaS execution foundation.

## What this project does

The framework can be used in two ways:

1. **Local testing framework / CLI** — define or generate tests and execute them against any web application.
2. **SaaS foundation** — authenticate users, isolate organizations/projects, store test suites and versions, create executions, queue work, run tests in isolated worker processes, and store artifacts.

The existing Python + Playwright engine remains the execution core. The SaaS layer is intentionally thin and does not replace the existing CLI/test contract.

---

## Feature overview

### Browser automation

- Playwright support for **Chromium, Firefox, and WebKit**.
- Click, type/fill, select, check/uncheck, hover, press, wait, navigation/load-state, response, upload, download, and JavaScript evaluation actions.
- Cookies and localStorage/session workflows.
- Reusable login/authentication workflows.
- Alerts and browser dialogs.
- Popup windows, tabs, and multiple pages.
- Parallel isolated browser workers.

### AI-powered testing

- AI semantic validation of UI behavior/content.
- AI-assisted element location.
- Self-healing selectors with confidence/history.
- AI failure analysis with deterministic fallback paths.
- AI test generation from a live application.
- Same-origin multi-page discovery.
- Authenticated test generation/crawling.
- Agentic workflow planning.
- Context-aware realistic test-data generation.
- Autonomous exploration → test generation → execution.

OpenAI is optional. All core testing and the agentic fallback paths can run with `--ai-provider none`.

### API, network, and files

- API validation using real browser network traffic.
- Network route mocking/stubbing for deterministic success/error scenarios.
- File upload/download validation for CSV, XLSX, JSON, PDF, and common metadata.
- Response and network assertions.

### Validation

- Presence/visibility.
- Text and regex.
- URL.
- Table data.
- Attributes.
- Input values.
- Element state.
- Element counts.
- AI semantic assertions.

### Reporting and diagnostics

- HTML reports.
- JSON reports.
- PDF reports.
- Screenshots.
- Step traces.
- Playwright trace/video artifacts on failures.
- Failure diagnostics and AI failure analysis.
- Flaky-test history.
- Visual regression screenshot comparison with configurable pixel-difference thresholds.

### SaaS foundation — Phase 1A

The SaaS boundary is under `ai_testing_framework.server`, while `ai_testing_framework.cloud` contains engine-neutral execution contracts and the adapter around the existing `TestRunner`.

Implemented foundation features include:

- FastAPI health/readiness API.
- Supabase Auth JWT verification for protected API routes.
- Multi-tenant organizations/workspaces.
- Organization memberships with automatic owner membership.
- Project-scoped tenant isolation.
- PostgreSQL persistence through Supabase.
- Row Level Security (RLS) policies for tenant/project isolation.
- Authenticated `/v1/me`, organization, project, and execution APIs.
- Persistent execution records and lifecycle timestamps.
- Queue-backed execution with atomic worker claiming/completion.
- Local asynchronous worker execution through `ai-test-worker`.
- Project-scoped API keys with SHA-256 hashed secrets.
- API-key scopes, creation, listing, and revocation.
- Private Supabase Storage for execution artifacts.
- Artifact metadata and signed download URLs.
- Isolated SaaS execution processes with hard execution timeouts.
- Process-tree cleanup on timeout.
- Production Docker worker foundation.
- Chromium/Firefox/WebKit worker support.
- CPU, memory, and PID limits plus non-root worker/container hardening.
- Project-scoped test suite storage.
- Immutable versioned test suite uploads.
- JSON/YAML/YML upload validation.
- UTF-8 validation and a 10 MB suite upload limit.
- SHA-256 test-suite content fingerprints.
- Private `test-suites` storage bucket.
- Signed test-suite version download URLs.
- Multipart upload API support.

The SaaS API does not modify the existing local CLI execution contract.

---

# Installation

## Requirements

- Python **3.10+**
- Node.js is **not required** for the existing Python/CLI engine.
- Playwright-supported browser dependencies.
- Optional: OpenAI API access for AI-powered planning/semantic capabilities.
- Optional: Supabase project for SaaS features.

## Clone the repository

```bash
git clone https://github.com/iamgajanan/ai-testing-framework.git
cd ai-testing-framework
```

## Create a virtual environment

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

## Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

## Install Playwright browsers

Install all browsers:

```bash
playwright install
```

Or install a single browser:

```bash
playwright install chromium
playwright install firefox
playwright install webkit
```

On Linux CI/servers, install browser system dependencies as well:

```bash
playwright install --with-deps chromium
```

## Verify installation

```bash
ai-test --help
ai-test-worker --help
pytest -q
```

---

# Quick start

## 1. Start the demo application

```bash
python examples/demo_app.py
```

The demo application is normally available at:

```text
http://127.0.0.1:8000
```

## 2. Run the core sample suite

```bash
ai-test \
  --file tests/sample_tests/test_suite.json \
  --base-url http://127.0.0.1:8000 \
  --ai-provider none \
  --format html json
```

Reports are written under `reports/`.

## 3. Run a broader sample suite

```bash
ai-test \
  --file tests/sample_tests/advanced_suite.json \
  --base-url http://127.0.0.1:8000 \
  --ai-provider none \
  --format html json
```

## 4. Run with a specific browser

```bash
ai-test \
  --file tests/sample_tests/test_suite.json \
  --base-url http://127.0.0.1:8000 \
  --ai-provider none \
  --browser chromium
```

Supported browsers are `chromium`, `firefox`, and `webkit`.

## 5. Run in parallel

```bash
ai-test \
  --file tests/sample_tests/parallel_suite.json \
  --base-url http://127.0.0.1:8000 \
  --ai-provider none \
  --workers 3
```

---

# Test definitions

The framework supports test definitions from:

- JSON
- Markdown
- CSV
- XLSX

A typical JSON suite contains test cases and browser steps/assertions. Existing suites in `tests/sample_tests/` provide working examples for the supported functionality.

The framework can also generate executable suites from a live application instead of requiring a hand-authored suite.

---

# AI test generation

Generate a suite by exploring a live application:

```bash
ai-test generate \
  --url http://127.0.0.1:8000 \
  --output /tmp/generated_suite.json \
  --ai-provider none \
  --max-pages 3
```

Then execute the generated suite:

```bash
ai-test \
  --file /tmp/generated_suite.json \
  --base-url http://127.0.0.1:8000 \
  --ai-provider none
```

The generator discovers same-origin pages and creates executable tests from observed UI state.

---

# Authenticated crawling and generation

Create a login JSON object containing the login URL, selectors, credentials, and optionally the expected success URL:

```json
{
  "url": "http://127.0.0.1:8000/auth",
  "username_selector": "#username",
  "password_selector": "#password",
  "submit_selector": "#login",
  "username": "demo",
  "password": "secret",
  "success_url": "http://127.0.0.1:8000/protected"
}
```

Generate authenticated tests:

```bash
ai-test generate \
  --url http://127.0.0.1:8000/auth \
  --output tests/auth_suite.json \
  --login-json login.json \
  --max-pages 5 \
  --ai-provider none
```

The authenticated crawler logs in and starts discovery from the authenticated success URL.

---

# Autonomous testing

Phase D provides a complete autonomous workflow:

**live application → exploration → same-origin discovery → optional goal planning → generated executable suite → execution → normal reports**

Run it with:

```bash
ai-test autonomous \
  --url http://127.0.0.1:8000 \
  --output reports/autonomous \
  --max-pages 5 \
  --goal "Explore the application and verify its primary user-facing workflows" \
  --ai-provider none
```

Authenticated autonomous testing can reuse the login contract:

```bash
ai-test autonomous \
  --url http://127.0.0.1:8000/auth \
  --login-json login.json \
  --max-pages 5 \
  --ai-provider none
```

A successful autonomous run produces:

- `generated_suite.json` — executable tests discovered/generated from the application.
- `autonomous_run.json` — exploration/goal manifest and generated test count.
- `test_report.html` / `test_report.json` — standard framework results.

---

# Agentic planning and test data

## Workflow planning

```bash
ai-test plan \
  --description "A customer search application" \
  --workflow "Search for a customer" \
  --output /tmp/plan.json \
  --ai-provider none
```

## Realistic test-data generation

```bash
ai-test data \
  --fields '[{"name":"email","type":"email"},{"name":"start_date","type":"date"}]' \
  --count 5 \
  --output /tmp/data.json \
  --ai-provider none
```

Both commands have deterministic fallback behavior when OpenAI is unavailable.

---

# Phase C network mocking and visual regression

Network route mocking supports deterministic API scenarios such as successful responses and controlled error responses. The sample Phase C suite exercises route mocks together with visual regression.

Create a visual baseline and run the Phase C suite:

```bash
python tests/create_visual_baseline.py --browser chromium
ai-test \
  --file tests/sample_tests/phase_c_suite.json \
  --base-url http://127.0.0.1:8000 \
  --ai-provider none \
  --browser chromium \
  --format html json
```

Visual comparisons use configurable pixel-difference thresholds so small rendering differences can be controlled without disabling visual verification.

---

# SaaS API

The SaaS API is a FastAPI application under `ai_testing_framework.server`.

Start it locally:

```bash
uvicorn ai_testing_framework.server.app:app --host 127.0.0.1 --port 8001
```

Health endpoints:

```text
GET /health
GET /ready
```

## Authentication and tenancy

Configure:

```text
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_PUBLISHABLE_KEY=<publishable-key>
```

Protected API requests use a Supabase Auth JWT. The JWT subject (`sub`) identifies the authenticated user, and RLS provides tenant/project isolation.

The API layer uses the publishable key together with the user's JWT for Supabase Data API access. A Supabase service-role/secret key is not exposed to the API client layer.

Core authenticated endpoints include:

```text
GET  /v1/me
GET  /v1/organizations
POST /v1/organizations
GET  /v1/projects?organization_id=<uuid>
POST /v1/projects
POST /v1/executions
```

---

# Test suite storage API

Test suites are project-scoped and stored privately with immutable versions.

Supported uploads:

- `.json`
- `.yaml`
- `.yml`
- UTF-8 encoded
- Maximum size: **10 MB**

Each uploaded version stores metadata including:

- suite ID/version
- organization/project ownership
- filename/content type
- byte size
- SHA-256 fingerprint
- private storage path
- creator and timestamp

The API also supports signed download URLs for authorized users.

The storage model is:

```text
organization
  └── project
      └── test suite
          ├── v1
          ├── v2
          └── v3
```

---

# Execution queue and workers

The SaaS execution flow is:

```text
CLI / Dashboard / CI
        ↓
     FastAPI
        ↓
   authenticated
   project-scoped API
        ↓
 persistent execution
       record
        ↓
     job queue
        ↓
 atomic worker claim
        ↓
 isolated execution process
        ↓
 existing TestRunner / Playwright engine
        ↓
 pass/fail + timestamps
        ↓
 artifacts + signed URLs
```

A worker can process one queued execution at a time:

```bash
ai-test-worker --once --poll-seconds 2
```

The cloud runner foundation adds hard execution timeouts and process-tree cleanup so a stuck browser/test cannot remain running indefinitely.

---

# API keys and artifacts

Project-scoped API keys are stored as SHA-256 hashes rather than plaintext secrets. Keys support scopes and can be created, listed, and revoked.

Execution artifacts are stored in private Supabase Storage. Artifact metadata is persisted against the execution, and authorized users receive signed URLs instead of public bucket URLs.

---

# Database and Supabase setup

The repository contains Supabase migrations for the SaaS foundation. The schema includes organizations, organization memberships, projects, executions, API keys, artifacts, test suites, and immutable test suite versions, with indexes, timestamps, grants, and RLS policies where appropriate.

For a Supabase-backed deployment, configure the project's database and private storage using the migrations in:

```text
supabase/migrations/
```

Keep service-role/secret credentials server-side only. Storage access should use the Storage API and private buckets with signed URLs.

---

# Production worker/container

The cloud-runner foundation includes a production Docker worker designed for isolated execution.

Security/resource controls include:

- non-root execution
- dropped container capabilities
- CPU limits
- memory limits
- PID limits
- hard execution timeout
- process-tree cleanup
- Playwright browser isolation
- Chromium/Firefox/WebKit support

The worker environment should be configured through environment variables/secrets rather than committed credentials.

---

# Running the complete local test suite

Run unit tests:

```bash
pytest -q
```

Run the core E2E suite manually after starting the demo app:

```bash
ai-test \
  --file tests/sample_tests/test_suite.json \
  --base-url http://127.0.0.1:8000 \
  --ai-provider none \
  --browser chromium \
  --format html json
```

Other useful regression suites include:

```text
tests/sample_tests/ai_locator_suite.json
tests/sample_tests/self_healing_suite.json
tests/sample_tests/parallel_suite.json
tests/sample_tests/advanced_suite.json
tests/sample_tests/phase_b_suite.json
tests/sample_tests/phase_c_suite.json
```

The repository also contains focused regression tests for the SaaS API, execution queue, API keys, artifacts, test-suite storage, cloud runner, and existing framework behavior.

---

# CI/CD

GitHub Actions runs the complete test matrix on pushes to `main` and pull requests targeting `main`.

The matrix covers:

```text
Python 3.10 × Chromium
Python 3.10 × Firefox
Python 3.10 × WebKit
Python 3.11 × Chromium
Python 3.11 × Firefox
Python 3.11 × WebKit
Python 3.12 × Chromium
Python 3.12 × Firefox
Python 3.12 × WebKit
```

Each matrix job performs:

1. dependency installation
2. Playwright browser installation
3. unit tests
4. demo application startup
5. core E2E suite
6. AI locator regression
7. self-healing regression
8. parallel execution regression
9. API/file validation regression
10. Phase B authentication/dialog/tab regression
11. Phase C network mocking/visual regression
12. authenticated crawler verification
13. failure trace/video artifact verification
14. AI generation and multi-page discovery
15. Phase D autonomous testing
16. agentic planning/data generation
17. report artifact upload

The CI workflow is defined in `.github/workflows/ci.yml`.

---

# Recommended development workflow

When changing the framework:

```bash
# create/activate environment
python3 -m venv .venv
source .venv/bin/activate

# install
a pip install -r requirements.txt
pip install -e .

# install browser
playwright install chromium

# run unit tests
pytest -q

# run a relevant E2E suite
ai-test --file tests/sample_tests/test_suite.json --base-url http://127.0.0.1:8000 --ai-provider none
```

Before merging changes, run the relevant local tests and ensure the GitHub Actions matrix is green.

---

# Project structure

```text
ai-testing-framework/
├── src/ai_testing_framework/
│   ├── ai/                 # AI planning, generation, semantic capabilities
│   ├── cloud/              # engine-neutral SaaS execution contracts/adapter
│   ├── server/             # FastAPI, auth, queue, storage, worker APIs
│   ├── ...                 # browser engine, validators, reports, CLI, etc.
├── tests/
│   └── sample_tests/       # representative executable test suites
├── examples/
│   └── demo_app.py         # local application used by CI/E2E tests
├── supabase/
│   └── migrations/         # SaaS database/RLS/storage migrations
├── .github/workflows/
│   └── ci.yml              # 3 Python versions × 3 browsers
├── requirements.txt
└── setup.py
```

---

# Backward compatibility

The SaaS foundation is additive. Existing local test definitions, the `ai-test` CLI, Playwright engine, reports, and existing execution behavior remain the core contract.

The cloud API and workers adapt the existing engine rather than requiring users to rewrite their existing suites.

---

# Security notes

- Use Supabase Auth JWTs for authenticated SaaS requests.
- Keep service-role/secret keys out of clients and source control.
- Use RLS for tenant/project isolation.
- Keep test-suite and execution artifact buckets private.
- Use signed URLs for authorized downloads.
- API-key secrets are stored as SHA-256 hashes.
- Run production workers as non-root with restricted capabilities/resources.
- Treat test definitions, URLs, credentials, and inbound application data as untrusted input.
- Store credentials in environment/secrets management rather than test files committed to Git.

---

# Roadmap

The completed foundation progressively builds the SaaS platform around the existing engine. The next product layer can add the web dashboard, richer execution management, usage/billing, GitHub integration, and enterprise controls while retaining the current execution core.

---

# License

MIT
