from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from inbox_planner.schemas import ExtractedItem, ItemKind, Weekday

AT = datetime(2026, 11, 5, 20, 0, tzinfo=UTC)


def test_weekly_appointment_is_valid():
    item = ExtractedItem(
        kind="appointment",
        title="ST 421 lecture",
        starts_at=AT,
        weekly_on=("TU", "TH"),
        repeat_until=date(2026, 12, 3),
    )

    assert item.kind is ItemKind.APPOINTMENT
    assert item.weekly_on == (Weekday.TU, Weekday.TH)


@pytest.mark.parametrize(
    "fields",
    [
        pytest.param({"kind": "appointment"}, id="appointment without start"),
        pytest.param({"kind": "appointment", "starts_at": AT, "due_at": AT}, id="appointment due"),
        pytest.param({"kind": "deadline"}, id="deadline without due date"),
        pytest.param({"kind": "deadline", "due_at": AT, "starts_at": AT}, id="deadline start"),
        pytest.param(
            {
                "kind": "deadline",
                "due_at": AT,
                "weekly_on": ("TH",),
                "repeat_until": date(2026, 12, 3),
            },
            id="recurring deadline",
        ),
        pytest.param(
            {"kind": "appointment", "starts_at": AT, "weekly_on": ("TH",)},
            id="weekly without end",
        ),
        pytest.param(
            {"kind": "appointment", "starts_at": datetime(2026, 11, 5, 12, 0)},
            id="naive datetime",
        ),
        pytest.param({"kind": "appointment", "starts_at": AT, "room": "B12"}, id="unknown field"),
        pytest.param({"kind": "appointment", "starts_at": AT, "title": ""}, id="empty title"),
    ],
)
def test_inconsistent_items_are_rejected(fields: dict):
    with pytest.raises(ValidationError):
        ExtractedItem(**{"title": "x", **fields})
