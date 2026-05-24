# homework-pub-booking

**Build an AI agent that books a pub in Edinburgh.**

Five exercises, one story: your boss asks you to sort out a pub for
tonight. Six people, near Haymarket, starting at 19:30. Not a chain;
deposit under £300. A human would do it in half an hour of browsing.
Your agent will do it in under ten seconds, for about a penny in LLM
tokens.

By the time you finish:

- **Ex5** — the agent researches Edinburgh pubs, checks the weather,
  prices the catering, writes an HTML flyer. You can open the flyer
  in a browser. You wrote the dataflow-integrity check that would
  catch the LLM making up a price.
- **Ex6** — a Rasa Pro dialog engine running alongside your agent
  confirms the booking against policy rules. Party too big? Rasa
  rejects, and your bridge sends the agent back to look again.
- **Ex7** — you wire the round-trip bridge. The loop half and the
  structured half talk across process boundaries via atomic file IPC.
- **Ex8** — the pub manager calls back. Real voice: Speechmatics for
  speech-to-text, Rime Arcana for text-to-speech.
- **Ex9** — reflection questions grounded in YOUR session logs.

If this sounds ambitious, it is. That's the point. Production agent
systems aren't one LLM call in a loop — they're loop halves handing
off to structured halves, observing each other via atomic IPC,
recovering from rejection, sometimes speaking.

This homework teaches that architecture by making you build it,
piece by piece, against real LLMs and real services.

---

## The first hour

```bash
git clone https://github.com/sovereignagents/homework-pub-booking.git
cd homework-pub-booking

# 1. install Python 3.12 + sovereign-agent 0.2.0 + homework deps
make setup

# 2. put your Nebius key into .env (free signup at tokenfactory.nebius.com)
$EDITOR .env

# 3. confirm the environment works — one cheap LLM probe
make verify
```

If `make verify` prints green ✓ on every line, you're ready.

**Optional installs (do them only when you get to those exercises):**

```bash
make setup-rasa    # for Ex6 — adds rasa-pro (~400MB)
make setup-voice   # for Ex8 — adds speechmatics-python + sounddevice + pydub
```

Get these when you reach the exercise, not now.

---

## The first day — Ex5

Ex5 is where you learn the agent architecture by writing its tools.

### Read first

```
starter/edinburgh_research/
├── tools.py          # four tools with TODOs — your job
├── integrity.py      # verify_dataflow TODO — the heart of Ex5's grade
├── sample_data/      # fixtures — DO NOT MODIFY
│   ├── venues.json
│   ├── weather.json
│   └── catering.json
└── run.py            # runner — read it but don't modify
```

### Implement in this order

1. **`venue_search(near, party_size, budget_max_gbp)`** — read
   `venues.json`, filter by area + seats + budget. Return a
   `ToolResult` with `success=True, output={"count": N, "results": [...]}`.
2. **`get_weather(city, date)`** — read `weather.json`, look up
   the date. Return a `ToolResult` with condition + temperature.
3. **`calculate_cost(venue_id, party_size, duration_hours, catering_tier)`**
   — read `catering.json`, apply the base rate × venue modifier +
   service + venue floor. Return total + deposit.
4. **`generate_flyer(session, event_details)`** — write an HTML flyer
   to `session.workspace_dir / "flyer.html"`. Semantic tags
   (`<article>`, `<h1>`, `<dl>`) with `data-testid="<name>"` on
   every fact.
5. **`verify_dataflow(flyer_content)`** in `integrity.py` — read the
   flyer, extract every concrete fact (money, temperature, condition),
   and verify each one appeared in some tool call.

### How to run and see results

```bash
# Run offline — deterministic, no LLM tokens used
make ex5

# Expected output (when TODOs are done):
#   Session sess_xxxx
#   === flyer.html (1543 bytes) ===
#   <!DOCTYPE html>...
#   === Dataflow integrity check ===
#   ✓  dataflow OK: verified 3 fact(s) against tool outputs

# Open the flyer you just made
open "$(make logs)/workspace/flyer.html"

# Narrate what the agent did in English
make narrate-latest
```

### Then try real Nebius

```bash
make ex5-real
```

**Expect Qwen3-32B to occasionally spiral** (make 5+ venue_search
calls with increasingly desperate params). When it does, the
diagnostic shows you the tool-call histogram:

```
Tool-call histogram (8 total):
  venue_search        ████████ ← SPIRAL?
  ★ NEVER CALLED: get_weather, calculate_cost, generate_flyer
```

That IS the lesson. See [`docs/real-mode-failures.md`](docs/real-mode-failures.md)
for the defensive pattern (tool-level cap after N calls).

### The fabrication test

Once Ex5 is green, deliberately break your flyer:

```bash
# 1. Run Ex5 to produce a flyer
make ex5
# 2. Edit the generated HTML — change "£540" to "£9999"
$EDITOR "$(make logs)/workspace/flyer.html"
# 3. Re-run the dataflow check directly (not through the scenario)
python -c "
from starter.edinburgh_research.integrity import verify_dataflow
from pathlib import Path
result = verify_dataflow(Path('$(make logs)/workspace/flyer.html').read_text())
print(result.summary)
"
# Expected: dataflow FAIL: 1 unverified fact(s): ['£9999']
```

The direct check reloads the session's persisted `workspace/tool_call_log.json`;
run `make ex5` again first if you're checking an older session that predates
that file.

If your check passes with £9999 in the flyer, it's too lenient. The
grader plants exactly this fabrication during scoring.

---

## The first week — Ex6 through Ex9

### Ex6 — Rasa structured half (day 2)

**This is the one where students lose the most time to confusion**, so
read carefully.

Ex6 runs **three processes in three terminals**. Two of them are Rasa
— they live outside your Python scenario. Your code POSTs HTTP to
them; they POST HTTP to a custom-action server you also wrote.

```
 ┌────────────────┐        ┌────────────────┐        ┌──────────────────┐
 │  Terminal 3    │───────▶│  Terminal 2    │───────▶│  Terminal 1      │
 │                │ HTTP   │                │ HTTP   │                  │
 │  make ex6-real │  POST  │ make rasa-serve│  POST  │ make rasa-actions│
 │                │        │    :5005       │        │   :5055          │
 │  (scenario)    │        │                │        │                  │
 └────────────────┘        └────────────────┘        └──────────────────┘
```

**Setup (one-time):**

```bash
make setup-rasa   # installs rasa-pro (~400MB, takes 1-2 min)
```

**Get a Rasa Pro developer license** (free) at
https://rasa.com/rasa-pro-developer-edition/ → paste into `.env` as
`RASA_PRO_LICENSE=eyJh...`.

**Implement:**

1. **`starter/rasa_half/validator.py`** — `normalise_booking_payload`
   converts loose booking data into Rasa's REST message shape.
2. **`starter/rasa_half/structured_half.py`** — `RasaStructuredHalf.run`
   POSTs to Rasa, parses the response, returns a `HalfResult`.
3. **`rasa_project/actions/actions.py`** — `ActionValidateBooking`
   reads `tracker.latest_message.metadata.booking`, checks rules,
   sets slots.

**Run:**

```bash
# Terminal 1:
make rasa-actions

# Terminal 2 (trains first time, takes ~60s):
make rasa-serve

# Wait for Terminal 2 to print "Rasa server is up and running", then:
# Terminal 3:
make ex6-real
```

If `make ex6-real` fails with "Rasa isn't running yet" — you forgot
Terminals 1+2. If it fails with "Internal error" — your action server
raised a Python exception; check Terminal 1 for the real traceback.

**After ANY edit to `actions.py`:** Ctrl-C Terminal 1, restart
`make rasa-actions`. Rasa caches Python modules in memory; it will
NOT hot-reload your changes.

If you don't have a Rasa license or want to develop offline:

```bash
make ex6        # uses stdlib mock server; works without license
```

The mock matches Rasa's response shape — your `structured_half.py`
code validates end-to-end. You lose ~40% of Ex6's points (the ones
that grade against real CALM flows) but keep everything else.

**Full Rasa walkthrough:** [`docs/rasa-setup.md`](docs/rasa-setup.md)

### Ex7 — Handoff bridge (day 3)

Implement `HandoffBridge.run()` in `starter/handoff_bridge/bridge.py`.
The bridge orchestrates round-trips: loop → handoff to structured →
reject? → build a reverse task → loop again. Max 3 rounds.

```bash
make ex7           # offline deterministic trajectory
make ex7-real      # real LLM in the loop (may spiral like Ex5)
make narrate-latest   # see the state transitions
```

Expected narration:

```
--:--:--  🔁  Bridge round 1 — starting loop half
--:--:--  ↪️   State: loop → structured  (round 1)
--:--:--  ↪️   State: structured → loop  (round 1)   ← rejection!
--:--:--  🔁  Bridge round 2 — starting loop half
--:--:--  ↪️   State: loop → structured  (round 2)
--:--:--  ↪️   State: structured → complete  (round 2)   ← booked!
```

### Ex8 — Voice pipeline (day 4)

**Setup (if you want voice):**

```bash
make setup-voice
# macOS: brew install portaudio
# Then: System Settings → Privacy & Security → Microphone → grant terminal access
```

**Get API keys** from https://portal.speechmatics.com and https://rime.ai.
Add `SPEECHMATICS_KEY` and `RIME_API_KEY` to `.env`.

Implement `run_voice_mode` in `starter/voice_pipeline/voice_loop.py`:

- Mic capture via `sounddevice`
- Speechmatics real-time STT over websocket
- Pub-manager reply from Llama-3.3 via `manager_persona.py`
- Rime Arcana TTS → MP3 → pydub decode → sounddevice playback

**Run:**

```bash
make ex8-text    # free, no mic — works anywhere
make ex8-voice   # needs mic + both API keys — real conversation
```

Text mode is the PRIMARY gradeable path. Voice is a bonus. Your
trace must emit identical event shapes in either mode.

### Ex9 — Reflection (day 5)

Three questions grounded in YOUR session logs. Each answer cites
specific `sess_xxxx` IDs that ran on your machine.

```bash
$EDITOR answers/ex9_reflection.md
```

The Reasoning layer is 30/100 and graded by CI's LLM-as-judge. Write
for a human reviewer; reference real sessions by ID; be specific.

---

## Tooling — what each make target does

Run `make help` anytime for the full list. The ones you'll use most:

| Command | When |
|---|---|
| `make verify` | After setting up `.env` — probe Nebius |
| `make test` | Between commits — fast skip-aware tests |
| `make ex5` | Run Ex5 offline |
| `make ex5-real` | Run Ex5 against real Nebius (~£0.01) |
| `make narrate-latest` | See the last session in English |
| `make narrate SESSION=sess_abc` | Narrate a specific session |
| `make logs` | Print the path to your most recent session |
| `make check-submit` | Local grader (advisory) |

Same pattern for ex6, ex7, ex8. Ex6 has tiers:

| Command | Tier | Needs |
|---|---|---|
| `make ex6` | 1 (mock) | nothing |
| `make ex6-real` | 2 (two terminals) | Rasa license + 3 terminals |
| `make ex6-auto` | 3 (auto-spawn) | Rasa license only |

See `docs/rasa-setup.md` for the full Rasa walkthrough.

---

## The session directory — your main debugger

Every run creates `~/Library/Application Support/sovereign-agent/examples/<scenario>/sess_<id>/`
(macOS; `~/.local/share/...` on Linux). Inside:

```
sess_abc123/
├── SESSION.md              # human summary of the run
├── session.json            # machine state
├── workspace/
│   └── flyer.html          # what Ex5 wrote
├── logs/
│   └── trace.jsonl         # every event, every tool call
├── extras/
│   └── tickets/
│       └── tk_*.json       # one ticket per operation
└── ipc/
    └── handoff_to_*.json   # messages between halves
```

You don't need a debugger. `cat`, `ls`, `jq`, and `make narrate-latest`
are the whole toolkit. Every question you could ask ("which tool ran
when", "what did the planner output", "why did the bridge fail")
answers to a file in that directory.

This is [Decision 1](https://github.com/sovereignagents/sovereign-agent)
of the sovereign-agent architecture — sessions are directories. Your
future self, debugging at 2 AM, will thank you.

---

## Grading

Your code is graded by `grader/check_submit.py`. Run it yourself:

```bash
make check-submit
```

Layers and weights:

| Layer | Weight | What it checks |
|---|---|---|
| Mechanical | 30 | ruff, format, files exist, tests collect + pass without skips |
| Behavioural | 40 | Each scenario runs end-to-end + integrity checks |
| Reasoning | 30 | Ex9 answers (LLM judge in CI) |

**A fresh scaffold scores 4/76** — 14 Mechanical freebies (repo shape,
lint, format) minus a 10pt penalty for missing integrity checks. Don't
worry about the starting number; every exercise moves it up.

**A complete submission scores ~70/76 locally** (the 30 Reasoning
points come from CI). Cohort average is 55-65; anything above 65 is
solid.

### Real-mode failures are FEATURES, not bugs

When `make ex5-real` fails because Qwen spiralled, or `make ex6-real`
fails because you forgot to restart Rasa after editing `actions.py` —
those failures aren't marks lost. They're the curriculum.

**Every real-mode failure mode we've seen is documented in
[`docs/real-mode-failures.md`](docs/real-mode-failures.md)** with
diagnosis and workaround. Read it when something real fails. Most
of the learning happens in the debugging, not the coding.

---

## Testing

```bash
make test           # public tests — fast (skips count as fail when unimplemented)
make lint           # ruff check
make format         # ruff format --fix
make format-check   # ruff format --check
make ci             # everything CI runs on a PR, in order
```

Fresh clone reports:

```
24 passed, 3 skipped in 0.4s
```

The 3 skips are `test_verify_dataflow`, `test_normalise_booking_payload`,
and `test_ex6_validates_party_size`. Each skip triggers when your TODO
raises `NotImplementedError`. **Your goal is to turn all three into
`passed`.** That's the fastest signal you're on track.

---

## When something breaks

Four layers of help, in order of "most helpful" to "actually digging in":

1. **`make verify`** — one-shot diagnostic. Tells you if the env is broken.
2. **`make narrate-latest`** — narrates your last run in English.
3. **[`docs/real-mode-failures.md`](docs/real-mode-failures.md)** —
   every known real-mode failure with diagnosis + workaround.
4. **`cat logs/trace.jsonl`** — source of truth. Every decision the
   agent made is one `cat` away.

If all four fail, open a GitHub issue. Include the output of
`make verify` and `make narrate-latest` — usually we can spot the
problem from those.

---

## Keys and cost

| Key | For | Free tier? |
|---|---|---|
| `NEBIUS_KEY` | All LLM calls | Yes — free sign-up at tokenfactory.nebius.com |
| `RASA_PRO_LICENSE` | Ex6 real Rasa server | Yes — developer edition at rasa.com |
| `SPEECHMATICS_KEY` | Ex8 voice STT | Yes — 2h audio/month at portal.speechmatics.com |
| `RIME_API_KEY` | Ex8 voice TTS | Yes — rime.ai |

**Minimum for Ex5+Ex7+Ex9:** just `NEBIUS_KEY`.
**Add for Ex6:** `RASA_PRO_LICENSE`.
**Add for Ex8 voice:** `SPEECHMATICS_KEY` + `RIME_API_KEY`.

Total LLM spend for the whole homework: under £0.50 if you run every
`-real` command 3-5 times.

---

## Pinning policy

This cohort pins `sovereign-agent == 0.2.0` exactly.

```toml
[project]
dependencies = [
    "sovereign-agent == 0.2.0",    # do not change without a CHANGELOG entry
]
```

Different framework versions produce slightly different planner
outputs and trace shapes. One pin = one set of expected behaviours =
fair grading. We'll tell you cohort-wide if (when) to upgrade.

---

## What's in this repo

```
homework-pub-booking/
├── README.md                 # this file
├── STUDENT-ONBOARDING.md     # the first-hour checklist (duplicated here)
├── ASSIGNMENT.md             # full specs for each exercise
├── starter/                  # where you implement
│   ├── edinburgh_research/   # Ex5
│   ├── rasa_half/            # Ex6 (your Python side)
│   ├── handoff_bridge/       # Ex7
│   └── voice_pipeline/       # Ex8
├── rasa_project/             # Ex6 (the Rasa side — flows, domain, custom actions)
├── answers/                  # Ex9 reflections you'll fill in
├── tests/public/             # tests you can see
├── scripts/                  # make verify, narrate, etc.
└── docs/
    ├── rasa-setup.md         # full Rasa walkthrough
    ├── real-mode-failures.md # catalogue of real-mode failures + fixes
    ├── nebius-signup.md      # how to get an API key
    └── troubleshooting.md    # legacy; real-mode-failures.md supersedes
```

Three things are deliberately OUT of this repo:

- **Solution code.** Educators have it privately. If you see a
  `solution/` directory in your checkout, open an issue — you
  shouldn't have access.
- **Session artifacts.** Generated files stay in the platform data
  dir, not in the repo. Gitignored.
- **`.env`.** Contains secrets. Gitignored. `.env.example` is the template.

---

## Lineage

The homework architecture is taught by the
[sovereign-agent](https://github.com/sovereignagents/sovereign-agent)
framework. The teaching shape is inspired by:

- **[fastai](https://github.com/fastai/fastai)** (Jeremy Howard) —
  library and course are one thing
- **[nanoGPT](https://github.com/karpathy/nanoGPT)** (Andrej Karpathy)
  — small, readable, no magic
- **[LLMs-from-scratch](https://github.com/rasbt/LLMs-from-scratch)**
  (Sebastian Raschka) — reading order matters
- **[minitorch](https://github.com/minitorch/minitorch)** (Sasha Rush)
  — rebuild-the-framework pedagogy

The agent architecture itself — sessions-as-directories, two halves,
atomic IPC, tickets-as-commits — descends from
**[NanoClaw](https://github.com/qwibitai/nanoclaw)** (Gavriel Cohen),
with lessons absorbed from Claude Code, OpenHands, Aider, and the
SWE-agent paper.

---

## License

MIT. See [LICENSE](LICENSE).

---

**Next steps:** `make setup`, edit `.env`, `make verify`. Then open
[`ASSIGNMENT.md`](ASSIGNMENT.md) for the full Ex5 spec and start
implementing `starter/edinburgh_research/tools.py`.
