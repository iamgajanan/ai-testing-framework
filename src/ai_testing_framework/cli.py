from __future__ import annotations

import argparse
import os
import sys

from .core.test_runner import TestRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Universal AI-powered web test runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run a test suite (default when no subcommand given)")
    _add_run_args(run_p)

    gen_p = sub.add_parser("generate", help="Generate a test suite from a live URL")
    gen_p.add_argument("--url", required=True, help="URL to generate tests for")
    gen_p.add_argument("--output", default="tests/generated_suite.json", help="Output path for generated JSON suite")
    gen_p.add_argument("--browser", default="chromium", choices=["chromium", "firefox", "webkit"])
    gen_p.add_argument("--base-url", default="", help="Base URL (stripped from relative paths)")
    gen_p.add_argument("--max-pages", type=int, default=1, metavar="N", help="Discover up to N same-origin pages (default: 1)")
    gen_p.add_argument("--ai-provider", choices=["openai", "none"], default="none")
    gen_p.add_argument("--config", default=None)

    _add_run_args(parser)
    return parser


def _add_run_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--file", default=None, help="Path to test suite file")
    p.add_argument("--browser", default="chromium", choices=["chromium", "firefox", "webkit"])
    p.add_argument("--test", dest="test_id", default=None, help="Run only a specific test ID")
    p.add_argument("--base-url", default="", help="Base URL for relative test URLs")
    p.add_argument("--output", default="reports", help="Report output directory")
    p.add_argument("--config", default=None, help="YAML configuration file")
    p.add_argument("--ai-provider", choices=["openai", "none"], default=None)
    p.add_argument("--workers", type=int, default=None, metavar="N", help="Parallel browser workers (default: 1 = sequential)")
    p.add_argument("--format", dest="formats", nargs="+", choices=["html", "json", "pdf", "all"], default=None, metavar="FORMAT", help="Report formats: html json pdf all")


def _write_github_summary(results, output_dir: str, workers: int = 1) -> None:
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_file:
        return
    total, passed = len(results), sum(r.status == "PASS" for r in results)
    failed = total - passed
    dur = sum(r.duration for r in results)
    rate = (passed / total * 100) if total else 0
    mode = f"{workers} workers (parallel)" if workers > 1 else "sequential"
    lines = ["## 🤖 AI Test Report", "", "| Total | Passed | Failed | Pass Rate | Duration | Mode |", "|-------|--------|--------|-----------|----------|------|", f"| {total} | {passed} | {failed} | {rate:.1f}% | {dur:.1f}s | {mode} |", "", "### Results", "", "| ID | Name | Status | Duration |", "|----|------|--------|----------|"]
    for r in results:
        lines.append(f"| `{r.id}` | {r.name} | {'✅' if r.status == 'PASS' else '❌'} {r.status} | {r.duration:.2f}s |")
    failed_results = [r for r in results if r.status == "FAIL" and r.failure_analysis]
    if failed_results:
        lines += ["", "### 🔍 Failure Analysis", ""]
        for r in failed_results:
            fa = r.failure_analysis
            lines.append(f"- **{r.id}** [{fa.get('category','?')}]: {fa.get('root_cause','')}")
    healed = [r for r in results if r.healed_selectors]
    if healed:
        lines += ["", "### ⚕️ Self-healed selectors", ""]
        for r in healed:
            for h in r.healed_selectors:
                lines.append(f"- **{r.id}**: `{h['failed_selector']}` → `{h['healed_selector']}` (confidence {h.get('confidence', 0):.0%})")
    try:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except OSError:
        pass


def _cmd_run(args) -> int:
    if not args.file:
        print("ERROR: --file is required for the run command.", file=sys.stderr)
        return 2
    formats = ["html", "json", "pdf"] if args.formats and "all" in args.formats else args.formats
    runner = TestRunner(config=args.config, base_url=args.base_url)
    if args.ai_provider:
        runner.set_ai_provider(args.ai_provider)
    try:
        results = runner.run(args.file, browser=args.browser, test_id=args.test_id, output_dir=args.output, formats=formats, workers=args.workers)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    passed = sum(r.status == "PASS" for r in results)
    failed = len(results) - passed
    w = args.workers or 1
    print(f"Tests: {len(results)} | Passed: {passed} | Failed: {failed}{f' ({w} workers)' if w > 1 else ''}")
    print(f"HTML report: {args.output}/test_report.html")
    for r in results:
        if r.status == "FAIL" and r.failure_analysis:
            fa = r.failure_analysis
            print(f"\n  ❌ {r.id} [{fa.get('category', 'unknown')}]: {fa.get('root_cause', '')}")
            if fa.get("suggested_fix"):
                print(f"     💡 {fa['suggested_fix']}")
    _write_github_summary(results, args.output, workers=w)
    return 0 if failed == 0 else 1


def _cmd_generate(args) -> int:
    from .ai.test_generator import TestGenerator
    generator = TestGenerator(provider=args.ai_provider or "none")
    print(f"Discovering up to {args.max_pages} page(s) from {args.url} ...")
    try:
        path = generator.generate(url=args.url, output_path=args.output, browser=args.browser, base_url=args.base_url, max_pages=args.max_pages)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"✅ Generated test suite written to: {path}")
    print(f"   Run with: ai-test --file {path} --base-url <your-base-url>")
    return 0


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "generate":
        return _cmd_generate(args)
    return _cmd_run(args)


if __name__ == "__main__":
    raise SystemExit(main())
