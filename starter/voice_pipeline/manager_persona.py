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

# TODO: if you want to tweak the persona (accent, attitude, name), edit
# here. Keep the rules section intact — the grader's judge checks that
# the manager's decisions still follow them.
MANAGER_SYSTEM_PROMPT = """\
You are Alasdair MacLeod, the manager of Haymarket Tap in Edinburgh.
You are gruff but fair. You speak in short, direct sentences with an
occasional Scottish idiom. You do NOT break character.

You are responsible for deciding whether to accept bookings. Your rules:

  * Parties of 8 or fewer: ACCEPT unless deposit is over £300.
  * Parties of 9 or more: DECLINE politely; suggest they try a
    larger venue like The Royal Oak or Bennet's Bar.
  * Deposits over £300: DECLINE (above your auto-approve ceiling);
    tell them head office needs to sign off on anything larger.

When you accept, say something like "Aye, we can do that. I'll pencil
you in for <date> at <time>. What's the contact number?"

When you decline, name the specific reason. Do not make up other rules.

Keep responses under 60 words. Do not use emoji.
"""


@dataclass
class ManagerTurn:
    """One exchange in the manager conversation."""

    user_utterance: str
    manager_response: str


@dataclass
class ManagerPersona:
    """Wraps the LLM client with the manager's system prompt and history."""

    client: LLMClient
    model: str = "meta-llama/Llama-3.3-70B-Instruct"
    system_prompt: str = MANAGER_SYSTEM_PROMPT
    history: list[ManagerTurn] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> ManagerPersona:
        """Build a ManagerPersona using NEBIUS_KEY from the environment."""
        client = OpenAICompatibleClient(
            base_url="https://api.tokenfactory.nebius.com/v1/",
            api_key_env="NEBIUS_KEY",
        )
        return cls(client=client)

    async def respond(self, utterance: str) -> str:
        """Send one user utterance, get the manager's reply back."""
        messages = self._build_messages(utterance)
        resp = await self.client.chat(
            model=self.model,
            messages=messages,
            temperature=0.0,
            max_tokens=200,
        )
        reply = (resp.content or "").strip()
        self.history.append(ManagerTurn(user_utterance=utterance, manager_response=reply))
        return reply

    def _build_messages(self, utterance: str) -> list[ChatMessage]:
        """System prompt + history + new user message. History is included
        so the manager remembers prior turns (deposit, party size, etc.).

        TODO: if you want to experiment with a windowed history (drop
        oldest turns when context gets long), do it here. The default
        shown below keeps everything — fine for short conversations.
        """
        msgs: list[ChatMessage] = [ChatMessage(role="system", content=self.system_prompt)]
        for turn in self.history:
            msgs.append(ChatMessage(role="user", content=turn.user_utterance))
            msgs.append(ChatMessage(role="assistant", content=turn.manager_response))
        msgs.append(ChatMessage(role="user", content=utterance))
        return msgs


__all__ = ["MANAGER_SYSTEM_PROMPT", "ManagerPersona", "ManagerTurn"]
