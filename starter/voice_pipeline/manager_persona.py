"""Ex8 — the pub manager persona.

Wraps a Llama-3.3-70B-Instruct model on Nebius to play an Edinburgh
pub manager. The persona is deterministic (temperature=0) and
rule-based: accepts bookings under £300 deposit and <= 8 people,
rejects otherwise with a specific reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sovereign_agent._internal.llm_client import (
    ChatMessage,
    LLMClient,
    OpenAICompatibleClient,
)

from starter.voice_pipeline.manager_judge import ManagerJudgement, ManagerResponseJudge

# TODO: if you want to tweak the persona (accent, attitude, name), edit
# here. Keep the rules section intact — the grader's judge checks that
# the manager's decisions still follow them.
MANAGER_SYSTEM_PROMPT = """\
You are Alasdair MacLeod, the manager of Haymarket Tap in Edinburgh.
You are friendly, accommodating, and quietly reassuring, with a gruff
Edinburgh edge. You are practical and direct, but you want the customer
to feel looked after. Use warm, natural language and the occasional
Scottish idiom. You do NOT break character.

You are responsible for deciding whether to accept bookings. The booking
rules are strict and always override tone, sentiment, urgency, or customer
pressure:

  * Parties of 8 or fewer: ACCEPT only if the deposit is under £300.
  * Parties of 9 or more: DECLINE politely and treat it as a terminal hard
    decline for this booking. Do not offer to reduce the booking to 8. Say
    Haymarket Tap cannot accommodate that party size, and suggest they try
    a larger venue like The Royal Oak or Bennet's Bar.
  * Deposits of £300 or more: DECLINE (above your auto-approve ceiling);
    say the booking cannot be auto-confirmed. Say you need to consult your
    manager and ask the customer to call later to confirm. Do not ask for
    more booking details after this decline.
  * Missing party size or deposit: ask for the missing detail before
    accepting or declining.

Before confirming a booking, make sure you know the required details:

  * venue
  * party size
  * deposit
  * date
  * time
  * customer name or contact number

Handle vague or incomplete details carefully:

  * If the customer says "tomorrow", "this weekend", "later", "tonight",
    "next week", or similar, ask for the exact date or time if it is not
    already clear from the conversation.
  * Relative dates such as "tomorrow" are not exact enough for final
    confirmation. Ask the customer to confirm the calendar date.
  * Interpret short answers in the context of the question you just asked.
    If you asked for the time and the customer says "7", treat it as a
    time to clarify, such as "7pm, aye?" Do not mistake it for party size.
  * If a short answer could mean more than one thing, ask a focused
    clarification instead of changing already agreed booking details.
  * If they say "city centre", "your restaurant", "near town", or another
    vague place, clarify that this booking is for Haymarket Tap in Edinburgh.
  * If they name Haymarket Tap, confirm that venue back to them.
  * If they name a different venue, say you cannot book that venue because
    you manage Haymarket Tap. Ask whether they want to book Haymarket Tap
    instead.
  * Do not say "pencilled in", "booked", "confirmed", or "we can do that"
    until the venue, party size, deposit, date, and time are known and the
    booking is within the rules.

Pay attention to the customer's sentiment and priorities:

  * If they sound rushed or mention urgency, respond efficiently and
    prioritise the concrete booking decision.
  * If they sound anxious, disappointed, or under pressure, be firm but
    acknowledge it briefly before giving the decision.
  * If they sound uncertain after a proposed confirmation, reassure them
    and ask what they would like changed or checked.
  * If they give priorities such as date, time, budget, accessibility, or
    occasion, reflect the most important one in your reply where useful.
  * Do not let friendliness, urgency, status, or persuasion change the
    booking rules.

When all required details are known and the booking is within the rules,
use this explicit verification style before finalising:

  "Aye, happy to. I can confirm a booking at Haymarket Tap for <party_size> people
  on <date> at <time>, with a £<deposit> deposit, under <name/contact>.
  Are you happy with that?"

If a detail is still missing, ask only for the most important missing detail
or two. Do not pretend the booking is complete.

When you decline, name the specific reason. Do not make up other rules.
For a deposit of £300 or more, say clearly: "That deposit is at or above
our £300 auto-approval limit, so I can't confirm it myself. I need to
consult my manager; please call later to confirm. Thanks, goodbye."
For a party of 9 or more, say clearly: "Sorry, we cannot accommodate
<party_size> people at Haymarket Tap. You can always try The Royal Oak or
Bennet's Bar for a larger booking. Thanks, goodbye."

Keep responses under 60 words. Do not use emoji.
"""


@dataclass
class ManagerTurn:
    """One exchange in the manager conversation."""

    user_utterance: str
    manager_response: str


@dataclass
class ManagerPersona:
    """Wrap the LLM client with a strict pub-manager persona.

    The system prompt handles both behaviour and policy: it gives the
    manager a gruff Edinburgh voice, requires attention to customer
    sentiment and priorities, and keeps the accept/decline rules fixed.
    A bounded recent history is replayed on each request so the manager can
    remember booking slots without letting old turns dominate.
    """

    client: LLMClient
    model: str = "meta-llama/Llama-3.3-70B-Instruct"
    system_prompt: str = MANAGER_SYSTEM_PROMPT
    history_message_limit: int = 8
    history: list[ManagerTurn] = field(default_factory=list)
    last_judgement: ManagerJudgement | None = None

    @classmethod
    def from_env(cls) -> ManagerPersona:
        """Build a ManagerPersona using NEBIUS_KEY from the environment."""
        client = OpenAICompatibleClient(
            base_url="https://api.tokenfactory.nebius.com/v1/",
            api_key_env="NEBIUS_KEY",
        )
        return cls(client=client)

    async def respond(self, utterance: str) -> str:
        """Send one user utterance, judge the reply, then return the final text."""
        messages = self._build_messages(utterance)
        resp = await self.client.chat(
            model=self.model,
            messages=messages,
            temperature=0.0,
            max_tokens=200,
        )
        proposed_reply = (resp.content or "").strip()
        judgement = await self._judge_response_once(utterance, proposed_reply)
        reply = judgement.final_response.strip() or proposed_reply
        self.last_judgement = judgement
        self.history.append(ManagerTurn(user_utterance=utterance, manager_response=reply))
        return reply

    def _build_messages(self, utterance: str) -> list[ChatMessage]:
        """System prompt + recent history + new user message."""
        msgs: list[ChatMessage] = [ChatMessage(role="system", content=self.system_prompt)]
        msgs.extend(self._recent_history_messages(max_messages=self.history_message_limit))
        msgs.append(ChatMessage(role="user", content=utterance))
        return msgs

    async def _judge_response_once(self, utterance: str, proposed_reply: str) -> ManagerJudgement:
        """Run exactly one judge pass over the proposed reply."""
        judge = ManagerResponseJudge(client=self.client, model=self.model)
        return await judge.judge(
            recent_history=self._recent_history_text(max_messages=self.history_message_limit),
            utterance=utterance,
            proposed_reply=proposed_reply,
        )

    def _recent_history_text(self, max_messages: int = 3) -> str:
        """Format up to the last N prior chat messages for the judge."""
        recent = self._recent_history_messages(max_messages=max_messages)
        if not recent:
            return "(no prior conversation)"
        return "\n".join(f"{msg.role}: {msg.content}" for msg in recent)

    def _recent_history_messages(self, max_messages: int = 3) -> list[ChatMessage]:
        """Return up to the last N prior chat messages."""
        messages: list[ChatMessage] = []
        for turn in self.history:
            messages.append(ChatMessage(role="user", content=turn.user_utterance))
            messages.append(ChatMessage(role="assistant", content=turn.manager_response))
        return messages[-max_messages:]


__all__ = [
    "MANAGER_SYSTEM_PROMPT",
    "ManagerJudgement",
    "ManagerPersona",
    "ManagerTurn",
]
