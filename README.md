# Universal AI Testing Framework

Phase 1 MVP of a generic AI-powered web testing framework built with Python, Playwright, Pytest, and OpenAI.

## MVP

- Markdown and JSON test-suite parsers
- Playwright browser automation
- Selector-based actions: click, type, fill, select, upload, wait
- AI semantic response validation using OpenAI
- Deterministic validators: regex, element presence, text contains, URL contains
- HTML and JSON reports with screenshots on failure
- Console and API error capture
- CLI runner

## Requirements

- Python 3.9+
- Playwright browsers
- Optional `OPENAI_API_KEY` for AI validation

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Quick start

Run the included local demo app and tests:

```bash
python examples/demo_app.py
ai-test --file tests/sample_tests/test_suite.json --browser chromium --base-url http://127.0.0.1:8000
```

Then open `reports/test_report.html`.

To run the Markdown suite:

```bash
ai-test --file tests/sample_tests/test_suite.md --browser chromium --base-url http://127.0.0.1:8000
```

To use OpenAI semantic validation:

```bash
export OPENAI_API_KEY="your-api-key"
ai-test --file tests/sample_tests/test_suite.json --ai-provider openai
```

Without an API key, `ai_semantic` validation uses a local heuristic fallback so the framework remains runnable offline.

## Project structure

```text
ai-testing-framework/
├── src/ai_testing_framework/
│   ├── automation/
│   ├── core/
│   ├── parsers/
│   ├── reporters/
│   └── validators/
├── tests/
│   ├── sample_tests/
│   └── test_data/
├── examples/
├── reports/
├── config.yaml
├── requirements.txt
└── setup.py
```

## Test formats

### JSON

```json
{
  "test_suite": "Demo",
  "tests": [
    {
      "id": "TC-001",
      "name": "Search",
      "url": "/",
      "steps": [
        {"action": "type", "selector": "#query", "value": "OpenAI"},
        {"action": "click", "selector": "#submit"},
        {"action": "wait", "selector": "#result", "timeout": 5000}
      ],
      "validations": [
        {"type": "text_contains", "selector": "#result", "expected": "OpenAI"},
        {"type": "ai_semantic", "prompt": "Check whether the result is a relevant search result for OpenAI", "expected": "A result about OpenAI"}
      ]
    }
  ]
}
```

### Markdown

Use the format shown in `tests/sample_tests/test_suite.md`. The parser recognizes suite/test headings, URL, numbered steps, Expected, AI Validation, Fallback Check, Validation, and UI Check lines.

## CLI

```text
ai-test --help
ai-test --file tests/sample_tests/test_suite.md
ai-test --file tests/sample_tests/test_suite.json --report html --output reports
ai-test --file tests/sample_tests/test_suite.json --test TC-001
```

## Notes

This is the Phase 1 MVP. Self-healing selectors, CSV/XLSX parsing, API interception assertions, PDF reports, cross-browser matrices, and advanced concurrency are intentionally reserved for later phases.

License: MIT
