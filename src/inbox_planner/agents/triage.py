"""Triage agent: is the e-mail useful, and of which kind? One small, cheap call."""

from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from inbox_planner.agents.context import render_message
from inbox_planner.llm.base import LLMClient, LLMError, LLMRequest, Usage
from inbox_planner.mail.models import Message
from inbox_planner.schemas import Category

SYSTEM_PROMPT = """\
You triage the e-mails of a university student who is on exchange abroad and reads \
several mailboxes. Pick the single main reason the e-mail matters to the student.

Categories:
- appointment: the student must be somewhere, or online, at a given time (class, exam, \
interview, booked meeting, planned call).
- deadline: some work must be handed in before a due time (homework, quiz, project, \
technical test, report).
- procedure: an administrative process to complete (insurance, address, immigration \
paperwork, contracts, application files).
- info: worth knowing, nothing to schedule (grades posted, closures, holidays, \
maintenance notices, optional events announced to everyone).
- noise: nothing useful (promotions, newsletters, social network notifications, phishing).

Rules:
- A date inside a promotion or a newsletter does not make it a deadline: it is noise.
- An optional event announced to a whole mailing list is info.
- Urgent account warnings from look-alike domains are phishing: noise.

Give the category and one short sentence explaining why."""


class TriageOutput(BaseModel):
    """What the model must return."""

    model_config = ConfigDict(extra="forbid")

    category: Category
    reason: str = Field(description="One short sentence explaining the choice.")


@dataclass(frozen=True)
class TriageResult:
    message_id: str
    category: Category
    reason: str
    model: str
    usage: Usage
    duration_ms: int


class TriageAgent:
    def __init__(self, llm: LLMClient, model: str, timezones: Mapping[str, str]) -> None:
        self.llm = llm
        self.model = model
        self.timezones = timezones

    def run(self, message: Message) -> TriageResult:
        request = LLMRequest(
            model=self.model,
            system=SYSTEM_PROMPT,
            prompt=render_message(message, self.timezones),
            schema=TriageOutput,
            tag=f"triage/{message.id}",
        )
        response = self.llm.complete(request)
        try:
            output = TriageOutput.model_validate(response.data)
        except ValidationError as error:
            raise LLMError(f"triage answer for {message.id} does not match the schema") from error
        return TriageResult(
            message_id=message.id,
            category=output.category,
            reason=output.reason,
            model=response.model,
            usage=response.usage,
            duration_ms=response.duration_ms,
        )
