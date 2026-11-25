"""Scores for triage and extraction. Pure functions: no model call here."""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from inbox_planner.schemas import Category, ExtractedItem


def ratio(part: int, whole: int) -> float | None:
    return part / whole if whole else None


@dataclass(frozen=True)
class ClassScore:
    precision: float | None
    recall: float | None
    support: int


@dataclass(frozen=True)
class TriageScores:
    accuracy: float
    per_class: dict[Category, ClassScore]
    useful_precision: float | None  # "useful" means anything but noise
    useful_recall: float | None
    confusion: Counter[tuple[Category, Category | None]]
    failures: int


def score_triage(
    gold: Mapping[str, Category], predicted: Mapping[str, Category | None]
) -> TriageScores:
    ids = list(gold)
    per_class = {}
    for category in Category:
        true_pos = sum(gold[i] is category and predicted.get(i) is category for i in ids)
        n_predicted = sum(predicted.get(i) is category for i in ids)
        n_gold = sum(gold[i] is category for i in ids)
        per_class[category] = ClassScore(
            ratio(true_pos, n_predicted), ratio(true_pos, n_gold), n_gold
        )

    def useful(category: Category | None) -> bool:
        return category is not None and category is not Category.NOISE

    both_useful = sum(useful(gold[i]) and useful(predicted.get(i)) for i in ids)
    return TriageScores(
        accuracy=sum(predicted.get(i) is gold[i] for i in ids) / len(ids),
        per_class=per_class,
        useful_precision=ratio(both_useful, sum(useful(predicted.get(i)) for i in ids)),
        useful_recall=ratio(both_useful, sum(useful(gold[i]) for i in ids)),
        confusion=Counter((gold[i], predicted.get(i)) for i in ids),
        failures=sum(predicted.get(i) is None for i in ids),
    )


def instant(item: ExtractedItem) -> datetime:
    when = item.starts_at or item.due_at
    assert when is not None  # guaranteed by the ExtractedItem validator
    return when


def match_items(
    gold: Sequence[ExtractedItem], predicted: Sequence[ExtractedItem]
) -> list[tuple[ExtractedItem, ExtractedItem]]:
    """Pair each expected item with a predicted one of the same kind at the same instant."""
    remaining = list(predicted)
    pairs = []
    for expected in gold:
        for candidate in remaining:
            if candidate.kind is expected.kind and instant(candidate) == instant(expected):
                pairs.append((expected, candidate))
                remaining.remove(candidate)
                break
    return pairs


def _same_meeting_id(a: str | None, b: str | None) -> bool:
    def digits(value: str | None) -> str:
        return "".join(ch for ch in value or "" if ch.isalnum())

    return digits(a) == digits(b)


@dataclass(frozen=True)
class ExtractionScores:
    gold_items: int
    predicted_items: int
    matched: int  # same kind and exactly the same instant, time zone included
    precision: float | None
    recall: float | None
    wrong_zone: int  # right local time, wrong UTC offset
    video_expected: int
    video_url_exact: int
    meeting_details_exact: int  # meeting id and passcode both right
    recurring_expected: int
    recurrence_exact: int
    duration_expected: int
    duration_exact: int
    invalid_items: int
    failures: int


def score_extraction(
    gold: Mapping[str, Sequence[ExtractedItem]],
    predicted: Mapping[str, Sequence[ExtractedItem] | None],
    invalid_items: int = 0,
) -> ExtractionScores:
    n_gold = n_predicted = wrong_zone = 0
    pairs: list[tuple[ExtractedItem, ExtractedItem]] = []
    for message_id, expected in gold.items():
        found = predicted.get(message_id) or ()
        n_gold += len(expected)
        n_predicted += len(found)
        matched = match_items(expected, found)
        pairs += matched
        left = [p for p in found if all(p is not m for _, m in matched)]
        for item in expected:
            if any(item is g for g, _ in matched):
                continue
            wall_clock = instant(item).replace(tzinfo=None)
            if any(
                p.kind is item.kind and instant(p).replace(tzinfo=None) == wall_clock for p in left
            ):
                wrong_zone += 1

    with_video = [(g, p) for g, p in pairs if g.video_url]
    recurring = [(g, p) for g, p in pairs if g.weekly_on]
    with_duration = [(g, p) for g, p in pairs if g.duration_minutes]
    return ExtractionScores(
        gold_items=n_gold,
        predicted_items=n_predicted,
        matched=len(pairs),
        precision=ratio(len(pairs), n_predicted),
        recall=ratio(len(pairs), n_gold),
        wrong_zone=wrong_zone,
        video_expected=len(with_video),
        video_url_exact=sum(g.video_url == p.video_url for g, p in with_video),
        meeting_details_exact=sum(
            _same_meeting_id(g.meeting_id, p.meeting_id)
            and (g.passcode or "") == (p.passcode or "")
            for g, p in with_video
        ),
        recurring_expected=len(recurring),
        recurrence_exact=sum(
            set(g.weekly_on) == set(p.weekly_on) and g.repeat_until == p.repeat_until
            for g, p in recurring
        ),
        duration_expected=len(with_duration),
        duration_exact=sum(g.duration_minutes == p.duration_minutes for g, p in with_duration),
        invalid_items=invalid_items,
        failures=sum(predicted.get(i) is None for i in gold),
    )
