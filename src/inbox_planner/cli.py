"""Command line.

- `inbox-planner eval`: score triage and extraction on the demo mailbox.
- `inbox-planner plan`: plan the demo week according to the energy of each day.
"""

import argparse
import sys
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from inbox_planner import __version__
from inbox_planner.connectors.demo import DEMO_NOW, DEMO_TIMEZONES, DemoConnector
from inbox_planner.evaluation.report import render_report
from inbox_planner.evaluation.runner import run_extraction, run_triage, score_pipeline
from inbox_planner.llm.base import CacheMiss, LLMUnavailable
from inbox_planner.llm.cache import CachedClient
from inbox_planner.llm.claude_code import ClaudeCodeClient
from inbox_planner.pipeline import (
    DEFAULT_EXTRACTION_MODEL,
    DEFAULT_TRIAGE_MODEL,
    items_by_message,
    process_mailbox,
)
from inbox_planner.planning.calendar import build_events
from inbox_planner.planning.energy import Energy
from inbox_planner.planning.planner import PlannerSettings, plan_week, tasks_from_items
from inbox_planner.planning.render import render_plan

MODELS = ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5")
ENERGY_WORDS = {
    "off": Energy.OFF,
    "creve": Energy.TIRED,
    "crevé": Energy.TIRED,
    "tired": Energy.TIRED,
    "normal": Energy.NORMAL,
    "forme": Energy.ENERGIZED,
    "energized": Energy.ENERGIZED,
}


def _models(value: str) -> list[str]:
    return [m.strip() for m in value.split(",") if m.strip()]


def _energies(value: str) -> list[Energy]:
    try:
        return [ENERGY_WORDS[word.strip().lower()] for word in value.split(",") if word.strip()]
    except KeyError as error:
        raise argparse.ArgumentTypeError(
            f"unknown energy {error}; use: off, creve, normal, forme"
        ) from error


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
        default=[DEFAULT_TRIAGE_MODEL, DEFAULT_EXTRACTION_MODEL],
        help="triage model and extraction model of the end-to-end chain",
    )
    evaluate.add_argument(
        "--record",
        action="store_true",
        help="ask Claude Code (your Claude subscription) for answers missing from the cache",
    )
    evaluate.add_argument("--workers", type=int, default=4)
    evaluate.add_argument("--output", type=Path, help="also write the Markdown report here")

    plan = commands.add_parser("plan", help="plan the demo week (recorded answers, no account)")
    plan.add_argument(
        "--energy",
        type=_energies,
        default=[],
        help="energy of each day from the demo Monday, e.g. creve,normal,forme,normal,off",
    )
    web = commands.add_parser("web", help="open the web view of the demo (local only)")
    web.add_argument(
        "--host", default="127.0.0.1", help="127.0.0.1: reachable from this computer only"
    )
    web.add_argument("--port", type=int, default=8000)
    return parser


def _web(args: argparse.Namespace) -> int:
    import uvicorn

    from inbox_planner.web.app import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port)
    return 0


def _evaluate(args: argparse.Namespace) -> int:
    llm = CachedClient(live=ClaudeCodeClient() if args.record else None)
    triage_model, extraction_model = args.pipeline
    triage_models = list(dict.fromkeys([*args.triage_models, triage_model]))
    extraction_models = list(dict.fromkeys([*args.extraction_models, extraction_model]))
    triage_runs = [run_triage(llm, m, args.workers) for m in triage_models]
    extraction_runs = [run_extraction(llm, m, args.workers) for m in extraction_models]

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


def _plan(args: argparse.Namespace) -> int:
    zone = ZoneInfo(DEMO_TIMEZONES["osu"])
    processed = process_mailbox(DemoConnector(), CachedClient(), DEMO_TIMEZONES, now=DEMO_NOW)
    items = items_by_message(processed)
    settings = PlannerSettings()
    horizon_end = DEMO_NOW + timedelta(days=settings.horizon_days)
    first_day = DEMO_NOW.astimezone(zone).date()
    energy = {first_day + timedelta(days=n): e for n, e in enumerate(args.energy)}
    plan = plan_week(
        tasks_from_items(items, settings),
        build_events(items, DEMO_NOW, horizon_end, zone),
        DEMO_NOW,
        zone,
        energy,
        settings,
    )
    print(render_plan(plan), end="")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    commands = {"eval": _evaluate, "plan": _plan, "web": _web}
    if args.command not in commands:
        print(f"inbox-planner {__version__}. Commands: eval, plan, web (see --help)")
        return 0
    try:
        return commands[args.command](args)
    except CacheMiss as error:
        print(f"Missing recorded answer ({error}). Re-run eval with --record.", file=sys.stderr)
        return 2
    except LLMUnavailable as error:
        print(
            f"Claude Code is unavailable: {error}\n"
            "Answers recorded so far are kept; re-run the same command to continue.",
            file=sys.stderr,
        )
        return 2
