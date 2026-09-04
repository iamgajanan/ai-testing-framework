# Universal AI Testing Framework

Phase 2 of a generic AI-powered web testing framework built with Python, Playwright, Pytest, and OpenAI.

## Current capabilities

- Markdown, JSON, CSV, and XLSX test-suite parsers
- Data-driven tabular test definitions (multiple rows can build one test case)
- Playwright browser automation
- Selector-based actions: click, type, fill, select, upload, wait
- AI semantic response validation using OpenAI
- Deterministic validators: regex, element presence, text contains, URL contains, table validation
- HTML and JSON reports with screenshots on failure
- Console and API error capture
- CLI runner

## Requirements

- Python 3.10+
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

### CSV and XLSX

Tabular suites use one row per action or validation. Rows sharing the same `TestID` are grouped into one test case. Supported columns include:

`TestID`, `Name`, `URL`, `Action`, `Selector`, `Value`, `Timeout`, `Expected`, `ValidationType`, `Validation`, `ValidationSelector`, `Pattern`, `ExpectedColumns`, `RowCondition`, `ErrorChecks`.

Use `|` to separate multiple values in `ExpectedColumns` and `ErrorChecks`.

CSV example:

```csv
TestID,Name,URL,Action,Selector,Value,Expected,ValidationType,Validation,ErrorChecks
TC-CSV-001,CSV Search,/,type,#query,OpenAI,,,,
TC-CSV-001,CSV Search,/,click,#submit,,,,
TC-CSV-001,CSV Search,/,wait,#result,5000,,,,
TC-CSV-001,CSV Search,,,,,OpenAI,text_contains,,
```

Run either format directly:

```bash
ai-test --file tests/test_data/sample_suite.csv --browser chromium --base-url http://127.0.0.1:8000 --ai-provider none
ai-test --file path/to/suite.xlsx --browser chromium --base-url http://127.0.0.1:8000 --ai-provider none
```

## OpenAI semantic validation

```bash
export OPENAI_API_KEY="your-api-key"
ai-test --file tests/sample_tests/test_suite.json --ai-provider openai
```

Without an API key, `ai_semantic` validation uses a local heuristic fallback so the framework remains runnable offline.

## CLI

```text
ai-test --help
ai-test --file tests/sample_tests/test_suite.md
ai-test --file tests/sample_tests/test_suite.json --output reports
ai-test --file tests/sample_tests/test_suite.json --test TC-001
ai-test --file tests/test_data/sample_suite.csv --ai-provider none
```

## Project structure

```text
ai-testing-framework/
├── src/ai_testing_framework/
│   ├── automation/
│   ├── core/
│   ├── parsers/
│   │   ├── csv_parser.py
│   │   ├── json_parser.py
│   │   ├── md_parser.py
│   │   └── xlsx_parser.py
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

## Roadmap

Next: richer Playwright actions, API/network assertions, cross-browser matrices, trace/video artifacts, and self-healing selectors.

License: MIT
