"""Command line: `inbox-planner eval` scores the agents on the demo mailbox."""

import argparse
import sys
from pathlib import Path

from inbox_planner import __version__
from inbox_planner.evaluation.report import render_report
from inbox_planner.evaluation.runner import run_extraction, run_triage, score_pipeline
from inbox_planner.llm.base import CacheMiss, LLMUnavailable
from inbox_planner.llm.cache import CachedClient
from inbox_planner.llm.claude_code import ClaudeCodeClient

MODELS = ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5")
DEFAULT_PIPELINE = ("claude-haiku-5-5", "claude-sonnet-5-5")


def _models(value: str) -> list[str]:
    return [m.strip() for m in value.split(",") if m.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="inbox-planner")
    parser.add_argument("--version", action="version", version=f"inbox-planner {__version__}")
    commands = parser.add_subparsers(dest="command")

    evaluate = commands.add_parser("eval", help="score triage and extraction on the demo mailbox")
    evaluate.add_argument("--triage-models", type=_models, default=list(MODELS))
    evaluate.add_argument("--extraction-models", type=_models, default=list(MODELS))
    evaluate.add_argument(
        "--pipeline",
        type=_models,
        default=list(DEFAULT_PIPELINE),
        help="triage model and extraction model of the end-to-end chain",
    )
    evaluate.add_argument(
        "--record",
        action="store_true",
        help="ask Claude Code (your Claude subscription) for answers missing from the cache",
    )
    evaluate.add_argument("--workers", type=int, default=4)
    evaluate.add_argument("--output", type=Path, help="also write the Markdown report here")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    if args.command != "eval":
        print(f"inbox-planner {__version__}. Try: inbox-planner eval --help")
        return 0

    llm = CachedClient(live=ClaudeCodeClient() if args.record else None)
    triage_model, extraction_model = args.pipeline
    triage_models = list(dict.fromkeys([*args.triage_models, triage_model]))
    extraction_models = list(dict.fromkeys([*args.extraction_models, extraction_model]))
    try:
        triage_runs = [run_triage(llm, m, args.workers) for m in triage_models]
        extraction_runs = [run_extraction(llm, m, args.workers) for m in extraction_models]
    except CacheMiss as error:
        print(f"Missing recorded answer ({error}). Re-run with --record.", file=sys.stderr)
        return 2
    except LLMUnavailable as error:
        print(
            f"Claude Code is unavailable: {error}. Log in with `claude` then /login.",
            file=sys.stderr,
        )
        return 2

    pipeline_triage = next(r for r in triage_runs if r.stats.model == triage_model)
    pipeline_extraction = next(r for r in extraction_runs if r.stats.model == extraction_model)
    report = render_report(
        triage_runs,
        extraction_runs,
        (
            pipeline_triage,
            pipeline_extraction,
            score_pipeline(pipeline_triage, pipeline_extraction),
        ),
    )
    print(report)
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    return 0
