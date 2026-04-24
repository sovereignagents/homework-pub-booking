# homework-pub-booking

**Week-5 homework for the sovereign-agent course: a hybrid pub-booking agent.**

You will extend [`sovereign-agent`](https://github.com/sovereignagents/sovereign-agent) with a
two-half agent that researches Edinburgh pubs (loop half), confirms bookings under
explicit rules (Rasa-backed structured half), and optionally handles voice conversation
with a Llama-3.3-70B pub manager persona.

## What you'll build

Five exercises. The full rubric is in `docs/grading-rubric.md` (30 Mechanical / 40 Behavioural / 30 Reasoning = 100 points). Rough weight of each exercise:

- **Ex5 — Edinburgh research scenario.** Plan-and-execute loop that searches
  venues, checks weather, calculates catering cost, and writes a flyer.
  Ships with a dataflow integrity check that catches LLM fabrication.
  *(~20 points across Behavioural and the "integrity check present" rule)*
- **Ex6 — Rasa structured half.** A `StructuredHalf` subclass driven by
  Rasa CALM flows. Students wire the custom `ActionValidateBooking`.
  *(~10 points)*
- **Ex7 — Handoff bridge.** Bidirectional round-trip: loop half finds a
  venue → structured half confirms → if the manager declines, control
  returns to the loop.
  *(~8 points + grounds Ex9-Q1)*
- **Ex8 — Voice pipeline.** Llama-3.3-70B speaks as the pub manager;
  Speechmatics ASR + ElevenLabs TTS (or text-only fallback).
  *(~7 points)*
- **Ex9 — Reflection.** Three written questions grounded in your own
  logs. Each cites specific facts from a session that actually ran on
  your machine.
  *(30 points — this is the whole Reasoning layer)*

See `ASSIGNMENT.md` for the full spec, `SETUP.md` for installation, and
`docs/grading-rubric.md` for what's graded.

## Quick start

```
git clone https://github.com/sovereignagents/homework-pub-booking.git
cd homework-pub-booking
make setup         # installs Python 3.12, sovereign-agent, and all deps
make verify        # proves your environment works end-to-end
```

`make setup` takes 1-2 minutes. `make verify` makes one real Nebius API call
(cost: <£0.001) to confirm your key works. If both print green ✓, you're ready
to start Ex5.

If `make verify` prints red ✗, it tells you exactly which doc to read. Please
do read it before opening an issue — every failure mode we've seen in previous
cohorts is in `docs/troubleshooting.md`.

## Timelines

- **Released:** see CHANGELOG.md.
- **Deadline:** set by your cohort's instructor; check the course portal.
- **Office hours:** posted in the `#module1-agents` channel.
- **Support:** the `#module1-agents` channel on Discord; GitHub issues on this repo.

## Where to get help (in order)

1. Run `make verify` and paste its output. It diagnoses most problems.
2. Read `docs/troubleshooting.md` — organised by error message.
3. Check the `#module1-agents` Discord channel — someone may have asked already.
4. Open a GitHub issue on this repo with the `setup` or `question` label.

## What NOT to ask for help with

Everything explicitly covered in `SETUP.md`:

- Installing `uv` (we show three ways)
- Getting a Nebius key (step-by-step with screenshots in `docs/nebius-signup.md`)
- Loading a `.env` file (we wrote `docs/dotenv-101.md` so you don't have to Google it)
- Which Python version (3.12 exactly; `.python-version` tells pyenv)
- Windows setup (use WSL — `docs/setup-windows.md` is firm on this)

## Pinning policy

Your `pyproject.toml` pins `sovereign-agent == 0.2.0` exactly. This is deliberate:

- The homework is graded against one specific framework version.
- If `sovereign-agent` ships `0.2.1` with a bug fix, you can bump the pin by
  editing `pyproject.toml` and running `uv sync`. CHANGELOG-v2026.04-week5.1
  will describe what changed and whether the update is required.
- Bumping to `0.3.0` (a minor version) is never automatic — breaking changes
  may exist. You will be told when to upgrade cohort-wide.

## Submission

1. Commit and push your work to your fork's `main` branch.
2. CI will run the grader automatically at the deadline timestamp.
3. You'll receive a report within 24 hours via the method described in
   `docs/grading-rubric.md`.

To dry-run the grader locally before submission:

    make check-submit

This runs the same checks CI will, minus the hidden private tests (worth ~30%
of the grade; see `docs/grading-rubric.md`). A local score of 65-70 maps roughly
to a CI score in the 90s because the public tests are the "you're on track"
checks — the hidden ones probe for subtler failure modes.

## License

MIT. See `LICENSE`.
