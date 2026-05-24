# Ex9 — Reflection

## Q1 — Planner handoff decision

### Your answer

In my Ex7 run (session `sess_3385ad75d55b`), the loop handed off to the
structured half in round 1. The clearest evidence is the
`handoff_to_structured` tool call, whose reason was:

> "loop half identified a candidate venue; passing to structured half for confirmation under policy rules"

The signal was that the loop had finished the open-ended research step:
it found a candidate venue, `haymarket_tap`, for a party of 12 near
Haymarket. At that point the remaining task was not research anymore;
it was deterministic booking validation under policy rules, especially
party-size and deposit limits. That is why the bridge routed the proposal
from `loop` to `structured`.

This decision is advisory at the planner/loop level but becomes physical
when the executor calls `handoff_to_structured` and the bridge writes the
handoff file. The structured half then validates the proposal and rejects
it with `party_too_large`, which proves the handoff was doing useful
policy work rather than just moving data around.

The broader lesson is that the loop half can propose a booking, but it
should not be trusted to commit one. The policy logic belongs in the
structured half's deterministic Python/Rasa validation, so even if the
LLM prose is ambiguous, the final booking decision is guarded by code.

### Citation

- `sessions/sess_3385ad75d55b/logs/trace.jsonl`
- `sessions/sess_3385ad75d55b/logs/handoffs/round_1_forward.json`



---

## Q2 — Dataflow integrity catch

### Your answer


sess_10b97779ceb2-early exit: The trace shows an agent-flow failure, Initially, the planner received the correct 
context, including party size 6, date 2026-05-02, time 19:19, and the Haymarket area, but it split the work into 
5 subgoals. This is far more than the expected  4 as many as the tools, whicb increases already the chance for failure.
The executor successfully found the correct venue, haymarket_tap, then prematurely called complete_task 
for that subgoal. It later fetched the weather for the correct date, but when it reached cost calculation 
it no longer carried forward the venue_id which had found from the task, so it handed off instead of calling 
calculate_cost. Verify dataflow did not detect this failure as no final flyer was created.This is now edited 
in the latest verify_dataflow.


Also during development I observed situation where  during the dataflow the venus search\
selected 'Haymarket_tap' but subsequnet tools like calculator  hallucinated and that was carried over to \
the flyer. In the original verify-dataflow this was a pass , falsely.
In the editted version I added condition that extracted infomration from all the used tools\
need to match for stricter pass.


### Citation

- sessions/sess_10b97779ceb2-hallucin/workspace/flyer.md
- sessions/sess_10b97779ceb2-hallucin/logs/trace.jsonl

---

## Q3 — Failure

### Your answer

The first production failure I would expect is conversation mixing under
load. In our homework code, the Rasa sender ID is derived from venue, date,
and time. Two customers booking the same venue at the same time could share
the same sender ID, so Rasa might treat their messages as one conversation.

The sovereign-agent primitive that would surface this is session identity:
each run has a `session_id`, and every Rasa request should use that session
ID as the sender. If the sender is not tied to the session, the trace and
Rasa tracker can diverge, making debugging very difficult.

In simple words: Rasa separates workflows by `sender`. If sender IDs collide,
requests can mix. The fix is to use the sovereign-agent session ID, not a
hash of booking details.

***
Equally another very obvious failorey is the stale venue data. In the
homework, the loop half chooses pubs from a fixed JSON file, but in a real
business pubs open, close, change capacity, change deposit rules, or stop
taking private bookings. The agent might confidently propose a venue that
is no longer available.

The sovereign-agent primitive that would surface this is the ticket state
machine. Venue lookup should be a ticketed tool call with a clear success or
failure state. If the live venue API says the pub is closed, unavailable, or
returns no current availability, the ticket should fail instead of letting
the planner continue with stale data.

In simple words: the risky part is not only whether the LLM can pick a pub.
The risky part is whether the pub data is current. A real agent should treat
venue availability as a fresh tool result, not as a memory or hardcoded JSON
fact.
