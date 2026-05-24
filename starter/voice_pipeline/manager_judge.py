"""One-pass quality judge for the Ex8 pub manager persona."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from sovereign_agent._internal.llm_client import ChatMessage, LLMClient

MANAGER_JUDGE_SYSTEM_PROMPT = """\
You are a strict quality judge for an Edinburgh pub booking manager.
Review the proposed manager response against the recent conversation.

Check these constraints:

  * Capacity: bookings may be accepted only for parties of 8 or fewer.
    A request for 9 or more people is a terminal hard decline for this
    booking: do not offer to reduce it to 8. The response must say Haymarket
    Tap cannot accommodate that party size and suggest The Royal Oak or
    Bennet's Bar for a larger booking.
  * Deposit: bookings may be accepted only when the deposit is under £300.
    A £300 deposit is not acceptable for auto-confirmation; the response
    should say it is at or above the £300 limit, that the manager must be
    consulted, and that the customer should call later to confirm. It should
    not ask for a contact number or more booking details after this decline.
  * Required details: before confirming or implying a booking is made, the
    manager must know venue, party size, deposit, date, time, and customer
    name or contact number.
  * Venue: this manager can book only Haymarket Tap in Edinburgh. If the
    customer names Haymarket Tap, the response should confirm it. If the
    customer names a different venue, the response should say the manager
    cannot book that venue and ask whether they want Haymarket Tap instead.
  * Missing facts: if any required detail is missing, the manager should ask
    for the most important missing detail or two instead of confirming.
  * Vague facts: if the customer says "tomorrow", "this weekend", "later",
    "tonight", "next week", "city centre", "your restaurant", or similar,
    the manager should clarify the exact date/time/place unless it is already
    clear from recent history.
  * Relative dates such as "tomorrow" are not enough for final confirmation;
    the manager should ask for or repeat a calendar date.
  * Contextual short answers: interpret bare numbers using the manager's last
    question. If the manager asked for time and the customer says "7", treat
    it as a time needing clarification, not as a changed party size.
  * Declines: if declining, the response must name the specific reason.
  * Confirmation: when all required details are known and the booking is
    allowed, the manager should repeat the details back and ask for
    verification before finalising.
  * Sentiment and priorities: the response should notice urgency, anxiety,
    disappointment, budget, date, time, accessibility, or occasion when present.
  * Persona: the response should sound like a gruff but fair Edinburgh pub
    manager and stay under 60 words.

Return only JSON with this shape:
{
  "approved": true,
  "reason": "max 20 words explaining the judgement",
  "final_response": "response to use"
}

If the proposed response is acceptable, set approved to true and copy it into
final_response. If it fails, set approved to false and write a corrected
final_response that obeys all constraints. Judge exactly once; do not review
or iterate on your own final_response.
The reason must be concise, user-visible, and no more than 20 words.
"""


@dataclass
class ManagerJudgement:
    """Quality check for one proposed manager response."""

    approved: bool
    reason: str
    final_response: str


@dataclass
class ManagerResponseJudge:
    """Run a single LLM judge pass over one proposed manager response."""

    client: LLMClient
    model: str
    system_prompt: str = MANAGER_JUDGE_SYSTEM_PROMPT

    async def judge(
        self,
        *,
        recent_history: str,
        utterance: str,
        proposed_reply: str,
    ) -> ManagerJudgement:
        """Return one judgement without retries or self-iteration."""
        messages = [
            ChatMessage(role="system", content=self.system_prompt),
            ChatMessage(
                role="user",
                content=(
                    "Recent conversation:\n"
                    f"{recent_history}\n\n"
                    f"Current customer utterance:\n{utterance}\n\n"
                    f"Proposed manager response:\n{proposed_reply}"
                ),
            ),
        ]
        try:
            resp = await self.client.chat(
                model=self.model,
                messages=messages,
                temperature=0.0,
                max_tokens=300,
            )
            return parse_judgement(resp.content, proposed_reply)
        except Exception as exc:
            return ManagerJudgement(
                approved=True,
                reason=f"Judge unavailable; kept proposed response: {exc}",
                final_response=proposed_reply,
            )


def parse_judgement(content: str | None, proposed_reply: str) -> ManagerJudgement:
    """Parse judge JSON, falling back to the proposed reply."""
    if not content:
        return ManagerJudgement(
            approved=True,
            reason="Judge returned no content; kept proposed response.",
            final_response=proposed_reply,
        )
    try:
        data = json.loads(_extract_json_object(content))
    except json.JSONDecodeError:
        return ManagerJudgement(
            approved=True,
            reason="Judge returned non-JSON content; kept proposed response.",
            final_response=proposed_reply,
        )
    approved = bool(data.get("approved", True))
    reason = _cap_words(str(data.get("reason") or ""), max_words=20)
    final_response = str(data.get("final_response") or proposed_reply)
    return ManagerJudgement(
        approved=approved,
        reason=reason,
        final_response=final_response,
    )


def _extract_json_object(content: str) -> str:
    """Extract the first JSON object, tolerating fenced or prefixed output."""
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]
    return stripped


def _cap_words(text: str, max_words: int) -> str:
    """Limit a display reason without exposing verbose model reasoning."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


__all__ = [
    "MANAGER_JUDGE_SYSTEM_PROMPT",
    "ManagerJudgement",
    "ManagerResponseJudge",
    "parse_judgement",
]
