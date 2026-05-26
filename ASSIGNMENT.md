# ASSIGNMENT.md — Ex5 through Ex9

This document is the authoritative specification of what you're being asked to
build. Everything you submit will be graded against the rubric in
`docs/grading-rubric.md`, which scores against this document.

> If you find a conflict between what an exercise's `README.md` under
> `starter/` says and what this document says, **this document wins**. Open
> an issue and we'll fix the README.

## The scenario

A customer wants to book an Edinburgh pub for an event. Your agent has to:

1. **Research** open pubs near Haymarket that can seat the party, check the
   weather, work out catering cost, and produce a flyer.
2. **Confirm** the booking under strict rules — no booking without checking the
   deposit amount, no booking over the party-size cap without escalation.
3. **Handle the round-trip** if the pub manager declines: go back to research,
   propose an alternative, try again.
4. **Speak to the manager** — simulated by an LLM persona — either in text
   mode or with real voice.

This is explicitly a **hybrid** scenario: the loop half (open-ended research)
and the structured half (rule-following confirmation) are BOTH needed. Using
only one cannot earn full marks.

The scenario extends the existing `examples/pub_booking` scenario in
sovereign-agent, but with deeper tooling and production-readiness checks.

---

## Ex5 — Edinburgh research scenario (20 points)

**Location:** `starter/edinburgh_research/`

**Goal:** a complete loop-half scenario that plans, executes, and produces a
flyer, with a dataflow integrity check that catches LLM fabrication.

### What you must implement

1. **Four tools** in `tools.py`:
   - `venue_search(near: str, party_size: int, budget_max_gbp: int) -> dict`
     — read `sample_data/venues.json`, return matches.
   - `get_weather(city: str, date: str) -> dict` — read `sample_data/weather.json`.
   - `calculate_cost(venue_id: str, party_size: int, duration_hours: int) -> dict`
     — use `sample_data/catering.json` to compute cost breakdown.
   - `generate_flyer(event_details: dict) -> dict` — produce a markdown flyer
     and write it to `workspace/flyer.md` in the session directory.

   All four are `parallel_safe=True` for reads, `False` for `generate_flyer`
   (it writes a file). Every tool logs its arguments and output into the
   `_TOOL_CALL_LOG` defined in `integrity.py`.

2. **A dataflow integrity check** in `integrity.py`:
   - Maintains a module-level `_TOOL_CALL_LOG` as a `list[ToolCallRecord]`.
   - Provides `verify_dataflow(session, flyer_content) -> IntegrityResult`.
   - The check: every specific fact in the final flyer (venue name, price,
     weather condition) must trace back to a tool call that produced that
     exact value. If a fact appears that was never returned by any tool,
     the agent **hallucinated** it. The check fails and reports the
     offending fact.

3. **A runnable scenario** in `run.py`:
   - Builds a `DefaultPlanner + DefaultExecutor + LoopHalf` using the
     session-scoped builtin tools plus yours.
   - Default mode uses `FakeLLMClient` with a scripted trajectory.
   - `--real` flag switches to `OpenAICompatibleClient` + Nebius.
   - Both modes end with a call to `verify_dataflow` and fail the run with
     a clear message if the check fails.

### How you're graded

| Aspect | Weight |
|---|---|
| `make ex5` runs clean; flyer.md written to session workspace | 4 pts |
| `venue_search`, `get_weather`, `calculate_cost` all read their fixtures correctly | 4 pts |
| `generate_flyer` is marked `parallel_safe=False` | 1 pt |
| `verify_dataflow` catches planted fabrication (grader plants one) | 6 pts |
| `verify_dataflow` does NOT false-positive on correct flyers | 3 pts |
| Session has at least one successful planner ticket AND one successful executor ticket, both with verified manifests | 2 pts |

**Penalty: −3 pts** if any tool is missing a dataflow entry (no tool call
gets to bypass integrity tracking).

---

## Ex6 — Rasa structured half (20 points)

**Location:** `starter/rasa_half/`, `rasa_project/`

**Goal:** wire Rasa CALM as the structured half, replacing the minimal
in-process `StructuredHalf` with a real dialog manager.

### What you must implement

1. **`StructuredHalf` subclass** in `structured_half.py` that routes a dict
   of booking intent into Rasa via an HTTP call, and routes Rasa's response
   back as a `HalfResult`.

2. **Rasa flows** in `rasa_project/data/flows.yml`:
   - `confirm_booking` — the happy path, ends by committing.
   - `resume_from_loop` — triggered when the loop half hands off mid-scenario.
   - `request_research` — triggered when the manager's reply doesn't fit the
     cap; sends the agent back to the loop half for another venue.

3. **Custom Rasa action** `ActionValidateBooking` in
   `rasa_project/actions/actions.py` — validates deposit <= £300 and party
   size <= 8. Returns a rejection reason to the flow if either fails.

4. **Validator** in `starter/rasa_half/validator.py` — the Python-side
   bridge that normalises booking data before it goes to Rasa (e.g.
   parses £ into int, canonicalises date formats).

### How you're graded

| Aspect | Weight |
|---|---|
| `make ex6` runs clean with Rasa container up | 4 pts |
| `confirm_booking` flow commits a valid booking | 4 pts |
| `ActionValidateBooking` correctly rejects deposits > £300 | 3 pts |
| `ActionValidateBooking` correctly rejects parties > 8 | 3 pts |
| `resume_from_loop` flow re-enters correctly after loop-side handoff | 4 pts |
| Validator normalises at least 3 of: date, currency, party size, time zone, venue_id | 2 pts |

---

## Ex7 — Handoff bridge (20 points)

**Location:** `starter/handoff_bridge/`

**Goal:** a BIDIRECTIONAL handoff round-trip between the loop half and the
structured half. Loop → structured → loop → structured → completion, at
minimum.

### What you must implement

1. **Bridge logic** in `bridge.py`: glue that reads an outgoing handoff
   from the loop half, dispatches it to Ex6's Rasa-backed structured half,
   and writes the return handoff back if the structured half rejects
   (e.g. party size > 8, so re-research).

2. **End-to-end demo** in `run.py`:
   - Start with a request: "party of 12, Haymarket, Friday 19:30".
   - Loop half finds `haymarket_tap` (only has 8 seats, below party size).
   - Hands off to structured half.
   - Structured half rejects with "party exceeds cap".
   - Bridge returns to loop half, which finds a different venue.
   - Second round: `royal_oak` (16 seats) — structured half approves.
   - Session marks complete with the final booking.

### How you're graded

| Aspect | Weight |
|---|---|
| Forward handoff (loop → structured) preserved with full context | 4 pts |
| Reverse handoff (structured → loop) preserved with rejection reason | 4 pts |
| Session reaches `completed` state within 3 round trips | 4 pts |
| At most one handoff file visible in `ipc/` at any time (fail-closed rule) | 2 pts |
| Trace contains clear `session.state_changed` events for each transition | 3 pts |
| Grader's planted failure (structured half always rejects) is caught and reported | 3 pts |

---

## Ex8 — Voice pipeline (20 points)

**Location:** `starter/voice_pipeline/`

**Goal:** a voice interaction with a Llama-3.3-70B pub manager persona. The
agent (your code) speaks to the manager; the manager responds in character
and may or may not accept the booking.

### What you must implement

1. **Manager persona** in `manager_persona.py` — system prompt + `ManagerPersona`
   class wrapping an `OpenAICompatibleClient` pointed at Llama-3.3-70B-Instruct
   on Nebius. The persona:
   - Speaks in the voice of a gruff Edinburgh pub manager.
   - Accepts bookings under £300 deposit and <= 8 people.
   - Declines otherwise, with a specific reason.

2. **Voice loop** in `voice_loop.py` — STT → agent → TTS round-trip:
   - Text mode (`--text`): reads from stdin, prints responses.
   - Voice mode (`--voice`): uses fully offline local models (Whisper for STT, Piper for TTS).
   - In both modes, the conversation is logged to the session as trace events
     with the correct event types (`voice.utterance_in`, `voice.utterance_out`).

3. **Graceful degradation**: if local models or dependencies fail to load but `--voice`
   was passed, fall back to text mode with a visible warning. Don't crash.

### How you're graded

| Aspect | Weight |
|---|---|
| Text mode runs a full 3+ turn conversation | 6 pts |
| Manager persona stays in character (LLM-as-judge, see §Reasoning) | 4 pts |
| Voice mode works end-to-end (if attempted) | 4 pts |
| Every utterance is in the trace with correct event_type | 3 pts |
| Missing dependency graceful degradation | 3 pts |

**Note:** If you cannot run local voice models and skip voice mode entirely, you can still score up to 16/20 on Ex8.

---

## Ex9 — Reflection (20 points)

**Location:** `answers/ex9_reflection.md`

**Goal:** three short written responses. Each must be grounded in specific
log entries or tickets from YOUR OWN runs — copy-paste of example output
gets zero marks.

### The three questions

- **Q1.** Find a point in your Ex7 logs where the planner decided to hand off
  to the structured half. Quote the planner's reasoning or the specific
  subgoal's `assigned_half` field. What signal caused the decision?
- **Q2.** Describe one instance where your Ex5 dataflow integrity check caught
  something manual inspection missed, OR (if you never saw it trigger) describe
  a plausible scenario where it WOULD catch a failure that a human reviewer
  wouldn't. Your scenario must be specific enough that someone else could
  construct the test case.
- **Q3.** If you were shipping this agent to a real pub-booking business next
  week, what's the first production failure you'd expect, and which
  sovereign-agent primitive (ticket state machine, manifest discipline,
  IPC atomic rename, SessionQueue retry, etc.) would surface it? One specific
  primitive, one specific failure mode.

### How you're graded

| Aspect | Weight |
|---|---|
| Each answer cites specific ticket IDs or trace lines from your own session dirs | 9 pts (3 × 3) |
| Each answer is 100-400 words — not shorter, not longer | 3 pts (1 × 3) |
| Answers are grounded in reality (not generic LLM waffle) | 6 pts (2 × 3) |
| Q3 names exactly ONE primitive and exactly ONE failure mode | 2 pts |

An LLM-as-judge (running a different model than the one you used) scores the
"grounded in reality" dimension by cross-checking your citations against the
trace artifacts committed to your repo at submission time.

---

## Integrity requirements (apply to every exercise)

- **Every scenario ships with a dataflow integrity check.** Ex5's is explicit;
  Ex6 and Ex7 can reuse Ex5's with minor adaptations; Ex8's is a per-utterance
  audit. **Penalty: −10 pts** from Mechanical if any scenario is missing.
- **No raw secrets committed.** `.env` is gitignored. If your submission
  contains a secret in source, the grader auto-detects and returns the
  submission with a zero on the affected exercise.
- **No LLM-generated commit messages wholesale.** Short commits are fine;
  commit floods of indistinguishable "fix X", "fix X (really this time)"
  messages are flagged for review and may lose Mechanical points.

## Submission

See `README.md` §Submission. Briefly: commit to `main`, CI runs at the
deadline, you receive a report.

Good luck. Ask questions early.
