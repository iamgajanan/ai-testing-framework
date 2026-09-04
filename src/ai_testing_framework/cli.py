from __future__ import annotations

import argparse
import sys

from .core.test_runner import TestRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Universal AI-powered web test runner")
    parser.add_argument("--file", required=True, help="Path to .md or .json test suite")
    parser.add_argument("--browser", default="chromium", choices=["chromium", "firefox", "webkit"])
    parser.add_argument("--test", dest="test_id", help="Run only a specific test ID")
    parser.add_argument("--base-url", default="", help="Base URL for relative test URLs")
    parser.add_argument("--output", default="reports", help="Report output directory")
    parser.add_argument("--config", default=None, help="YAML configuration file")
    parser.add_argument("--ai-provider", choices=["openai", "none"], default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    runner = TestRunner(config=args.config, base_url=args.base_url)
    if args.ai_provider:
        runner.set_ai_provider(args.ai_provider)
    try:
        results = runner.run(args.file, args.browser, args.test_id, args.output)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    passed = sum(r.status == "PASS" for r in results)
    print(f"Tests: {len(results)} | Passed: {passed} | Failed: {len(results) - passed}")
    print(f"HTML report: {args.output}/test_report.html")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
