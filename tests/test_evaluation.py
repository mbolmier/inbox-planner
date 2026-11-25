from datetime import UTC, datetime

from fakes import FakeLLM, oracle

from inbox_planner.evaluation.metrics import match_items, score_extraction, score_triage
from inbox_planner.evaluation.report import render_report
from inbox_planner.evaluation.runner import (
    estimate_cost,
    run_extraction,
    run_triage,
    score_pipeline,
)
from inbox_planner.llm.base import Usage
from inbox_planner.schemas import Category, ExtractedItem

AT = datetime(2026, 11, 5, 20, 0, tzinfo=UTC)


def deadline(when: datetime, title: str = "x") -> ExtractedItem:
    return ExtractedItem(kind="deadline", title=title, due_at=when)


def test_a_perfect_model_gets_perfect_scores_end_to_end():
    llm = FakeLLM(oracle)

    triage = run_triage(llm, "claude-haiku-5-5", workers=2)
    extraction = run_extraction(llm, "claude-sonnet-5-5", workers=2)
    pipeline = score_pipeline(triage, extraction)

    assert triage.scores.accuracy == 1
    assert triage.scores.failures == 0
    for scores in (extraction.scores, pipeline):
        assert scores.precision == scores.recall == 1
        assert scores.wrong_zone == 0
        assert scores.video_url_exact == scores.video_expected > 0
        assert scores.meeting_details_exact == scores.video_expected
        assert scores.recurrence_exact == scores.recurring_expected > 0
        assert scores.duration_exact == scores.duration_expected > 0
    report = render_report([triage], [extraction], (triage, extraction, pipeline))
    assert "100 %" in report and "Aucune." in report


def test_triage_scores_per_class_and_useful_mail():
    gold = {"a": Category.NOISE, "b": Category.DEADLINE, "c": Category.INFO, "d": Category.NOISE}
    predicted = {"a": Category.NOISE, "b": Category.PROCEDURE, "c": Category.NOISE, "d": None}

    scores = score_triage(gold, predicted)

    assert scores.accuracy == 0.25
    assert scores.failures == 1
    assert scores.per_class[Category.NOISE].precision == 0.5
    assert scores.per_class[Category.NOISE].recall == 0.5
    assert scores.useful_precision == 1.0  # the only "useful" prediction (b) is useful
    assert scores.useful_recall == 0.5  # b found, c missed


def test_items_match_on_kind_and_exact_instant():
    expected = [deadline(AT, "a")]

    assert match_items(expected, [deadline(AT, "other title")])
    assert not match_items(expected, [deadline(AT.replace(minute=1))])


def test_right_local_time_in_the_wrong_zone_is_reported():
    gold = {"m": [deadline(datetime.fromisoformat("2026-11-05T12:00:00-08:00"))]}
    predicted = {"m": [deadline(datetime.fromisoformat("2026-11-05T12:00:00-07:00"))]}

    scores = score_extraction(gold, predicted)

    assert scores.matched == 0
    assert scores.wrong_zone == 1


def test_cost_estimate_uses_public_prices_per_million_tokens():
    assert estimate_cost("claude-haiku-5-5", Usage(1_000_000, 1_000_000)) == 0.60
    assert estimate_cost("some-other-model", Usage(10, 10)) is None
