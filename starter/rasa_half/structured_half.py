"""Ex6 — RasaStructuredHalf.

A StructuredHalf subclass that delegates to a running Rasa instance.
Keeps the sovereign-agent contract (run(session, input_payload) -> HalfResult)
while using Rasa's flow engine as the actual dialog driver.
"""

from __future__ import annotations

from sovereign_agent.discovery import DiscoverySchema
from sovereign_agent.halves import HalfResult
from sovereign_agent.halves.structured import StructuredHalf
from sovereign_agent.session.directory import Session

RASA_REST_WEBHOOK_DEFAULT = "http://localhost:5005/webhooks/rest/webhook"


class RasaStructuredHalf(StructuredHalf):
    """Routes booking data through Rasa CALM flows.

    The parent StructuredHalf uses a rule list. We override run() so
    the data goes out over HTTP to Rasa, and the response comes back
    as a HalfResult.
    """

    name = "rasa"

    def __init__(
        self,
        *,
        rasa_url: str = RASA_REST_WEBHOOK_DEFAULT,
        sender_id_prefix: str = "homework",
        request_timeout_s: float = 10.0,
    ) -> None:
        # We don't use the parent's rule list; pass [] so it doesn't
        # try to evaluate rules on its own.
        super().__init__(rules=[])
        self.rasa_url = rasa_url
        self.sender_id_prefix = sender_id_prefix
        self.request_timeout_s = request_timeout_s

    def discover(self) -> DiscoverySchema:
        return {
            "name": self.name,
            "kind": "half",
            "description": "Rasa CALM-backed structured half for booking confirmation.",
            "parameters": {"type": "object"},
            "returns": {"type": "object"},
            "error_codes": ["SA_EXT_SERVICE_UNAVAILABLE", "SA_EXT_TIMEOUT"],
            "examples": [
                {
                    "input": {"data": {"action": "confirm_booking", "deposit_gbp": 200}},
                    "output": {"success": True, "next_action": "complete"},
                }
            ],
            "version": "0.1.0",
            "metadata": {"rasa_url": self.rasa_url},
        }

    # ------------------------------------------------------------------
    # TODO — the main override
    # ------------------------------------------------------------------
    async def run(self, session: Session, input_payload: dict) -> HalfResult:
        """Send a booking intent to Rasa, translate the response to a HalfResult.

        Steps you'll implement:
          1. Pull the `data` dict out of input_payload.
          2. Pass it through normalise_booking_payload() to get a Rasa-shaped message.
          3. POST {sender, message} to self.rasa_url.
          4. Parse the response. Rasa returns a list of messages; inspect them
             to determine outcome:
               - If any message text contains "booking confirmed" or
                 custom-data {"action": "committed"} → success, next_action=complete.
               - If any contains "rejected" or {"action": "rejected"} →
                 success=False, next_action=escalate.
               - Otherwise → success=False, next_action=escalate with reason
                 "rasa returned unexpected output".
          5. Return a HalfResult. ALWAYS include 'rasa_response' in output
             so the trace can be audited later.

        Use httpx or urllib — either is fine. httpx is already in the
        sovereign-agent dependency tree via openai, so no new dep.

        On network errors, return a HalfResult with success=False,
        next_action=escalate, and summary naming the SA_EXT_ error code.
        Do NOT raise — structured-half callers expect a HalfResult.
        """
        # TODO: implement. See the docstring above for the expected logic.
        raise NotImplementedError(
            "TODO Ex6: implement RasaStructuredHalf.run(). "
            "See the docstring for the expected HTTP flow."
        )


__all__ = ["RasaStructuredHalf", "RASA_REST_WEBHOOK_DEFAULT"]
