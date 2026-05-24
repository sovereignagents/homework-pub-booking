# Ex6 — Running Rasa Pro for the homework

This doc walks through everything specific to Ex6: the architecture,
getting a license, the three-terminal workflow, common errors, and
what each log file tells you.

If you just want the recipe: `make ex6-help`.

---

## Step 0 — Install rasa-pro (one-time)

rasa-pro is an opt-in dependency (~400MB, not included in `make setup`).
It runs in its own uv environment under `rasa_project/.venv`, separate
from the homework root Python 3.12 environment. Install it once with:

```bash
make setup-rasa
```

That runs `uv sync` inside `rasa_project/`. After this, the `rasa` CLI
is available through that project's `.venv` and `make rasa-*` targets
will work.

If you don't install rasa-pro, you can still complete tier 1 of Ex6
using the mock server (`make ex6`).

---

## Why Rasa at all?

Ex6 is where the homework teaches you one of the most important patterns
in production agent systems: **the loop half is stochastic, the structured
half is deterministic — and they run as separate processes**.

The loop half (Ex5/Ex7) is an LLM with tools. It's creative, sometimes
right, sometimes wrong. Good at ambiguous tasks.

The structured half (Ex6) is Rasa CALM flows executing deterministic
Python validators. Same inputs, same outputs, always. Good at
high-stakes decisions where you need reproducibility (party size caps,
deposit limits, refund policies).

In a real deployment these two halves talk over HTTP. Your Python scenario
POSTs to Rasa; Rasa POSTs to the action server; responses flow back.

We could hide all this behind a docker-compose file and a one-command
demo. We don't, because watching three terminals teaches you the pattern
more effectively than any lecture.

---

## Critical — instruct models only for Rasa's command generator

Rasa's `CompactLLMCommandGenerator` parses the LLM's output into
structured commands (`StartFlow`, `SetSlot`, etc.). Reasoning models
like `Qwen3-Next-80B-A3B-Thinking`, `DeepSeek-R1`, or `o3-mini` emit
`<think>...</think>` blocks before their final output. Rasa's parser
doesn't handle that — it chokes on the tags.

**Always configure Rasa with an instruct model.** Our `endpoints.yml`
defaults to `meta-llama/Llama-3.3-70B-Instruct` on Nebius for this
reason.

Safe choices for Nebius:

| Model | Notes |
|---|---|
| `meta-llama/Llama-3.3-70B-Instruct` | Default. Good command-parsing reliability. |
| `meta-llama/Llama-3.1-70B-Instruct` | Older, slightly cheaper. |
| `Qwen/Qwen3-32B` | Qwen instruct line (NOT the `-Thinking` variant). |
| `MiniMaxAI/MiniMax-M2.5` | Good tool-calling support. |

**Never** use a model with `-Thinking` or `R1` in its name for Rasa's
command generator. Your scenario may still use a reasoning model for
planning (Ex5, Ex7) — those aren't subject to Rasa's parser constraint.

---

## The three processes

```
 ┌────────────────┐        ┌────────────────┐        ┌──────────────────┐
 │  Terminal 3    │───────▶│  Terminal 2    │───────▶│  Terminal 1      │
 │                │ HTTP   │                │ HTTP   │                  │
 │  make ex6-real │  POST  │ make rasa-serve│  POST  │ make rasa-actions│
 │                │        │                │        │                  │
 │  (scenario)    │        │  Rasa  :5005   │        │ actions  :5055   │
 └────────────────┘        └────────────────┘        └──────────────────┘
         │                         │                          │
         │                         │                          │
     writes                   logs flows,                writes
     session/                 transitions,               session
                              slot-sets                  events
                              to stdout
```

Three independent processes. Three terminals, three log streams, three
pieces of the puzzle that any of the three can fail independently.

---

## Getting a Rasa Pro developer license

Rasa Pro is free for developers (generous tier) but you need to sign up.

1. Go to **https://rasa.com/rasa-pro-developer-edition/**
2. Sign up with your email. Approval is usually within a few hours.
3. You receive a JWT string by email — copy it.
4. Paste it into your `.env` as `RASA_PRO_LICENSE=eyJh...`.

**About the JWT format:**
- Single line, no quotes.
- If your `.env` parser eats `"` quotes around it, Rasa will reject it.
- The token is signed; don't try to "pretty" it by reformatting.

If you can't get a license (rare but happens), you can complete Ex6 using
the mock server:

```bash
make ex6        # mock mode — no license needed
```

The mock matches Rasa's HTTP response shape, so your code (the
`normalise_booking_payload` + `RasaStructuredHalf.run` implementations)
validates end-to-end. You'll lose ~40% of Ex6's Behavioural points
(the ones that grade against real Rasa flows) but keep all of Ex5,
Ex7, Ex8, and Ex9.

---

## First-run walkthrough

Open three terminals in the homework repo directory. In each, activate
the same uv-managed venv (it just works if you use `uv run`).

### Terminal 1 — start the action server

```bash
make rasa-actions
```

Expected output after ~2 seconds:

```
▶ Starting Rasa action server (port 5055). Ctrl-C to stop.
...
action_server - Action endpoint is up and running on http://0.0.0.0:5055
```

Leave this running. Any time your `ActionValidateBooking` raises an
error, you'll see the traceback here.

### Terminal 2 — train + serve the Rasa model

```bash
make rasa-serve
```

The first time takes ~60 seconds because it trains a model:

```
▶ No trained model found; running rasa train first...
Training flow policy...
  epoch 1/100  loss 0.431
  epoch 100/100 loss 0.012
✓ Training complete.
...
▶ Starting Rasa server (port 5005). Ctrl-C to stop.
Rasa server is up and running.
```

Subsequent runs reuse the cached model in `rasa_project/models/` (~2s).

If training fails, it's almost always one of:
- Invalid JWT license
- Syntax error in `rasa_project/data/flows.yml`
- Missing custom action named in domain.yml

The training output points at which.

### Terminal 3 — run the scenario

```bash
make ex6-real
```

Expected output:

```
✓ Rasa is up at http://localhost:5005
    HTTP 200 — {"version":"3.16.4",...}
✓ Action server is up at http://localhost:5055
    HTTP 200 (reachable but not 200)

▶ Running Ex6 scenario...

📂 Session sess_7b4e1c...
   dir: ~/Library/Application Support/sovereign-agent/examples/ex6-rasa-half/sess_7b4e1c...
   (tier 2: assuming rasa-actions + rasa-serve are already running ...)
   Rasa URL: http://localhost:5005/webhooks/rest/webhook

Structured half outcome: complete
  summary: booking confirmed by rasa (ref=BK-A3F2E1D9)
  output:  {'committed': True, 'booking': {...}, 'rasa_response': [...]}

📂 Session artifacts: ~/Library/Application Support/...
📜 Narrate this run:   make narrate SESSION=sess_7b4e1c...
```

---

## Common problems

### "connection refused" or "Rasa isn't running yet"

Terminals 1 and 2 aren't up, or one of them crashed. Check:
- `curl http://localhost:5005/version` — should give JSON
- `curl http://localhost:5055/health` — should give 200

If either fails: look at the terminal running that process. There's
probably a traceback.

### "port 5005 already in use"

Something else is using the port. Find and stop it:

```bash
lsof -i :5005
kill <PID>
```

Common culprits: a previous `rasa run` you forgot to Ctrl-C, a `docker
compose` from an old version of this homework, or another app on the
same port.

### "training failed: invalid license"

Your `RASA_PRO_LICENSE` is wrong. Check:
- No quotes around the JWT in `.env`
- No newlines (it's one long line)
- You didn't accidentally swap it with a different key

Test the token with Rasa's CLI directly:

```bash
cd rasa_project
RASA_PRO_LICENSE="your-jwt" rasa train --help
```

If that prints help text without license errors, the token is valid.

### "Environment variables: ['OPENAI_API_KEY'] not set"

You're seeing this because Rasa's LiteLLM-backed client validates env
vars before calling out. Two possible causes:

1. **Old config format.** Check `rasa_project/config.yml` — if it still
   has an inline `llm:` block with `provider: openai`, move LLM config
   to `endpoints.yml` under `model_groups:`. See this repo's current
   `endpoints.yml` as the reference shape.

2. **The `${NEBIUS_KEY}` substitution isn't reaching Rasa.** The
   Makefile's `rasa-*` targets set `OPENAI_API_KEY="${NEBIUS_KEY}"`
   as a safety net, so this shouldn't happen — but if you're running
   `rasa train` directly (without `make`), export it yourself:

   ```bash
   cd rasa_project
   export OPENAI_API_KEY="$NEBIUS_KEY"
   rasa train
   ```

### "401 Incorrect API key provided" (embeddings trying to hit OpenAI)

Full error looks like:

```
litellm.AuthenticationError: ... Incorrect API key provided:
v1.CmMKH... You can find your API key at https://platform.openai.com/...
```

The key OpenAI is refusing is your Nebius key — which is correct, because
Rasa shouldn't have called OpenAI at all. The cause is **embeddings
config in the wrong place in `config.yml`**.

Correct structure:

```yaml
pipeline:
  - name: CompactLLMCommandGenerator
    llm:
      model_group: nebius_llm
    flow_retrieval:           # ← embeddings must be nested HERE
      embeddings:
        model_group: nebius_embeddings
```

Wrong structure (what triggers the 401):

```yaml
pipeline:
  - name: CompactLLMCommandGenerator
    llm:
      model_group: nebius_llm
    embeddings:               # ← WRONG: sibling to llm, not under flow_retrieval
      model_group: nebius_embeddings
```

Rasa silently falls back to its default OpenAI embeddings provider when
the embeddings key isn't found where it expects, leading to the 401 against
`api.openai.com`.

### "SingleStepLLMCommandGenerator is deprecated"

Warning, not an error. Our `config.yml` uses the current name
`CompactLLMCommandGenerator`. If you've copied an older Rasa example
into your project, update the generator name.

### "training failed: flow syntax"

`rasa_project/data/flows.yml` has a syntax error. Training logs will
point at the line. Common issues: missing `description:` on a flow,
`steps:` with invalid indentation, unknown action name.

### Rasa starts but my scenario gets a weird response

Watch Terminal 2's logs when you run `make ex6-real`. Rasa prints every
command the LLM command-generator produces, every flow transition, every
slot-set. Your flow might be taking an unexpected branch.

---

## What gets logged where

When `make educator-validate-real` runs Ex6 in tier 3 mode (auto-spawn),
it pipes each subprocess's stdout to a log file inside the session
directory:

| File | What's in it |
|---|---|
| `session/logs/rasa/rasa_train.log` | Full output of `rasa train` |
| `session/logs/rasa/rasa_server.log` | Everything Terminal 2 would show |
| `session/logs/rasa/rasa_actions.log` | Everything Terminal 1 would show |
| `session/logs/rasa/rasa_host.log` | The lifecycle manager's own trace |

When you're running yourself (tier 2, three terminals), these just go
to your terminals. If you want them captured: `make rasa-actions 2>&1 |
tee actions.log` etc.

---

## Alternative path — auto-spawn

If you really don't want to run three terminals:

```bash
make ex6-auto
```

This spawns both Rasa processes inside the scenario runner, waits for
health, runs your code, and tears everything down. Same end result as
the three-terminal path; you just don't see the individual process logs
live.

Use this when you've already learned the pattern and just want a quick
validation before committing. Use the three-terminal version while
you're still debugging — you'll save hours by having the Rasa logs
right in front of you.
