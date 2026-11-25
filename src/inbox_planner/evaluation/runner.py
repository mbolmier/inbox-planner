"""Run triage and extraction on the demo mailbox and score them against the labels."""

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from inbox_planner.agents.extraction import ExtractionAgent, ExtractionResult
from inbox_planner.agents.triage import TriageAgent, TriageResult
from inbox_planner.connectors.demo import DEMO_NOW, DEMO_TIMEZONES, DemoConnector
from inbox_planner.evaluation.labels import load_labels
from inbox_planner.evaluation.metrics import (
    ExtractionScores,
    TriageScores,
    score_extraction,
    score_triage,
)
from inbox_planner.llm.base import CacheMiss, LLMClient, LLMError, LLMUnavailable, Usage
from inbox_planner.mail.models import Message
from inbox_planner.schemas import ACTIONABLE_CATEGORIES

# Anthropic public API prices, USD per million tokens (input, output), as listed on
# 2026-11-03. Used only to ESTIMATE what a run would cost with an API key: the
# recordings themselves were made with a Claude subscription.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}


def estimate_cost(model: str, usage: Usage) -> float | None:
    """Upper bound in USD: every input token at full price, no cache discount."""
    if model not in PRICES_PER_MTOK:
        return None
    input_price, output_price = PRICES_PER_MTOK[model]
    return (usage.input_tokens * input_price + usage.output_tokens * output_price) / 1_000_000


@dataclass(frozen=True)
class RunStats:
    model: str
    calls: int
    usage: Usage
    model_seconds: float  # time spent by the model, summed over calls
    cost_usd: float | None


@dataclass(frozen=True)
class TriageRun:
    stats: RunStats
    scores: TriageScores
    results: dict[str, TriageResult | None]


@dataclass(frozen=True)
class ExtractionRun:
    stats: RunStats
    scores: ExtractionScores
    results: dict[str, ExtractionResult | None]


def _run_all[R](
    task: Callable[[Message], R], messages: Sequence[Message], workers: int
) -> dict[str, R | None]:
    """Run the task on every message. A bad answer counts as a failure; an
    unreachable model (or a missing recording in replay mode) stops everything."""

    def safely(message: Message) -> R | None:
        try:
            return task(message)
        except (LLMUnavailable, CacheMiss):
            raise
        except LLMError:
            return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(zip((m.id for m in messages), pool.map(safely, messages), strict=True))


def _stats(model: str, results: Sequence[TriageResult | ExtractionResult | None]) -> RunStats:
    done = [r for r in results if r is not None]
    usage = sum((r.usage for r in done), Usage())
    return RunStats(
        model=model,
        calls=len(done),
        usage=usage,
        model_seconds=sum(r.duration_ms for r in done) / 1000,
        cost_usd=estimate_cost(model, usage),
    )


def run_triage(llm: LLMClient, model: str, workers: int = 4) -> TriageRun:
    messages = DemoConnector().fetch_messages()
    agent = TriageAgent(llm, model, DEMO_TIMEZONES, DEMO_NOW)
    results = _run_all(agent.run, messages, workers)
    gold = {mid: label.category for mid, label in load_labels().items()}
    predicted = {mid: r.category if r else None for mid, r in results.items()}
    return TriageRun(_stats(model, list(results.values())), score_triage(gold, predicted), results)


def run_extraction(llm: LLMClient, model: str, workers: int = 4) -> ExtractionRun:
    messages = DemoConnector().fetch_messages()
    agent = ExtractionAgent(llm, model, DEMO_TIMEZONES, DEMO_NOW)
    results = _run_all(agent.run, messages, workers)
    gold = {mid: label.items for mid, label in load_labels().items()}
    predicted = {mid: r.items if r else None for mid, r in results.items()}
    invalid = sum(r.invalid_items for r in results.values() if r)
    return ExtractionRun(
        _stats(model, list(results.values())), score_extraction(gold, predicted, invalid), results
    )


def score_pipeline(triage: TriageRun, extraction: ExtractionRun) -> ExtractionScores:
    """End to end: items are kept only for e-mails the triage marked as actionable."""
    gold = {mid: label.items for mid, label in load_labels().items()}
    predicted = {}
    for mid, result in extraction.results.items():
        verdict = triage.results.get(mid)
        keep = verdict is not None and verdict.category in ACTIONABLE_CATEGORIES
        predicted[mid] = (result.items if result else None) if keep else ()
    return score_extraction(gold, predicted)
