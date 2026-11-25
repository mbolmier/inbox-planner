"""Orchestrator: mailbox → triage → extraction (actionable mail only) → items.

It only reads. Anything that writes (reply drafts, calendar export, reminders)
goes through an explicit human validation step, added with those features.
"""

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from inbox_planner.agents.extraction import ExtractionAgent, ExtractionResult
from inbox_planner.agents.triage import TriageAgent, TriageResult
from inbox_planner.connectors.base import MailConnector
from inbox_planner.llm.base import CacheMiss, LLMClient, LLMError, LLMUnavailable
from inbox_planner.mail.models import Message
from inbox_planner.schemas import ACTIONABLE_CATEGORIES, ExtractedItem

# Decision D33: the cheapest model that held the measured quality, for both agents.
DEFAULT_TRIAGE_MODEL = "claude-haiku-5-5"
DEFAULT_EXTRACTION_MODEL = "claude-haiku-5-5"


@dataclass(frozen=True)
class ProcessedMessage:
    message: Message
    triage: TriageResult | None  # None if the model gave no usable answer
    extraction: ExtractionResult | None  # None when not actionable


def process_mailbox(
    connector: MailConnector,
    llm: LLMClient,
    timezones: Mapping[str, str],
    triage_model: str = DEFAULT_TRIAGE_MODEL,
    extraction_model: str = DEFAULT_EXTRACTION_MODEL,
    workers: int = 4,
) -> list[ProcessedMessage]:
    messages = connector.fetch_messages()
    triage_agent = TriageAgent(llm, triage_model, timezones)
    extraction_agent = ExtractionAgent(llm, extraction_model, timezones)

    def triage(message: Message) -> TriageResult | None:
        try:
            return triage_agent.run(message)
        except (CacheMiss, LLMUnavailable):
            raise
        except LLMError:
            return None

    def extract(message: Message) -> ExtractionResult | None:
        try:
            return extraction_agent.run(message)
        except (CacheMiss, LLMUnavailable):
            raise
        except LLMError:
            return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        verdicts = list(pool.map(triage, messages))
        actionable = [
            m
            for m, v in zip(messages, verdicts, strict=True)
            if v is not None and v.category in ACTIONABLE_CATEGORIES
        ]
        extracted = dict(
            zip((m.id for m in actionable), pool.map(extract, actionable), strict=True)
        )
    return [
        ProcessedMessage(m, v, extracted.get(m.id)) for m, v in zip(messages, verdicts, strict=True)
    ]


def items_by_message(processed: list[ProcessedMessage]) -> dict[str, tuple[ExtractedItem, ...]]:
    return {p.message.id: p.extraction.items for p in processed if p.extraction is not None}
