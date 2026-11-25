"""Drafting agent: propose a short reply. It is only a proposal.

The user reviews and edits it, then explicitly saves it as a draft. Nothing is
ever sent: no code path in this project can send an e-mail.
"""

from collections.abc import Mapping
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from inbox_planner.agents.context import render_message
from inbox_planner.llm.base import LLMClient, LLMError, LLMRequest
from inbox_planner.mail.compose import DraftReply, reply_subject, reply_to_address
from inbox_planner.mail.models import Message

SYSTEM_PROMPT = """\
You draft a reply to one e-mail on behalf of a university student on exchange abroad. \
The reply is saved as a draft that the student reviews and edits; it is never sent \
automatically.

Rules:
- Write in the language of the e-mail, in the register it uses (formal with staff).
- Be brief: a few sentences, then a polite closing and the student's first name, {signature}.
- Never invent facts, commitments, dates, times, documents or attachments. When something \
is missing, leave a placeholder in square brackets, e.g. [numéro de dossier].
- Follow the student's instruction about what to answer.
- Judge time only against the reference time given above the e-mail."""

INSTRUCTIONS = {
    "confirmer": "Confirm, or acknowledge receipt and say it will be done in time.",
    "decliner": "Politely decline and ask whether another option is possible.",
    "question": "Ask the one question that is most useful before acting.",
}
NO_REPLY_MARKERS = ("noreply", "no-reply", "donotreply", "notifications@", "notification@")


class DraftOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(description="The reply text only, without the subject line.")


def can_reply(message: Message) -> bool:
    """Automated senders (no-reply, notifications) get no reply."""
    return not any(marker in message.sender.lower() for marker in NO_REPLY_MARKERS)


class DraftingAgent:
    def __init__(
        self,
        llm: LLMClient,
        model: str,
        timezones: Mapping[str, str],
        now: datetime,
        signature: str = "Camille",  # the demo persona; a real user sets their own name
    ) -> None:
        self.llm = llm
        self.model = model
        self.timezones = timezones
        self.now = now
        self.system = SYSTEM_PROMPT.format(signature=signature)

    def run(self, message: Message, intent: str = "confirmer") -> DraftReply:
        if intent not in INSTRUCTIONS:
            raise ValueError(f"unknown intent {intent!r}")
        prompt = (
            f"Instruction from the student: {INSTRUCTIONS[intent]}\n\n"
            f"{render_message(message, self.timezones, self.now)}"
        )
        request = LLMRequest(
            model=self.model,
            system=self.system,
            prompt=prompt,
            schema=DraftOutput,
            tag=f"draft-{intent}/{message.id}",
        )
        response = self.llm.complete(request)
        try:
            output = DraftOutput.model_validate(response.data)
        except ValidationError as error:
            raise LLMError(f"draft for {message.id} does not match the schema") from error
        return DraftReply(
            source_message_id=message.id,
            to=reply_to_address(message),
            subject=reply_subject(message.subject),
            body=output.body.strip(),
        )
