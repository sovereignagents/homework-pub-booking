# homework-pub-booking — student-facing commands.
#
# Run `make` (no args) or `make help` to see the structured workflow.
# Run `make next` to get the exact next command to run based on repo state.

PY := python3
UV := uv

# Load .env into Make's own environment and export every variable to
# child processes. This is how Rasa/sovereign-agent/subprocess.run all
# end up seeing RASA_PRO_LICENSE, NEBIUS_KEY, etc. without extra Python
# plumbing. Idiom borrowed from the Rasa reference Makefile.
ifneq (,$(wildcard .env))
    include .env
    export
endif

# ── Terminal colours ──────────────────────────────────────────────────
# Uses tput if available; falls back to empty strings if not.
GREEN   := $(shell tput -Txterm setaf 2 2>/dev/null)
YELLOW  := $(shell tput -Txterm setaf 3 2>/dev/null)
BLUE    := $(shell tput -Txterm setaf 4 2>/dev/null)
MAGENTA := $(shell tput -Txterm setaf 5 2>/dev/null)
CYAN    := $(shell tput -Txterm setaf 6 2>/dev/null)
RED     := $(shell tput -Txterm setaf 1 2>/dev/null)
BOLD    := $(shell tput -Txterm bold 2>/dev/null)
DIM     := $(shell tput -Txterm dim 2>/dev/null)
RESET   := $(shell tput -Txterm sgr0 2>/dev/null)

.DEFAULT_GOAL := help

# ─── help — the main navigation ────────────────────────────────────────

.PHONY: help
help: ## Structured help — your actual starting point
	@echo ''
	@echo '${BOLD}${MAGENTA}🍺 homework-pub-booking${RESET} — build an AI agent that books a pub'
	@echo ''
	@echo '${DIM}Run ${RESET}${CYAN}make next${RESET}${DIM} any time — it tells you exactly what to do based on your repo state.${RESET}'
	@echo ''
	@echo '${YELLOW}${BOLD}🚀 FIRST-TIME SETUP${RESET} ${DIM}(do these once, in order)${RESET}'
	@echo '  ${GREEN}1.${RESET} ${CYAN}make setup${RESET}              install Python deps + create .env'
	@echo '  ${GREEN}2.${RESET} ${DIM}edit .env${RESET}                 set NEBIUS_KEY (minimum) — get one at tokenfactory.nebius.com'
	@echo '  ${GREEN}3.${RESET} ${CYAN}make verify${RESET}             probe Nebius with one cheap LLM call'
	@echo ''
	@echo '${YELLOW}${BOLD}📚 YOUR DAILY LOOP${RESET} ${DIM}(while implementing)${RESET}'
	@echo '  ${CYAN}make test${RESET}                    run public tests (skips → fails when TODOs unimplemented)'
	@echo '  ${CYAN}make check-submit${RESET}            run the local grader (advisory; CI is authoritative)'
	@echo '  ${CYAN}make narrate-latest${RESET}          narrate the most recent session in plain English'
	@echo '  ${CYAN}make logs${RESET}                    print the path to your most recent session'
	@echo ''
	@echo '${YELLOW}${BOLD}🎯 EXERCISES${RESET} ${DIM}(all have offline + -real variants)${RESET}'
	@echo '  ${GREEN}Ex5${RESET}  — Edinburgh research (loop half + 4 tools)'
	@echo '      ${CYAN}make ex5${RESET}                 offline (scripted LLM)'
	@echo '      ${CYAN}make ex5-real${RESET}            real Nebius (~£0.01, may spiral — see docs/real-mode-failures.md)'
	@echo ''
	@echo '  ${GREEN}Ex6${RESET}  — Rasa structured half (THREE TERMINALS) ${DIM}→ make ex6-help for the recipe${RESET}'
	@echo '      ${CYAN}make ex6${RESET}                 offline (stdlib mock, no setup)'
	@echo '      ${CYAN}make ex6-real${RESET}            real Rasa (needs setup-rasa + 3 terminals)'
	@echo '      ${CYAN}make ex6-auto${RESET}            one-terminal convenience (hides the lesson)'
	@echo ''
	@echo '  ${GREEN}Ex7${RESET}  — Handoff bridge (loop ↔ structured round-trip)'
	@echo '      ${CYAN}make ex7${RESET}                 offline scripted round-trip'
	@echo '      ${CYAN}make ex7-real${RESET}            real LLM in the loop'
	@echo ''
	@echo '  ${GREEN}Ex8${RESET}  — Voice pipeline ${DIM}${RESET}'
	@echo '      ${CYAN}make ex8-text${RESET}            text mode (free, no mic)'
	@echo '      ${CYAN}make ex8-voice${RESET}           real local Whisper + Piper TTS (needs setup-voice + mic)'
	@echo ''
	@echo '${YELLOW}${BOLD}🔧 OPTIONAL INSTALLS${RESET} ${DIM}(install only when you reach that exercise)${RESET}'
	@echo '  ${CYAN}make setup-rasa${RESET}              rasa-pro for Ex6 (~400MB, ~2min)'
	@echo '  ${CYAN}make setup-voice${RESET}             whisper + piper-tts + sounddevice for Ex8 voice'
	@echo ''
	@echo '${YELLOW}${BOLD}🎭 RASA (Ex6 ONLY)${RESET} ${DIM}three terminals — read docs/rasa-setup.md first${RESET}'
	@echo '  ${DIM}Terminal 1:${RESET} ${CYAN}make rasa-actions${RESET}      action server on :5055'
	@echo '  ${DIM}Terminal 2:${RESET} ${CYAN}make rasa-serve${RESET}        Rasa server on :5005 (trains if needed)'
	@echo '  ${DIM}Terminal 3:${RESET} ${CYAN}make ex6-real${RESET}          the scenario'
	@echo '  ${DIM}Reset:${RESET}     ${CYAN}make rasa-clean${RESET}        wipe trained model + cache'
	@echo '  ${DIM}Help:${RESET}      ${CYAN}make ex6-help${RESET}          the recipe in detail'
	@echo ''
	@echo '${YELLOW}${BOLD}🩺 WHEN THINGS BREAK${RESET}'
	@echo '  ${CYAN}make verify${RESET}                  one-shot env diagnostic'
	@echo '  ${CYAN}make narrate-latest${RESET}          last session in English'
	@echo '  ${DIM}docs/real-mode-failures.md${RESET}   catalogue of known failures + fixes'
	@echo '  ${DIM}cat \$$(make logs)/logs/trace.jsonl${RESET}  raw source of truth'
	@echo ''
	@echo '${YELLOW}${BOLD}🧹 HOUSEKEEPING${RESET}'
	@echo '  ${CYAN}make format${RESET}                  ruff format --fix'
	@echo '  ${CYAN}make lint${RESET}                    ruff check'
	@echo '  ${CYAN}make ci${RESET}                      everything CI runs on a PR'
	@echo '  ${CYAN}make clean${RESET}                   delete generated session artifacts'
	@echo '  ${CYAN}make clean-all${RESET}               full reset (deletes .venv too)'
	@echo ''
	@echo '${DIM}Less-used targets:${RESET} ${CYAN}make help-all${RESET} for the complete flat list (legacy).'
	@echo ''

.PHONY: help-all
help-all: ## Show the flat list of every target (legacy)
	@awk 'BEGIN {FS = ":.*##"; printf "\n${YELLOW}All targets (flat list):${RESET}\n\n"} \
	/^[a-zA-Z_-]+:.*?##/ { printf "  ${CYAN}%-30s${RESET} %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""

# ─── `make next` — state-aware guidance ─────────────────────────────────

.PHONY: next
next: ## Inspect repo state and tell you the exact next command to run
	@$(UV) run python scripts/make_next.py 2>/dev/null || \
	  $(PY) scripts/make_next.py

# ─── setup / verify ─────────────────────────────────────────────────────

.PHONY: setup
setup: ## Install Python 3.12, deps, and create .env from the template
	@command -v $(UV) >/dev/null 2>&1 || { \
	  echo "✗ uv is not installed."; \
	  echo "  Install from https://astral.sh/uv or run: pip install uv"; \
	  exit 1; \
	}
	@$(UV) sync --all-groups
	@if [ -f .env ]; then \
	  echo "✓ .env already exists (not overwriting)."; \
	elif [ -f .env.example ]; then \
	  cp .env.example .env && echo "✓ Created .env from template. Edit it and set NEBIUS_KEY."; \
	else \
	  echo "✗ Cannot create .env — .env.example is missing from your checkout."; \
	  echo ""; \
	  echo "  Your tarball extract didn't include dotfiles. Fix with one of:"; \
	  echo "    1. Re-extract with 'tar xzvf homework-pub-booking.tar.gz'"; \
	  echo "       — look for '.env.example' in the output to confirm."; \
	  echo "    2. Or run 'make env-bootstrap' — it regenerates .env.example"; \
	  echo "       from a bundled fallback inside the Makefile."; \
	  exit 1; \
	fi
	@echo ""
	@echo "✓ make setup done. Next steps:"
	@echo "    1. Edit .env (at minimum set NEBIUS_KEY)"
	@echo "    2. make verify          — confirm env works with a cheap live LLM call"
	@echo "    3. make ex5             — try the first exercise offline"
	@echo ""
	@echo "  For Ex6 (Rasa) you'll also need:  make setup-rasa"
	@echo "  That installs an extra ~400MB of Rasa-related deps (opt-in)."
	@echo ""

.PHONY: env-bootstrap
env-bootstrap: ## Regenerate .env.example from a bundled fallback (use if .env.example is missing)
	@if [ -f .env.example ]; then \
	  echo "ℹ .env.example already exists — not overwriting."; \
	  echo "  To force-regenerate: rm .env.example && make env-bootstrap"; \
	else \
	  $(UV) run python scripts/write_env_example.py; \
	  echo "✓ Wrote .env.example. Now run 'make setup'."; \
	fi

.PHONY: verify
verify: ## Run preflight + a real 1-token LLM call; prints green ✓ or points you at the right doc
	@$(UV) run python scripts/preflight.py
	@$(UV) run python scripts/nebius_smoke.py

# ─── tests / grading ────────────────────────────────────────────────────

.PHONY: test
test: ## Run the public test suite (pass = you're on track)
	@$(UV) run pytest tests/public -v

.PHONY: test-all
test-all: ## Run public + private tests (private tests only exist in the grader CI environment)
	@$(UV) run pytest tests/ -v

.PHONY: check-submit
check-submit: ## Run the local grader (advisory — CI at deadline is the authoritative grade)
	@$(UV) run python -m grader.check_submit

# ─── per-exercise targets ───────────────────────────────────────────────

# ─── rasa host-process (for Ex6) ──────────────────────────────────────
# Ex6 needs two Rasa processes on localhost. Students run each in its
# own terminal. The educator harness spawns them automatically when
# you `make ex6-real`.

# The three Rasa targets all check that `rasa` is installed. If it's
# not, they print a friendly install hint instead of the cryptic
# "Failed to spawn rasa" error uv gives. Students can't miss it.

define _rasa_preflight
	@if ! $(UV) run --no-sync which rasa >/dev/null 2>&1; then \
	  echo ""; \
	  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
	  echo "  ✗ rasa-pro isn't installed in this venv yet"; \
	  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
	  echo ""; \
	  echo "  rasa-pro is an opt-in extra (~400MB of deps). Install it with:"; \
	  echo ""; \
	  echo "      make setup-rasa"; \
	  echo ""; \
	  echo "  That runs 'uv sync --extra rasa'. Takes 1-2 minutes on first install."; \
	  echo "  Then re-run this command."; \
	  echo ""; \
	  echo "  Don't want to install rasa-pro yet?"; \
	  echo "    tier-1 mock mode works without it:  make ex6"; \
	  echo ""; \
	  exit 1; \
	fi
endef

.PHONY: setup-rasa
setup-rasa: ## Install rasa-pro + deps (needed for Ex6 tier 2 and 3)
	@echo "▶ Installing rasa-pro and related deps into .venv..."
	@echo "   This is a one-time ~1-2 minute install."
	@$(UV) sync --extra rasa
	@echo "✓ rasa-pro installed. You can now run: make rasa-actions / make rasa-serve"

.PHONY: setup-voice
setup-voice: ## Install local voice deps (whisper, piper-tts, sounddevice)
	@echo "▶ Installing voice deps (whisper, piper-tts, sounddevice)..."
	@echo "   Requires portaudio and ALSA plugins."
	@echo "   On Ubuntu/Debian: sudo apt-get install -y portaudio19-dev libasound2-plugins"
	@echo "   On macOS: brew install portaudio"
	@$(UV) sync --extra voice
	@echo ""
	@echo "✓ voice deps installed. For Ex8 voice mode you still need:"
	@echo "    - macOS: System Settings → Privacy & Security → Microphone"
	@echo "             → grant your terminal app access"
	@echo "    - Then: make ex8-voice"

.PHONY: rasa-train
rasa-train: ## Train the Rasa model (reruns use the cached model)
	$(_rasa_preflight)
	@cd rasa_project && OPENAI_API_KEY="$${NEBIUS_KEY}" $(UV) run rasa train

.PHONY: rasa-actions
rasa-actions: ## Terminal 1 — run the Rasa action server on :5055
	$(_rasa_preflight)
	@echo "▶ Starting Rasa action server (port 5055). Ctrl-C to stop."
	@cd rasa_project && OPENAI_API_KEY="$${NEBIUS_KEY}" $(UV) run rasa run actions -p 5055

.PHONY: rasa-serve
rasa-serve: ## Terminal 2 — run the Rasa server on :5005 (trains if needed)
	$(_rasa_preflight)
	@cd rasa_project && \
	  if [ ! -d models ] || [ -z "$$(ls -A models 2>/dev/null)" ]; then \
	    echo "▶ No trained model found; running rasa train first..."; \
	    OPENAI_API_KEY="$${NEBIUS_KEY}" $(UV) run rasa train; \
	  fi
	@echo "▶ Starting Rasa server (port 5005). Ctrl-C to stop."
	@cd rasa_project && OPENAI_API_KEY="$${NEBIUS_KEY}" $(UV) run rasa run --enable-api --cors "*" -p 5005

.PHONY: rasa-clean
rasa-clean: ## Remove Rasa's trained models and cache
	@rm -rf rasa_project/models rasa_project/.rasa 2>/dev/null
	@echo "✓ rasa_project/models/ and .rasa/ removed"

# ─── log / session discovery ──────────────────────────────────────────

.PHONY: logs
logs: ## Print the path to your most recent session (across all scenarios)
	@$(UV) run python -c "import sys; sys.path.insert(0, 'scripts'); \
		from narrator import _platform_data_dir; \
		from pathlib import Path; \
		cands = []; \
		[cands.extend(Path('sessions').glob('sess_*'))] if Path('sessions').exists() else None; \
		root = _platform_data_dir(); \
		[cands.extend(root.glob('examples/*/sess_*'))] if root.exists() else None; \
		cands = [c for c in cands if c.is_dir()]; \
		cands.sort(key=lambda p: p.stat().st_mtime, reverse=True); \
		print(cands[0] if cands else '(no sessions yet)')"

# ─── narration ────────────────────────────────────────────────────────

.PHONY: narrate
narrate: ## Narrate a session by id: make narrate SESSION=sess_abc123
	@if [ -z "$(SESSION)" ]; then \
	  echo "Usage: make narrate SESSION=<session-id>"; \
	  echo "Tip:   make narrate-latest   # narrate the most recent session"; \
	  exit 2; \
	fi
	@$(UV) run python scripts/narrator.py --session $(SESSION)

.PHONY: narrate-latest
narrate-latest: ## Narrate the most recent session — useful right after `make ex5-real`
	@$(UV) run python scripts/narrator.py --latest

.PHONY: ex5
ex5: ## Run Ex5 (Edinburgh research) in offline FakeLLMClient mode
	@$(UV) run python -m starter.edinburgh_research.run

.PHONY: ex5-real
ex5-real: ## Run Ex5 against the real Nebius LLM (uses tokens!)
	@$(UV) run python -m starter.edinburgh_research.run --real

.PHONY: ex6
ex6: ## Ex6 (mock) — offline Rasa mock, no setup needed (tier 1)
	@$(UV) run python -m starter.rasa_half.run

.PHONY: ex6-real
ex6-real: ## Ex6 (two-terminal) — probe localhost:5005, run if Rasa is up (tier 2, recommended)
	@$(UV) run python scripts/ex6_probe_and_run.py

.PHONY: ex6-auto
ex6-auto: ## Ex6 (one-terminal) — auto-spawn Rasa + action server, run, tear down (tier 3)
	@$(UV) run python -m starter.rasa_half.run --real --auto

.PHONY: ex6-help
ex6-help: ## Print the three-terminal recipe for Ex6 real mode
	@$(UV) run python scripts/ex6_help.py

.PHONY: ex7
ex7: ## Run Ex7 (handoff bridge) end-to-end
	@$(UV) run python -m starter.handoff_bridge.run

.PHONY: ex8-text
ex8-text: ## Run Ex8 (voice pipeline) in TEXT-ONLY mode — no Speechmatics needed
	@$(UV) run python -m starter.voice_pipeline.run --text

.PHONY: ex8-voice
ex8-voice: ## Run Ex8 with real STT/TTS — requires SPEECHMATICS_KEY
	@$(UV) run python -m starter.voice_pipeline.run --voice

.PHONY: ex9
ex9: ## Validate that your Ex9 reflection answers are populated and well-formed
	@$(UV) run python -m grader.check_submit --only ex9

# ─── housekeeping ───────────────────────────────────────────────────────

.PHONY: lint
lint: ## Ruff check
	@$(UV) run ruff check starter/ grader/ tests/ scripts/

.PHONY: format
format: ## Ruff format
	@$(UV) run ruff format starter/ grader/ tests/ scripts/

.PHONY: format-check
format-check: ## Ruff format --check (used by CI)
	@$(UV) run ruff format --check starter/ grader/ tests/ scripts/

.PHONY: clean
clean: ## Delete local session artifacts (does NOT delete your answers or code)
	@rm -rf sessions/ demo_sessions_* .pytest_cache/ .ruff_cache/ 2>/dev/null || true
	@echo "✓ cleaned session artifacts (your answers/ and starter/ are untouched)"

.PHONY: clean-all
clean-all: clean ## Full reset — delete .venv too, start over fresh
	@rm -rf .venv/ uv.lock
	@echo "✓ full reset. Run 'make setup' to start over."

.PHONY: doctor
doctor: ## Like sovereign-agent doctor but scoped to this repo
	@$(UV) run python scripts/preflight.py

.PHONY: ci
ci: lint format-check test ## Everything CI runs on a PR, in order
	@echo "✓ make ci green — your scaffold still compiles and tests pass."

# ─── educator-only targets (hidden from students) ───────────────────
# These require solution/ to exist. Students don't have it; running
# any of these from a student's checkout will print a helpful error.

.PHONY: educator-apply-solution
educator-apply-solution: ## [EDUCATOR] Copy solution/ over starter/ for validation
	@if [ ! -d solution ]; then \
	  echo "✗ solution/ not found — this target is educator-only."; \
	  echo "  Solutions live in a private sibling repo and are copied in manually."; \
	  exit 1; \
	fi
	@bash solution/apply_solution.sh

.PHONY: educator-reset
educator-reset: ## [EDUCATOR] Restore starter/, answers/, rasa_project/ from .educator_backup/
	@if [ ! -d .educator_backup ]; then \
	  echo "✗ .educator_backup/ not found. Did you ever run educator-apply-solution?"; \
	  exit 1; \
	fi
	@rm -rf starter answers rasa_project
	@cp -r .educator_backup/starter starter
	@cp -r .educator_backup/answers answers
	@if [ -d .educator_backup/rasa_project ]; then cp -r .educator_backup/rasa_project rasa_project; fi
	@echo "✓ starter/, answers/, rasa_project/ restored"

.PHONY: educator-validate
educator-validate: ## [EDUCATOR] Back up, apply solution, run all scenarios (offline), grade, restore
	@if [ ! -d solution ]; then \
	  echo "✗ solution/ not found — this target is educator-only."; \
	  exit 1; \
	fi
	@$(UV) run python scripts/educator_validate.py

.PHONY: educator-validate-real
educator-validate-real: ## [EDUCATOR] Diagnostic run against live services (~$0.20) — reports what happened, always exits 0
	@if [ ! -d solution ]; then \
	  echo "✗ solution/ not found — this target is educator-only."; \
	  exit 1; \
	fi
	@echo ""
	@echo "🔬 DIAGNOSTIC run against LIVE services:"
	@echo "   - Ex5/Ex7: Nebius API (~\$$0.05 each)"
	@echo "   - Ex6:     Rasa Pro host-process (needs RASA_PRO_LICENSE + 60-90s first-train)"
	@echo "   - Ex8:     heuristic check only (voice needs a mic; test manually)"
	@echo "   Total: ~\$$0.10-\$$0.20 and ~3 minutes on first run."
	@echo ""
	@echo "   This is a DIAGNOSTIC, not pass/fail. Real LLMs/services are"
	@echo "   nondeterministic — failures here become lessons in docs/,"
	@echo "   not build-breaking errors."
	@echo ""
	@echo "   Ctrl-C in 5 seconds to abort."
	@sleep 5
	@$(UV) run python scripts/educator_validate.py --real

.PHONY: educator-diagnostics
educator-diagnostics: ## [EDUCATOR] Comprehensive diagnostics — paste output when asking for help
	@$(UV) run python scripts/educator_diagnostics.py

.PHONY: educator-diagnostics-quick
educator-diagnostics-quick: ## [EDUCATOR] Diagnostics without network probes (fast)
	@$(UV) run python scripts/educator_diagnostics.py --quick

.PHONY: educator-backup
educator-backup: ## [EDUCATOR] Snapshot starter/, answers/, and rasa_project/ to .educator_backup/
	@rm -rf .educator_backup
	@mkdir .educator_backup
	@cp -r starter .educator_backup/starter
	@cp -r answers .educator_backup/answers
	@if [ -d rasa_project ]; then cp -r rasa_project .educator_backup/rasa_project; fi
	@echo "✓ starter/, answers/, rasa_project/ snapshotted to .educator_backup/"
