from __future__ import annotations

import argparse
import os
import sys

from .core.test_runner import TestRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Universal AI-powered web test runner")
    parser.add_argument("--file",     required=True,  help="Path to .md, .json, .csv, or .xlsx test suite")
    parser.add_argument("--browser",  default="chromium", choices=["chromium", "firefox", "webkit"])
    parser.add_argument("--test",     dest="test_id", help="Run only a specific test ID")
    parser.add_argument("--base-url", default="",     help="Base URL for relative test URLs")
    parser.add_argument("--output",   default="reports", help="Report output directory")
    parser.add_argument("--config",   default=None,   help="YAML configuration file")
    parser.add_argument("--ai-provider", choices=["openai", "none"], default=None)
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        metavar="N",
        help="Parallel browser workers (default: 1 = sequential)",
    )
    parser.add_argument(
        "--format",
        dest="formats",
        nargs="+",
        choices=["html", "json", "pdf", "all"],
        default=None,
        metavar="FORMAT",
        help="Report formats to emit: html json pdf all  (default: html json)",
    )
    return parser


def _write_github_summary(results, output_dir: str, workers: int = 1) -> None:
    """Write a Markdown step summary to $GITHUB_STEP_SUMMARY if running in CI."""
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_file:
        return
    total  = len(results)
    passed = sum(r.status == "PASS" for r in results)
    failed = total - passed
    dur    = sum(r.duration for r in results)
    rate   = (passed / total * 100) if total else 0
    mode   = f"{workers} workers (parallel)" if workers > 1 else "sequential"

    lines = [
        "## 🤖 AI Test Report",
        "",
        f"| Total | Passed | Failed | Pass Rate | Duration | Mode |",
        f"|-------|--------|--------|-----------|----------|------|",
        f"| {total} | {passed} | {failed} | {rate:.1f}% | {dur:.1f}s | {mode} |",
        "",
        "### Results",
        "",
        "| ID | Name | Status | Duration |",
        "|----|------|--------|----------|",
    ]
    for r in results:
        icon = "✅" if r.status == "PASS" else "❌"
        lines.append(f"| `{r.id}` | {r.name} | {icon} {r.status} | {r.duration:.2f}s |")

    healed = [r for r in results if r.healed_selectors]
    if healed:
        lines += ["", "### ⚕️ Self-healed selectors", ""]
        for r in healed:
            for h in r.healed_selectors:
                lines.append(
                    f"- **{r.id}**: `{h['failed_selector']}` → `{h['healed_selector']}` "
                    f"(confidence {h.get('confidence', 0):.0%})"
                )

    try:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except OSError:
        pass


def main() -> int:
    args = build_parser().parse_args()

    # Resolve --format all → all three formats
    formats = None
    if args.formats:
        if "all" in args.formats:
            formats = ["html", "json", "pdf"]
        else:
            formats = args.formats

    runner = TestRunner(config=args.config, base_url=args.base_url)
    if args.ai_provider:
        runner.set_ai_provider(args.ai_provider)

    try:
        results = runner.run(
            args.file,
            browser=args.browser,
            test_id=args.test_id,
            output_dir=args.output,
            formats=formats,
            workers=args.workers,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    passed = sum(r.status == "PASS" for r in results)
    failed = len(results) - passed
    w = args.workers or 1
    mode = f" ({w} workers)" if w > 1 else ""
    print(f"Tests: {len(results)} | Passed: {passed} | Failed: {failed}{mode}")
    print(f"HTML report: {args.output}/test_report.html")

    _write_github_summary(results, args.output, workers=w)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
