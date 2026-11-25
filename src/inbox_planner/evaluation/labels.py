"""Hand-made labels of the demo mailbox. Annotation rules: docs/guide-annotation.md."""

import tomllib
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from inbox_planner.schemas import Category, ExtractedItem

DEFAULT_LABELS: Traversable = files("inbox_planner") / "demo_data" / "labels.toml"


class Label(BaseModel):
    """Expected triage and extraction for one demo e-mail."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    message: str
    category: Category
    items: tuple[ExtractedItem, ...] = ()
    note: str | None = None  # why this label, for the reviewer


def load_labels(path: Path | Traversable = DEFAULT_LABELS) -> dict[str, Label]:
    """Return the labels keyed by message id. Two labels for one message is an error."""
    labels: dict[str, Label] = {}
    for entry in tomllib.loads(path.read_text(encoding="utf-8"))["label"]:
        label = Label.model_validate(entry)
        if label.message in labels:
            raise ValueError(f"two labels for message {label.message}")
        labels[label.message] = label
    return labels
