"""Ex6 probe-and-run — the didactic tier-2 entrypoint.

This script is what `make ex6-real` does:

  1. Probe http://localhost:5005/version
  2. If Rasa answers → run the Ex6 scenario against it
  3. If Rasa doesn't answer → print an ASCII block that tells the student
     exactly which two commands to run in which terminals, and why

Why probe-then-run instead of auto-spawn?

  Ex6 is where students first meet a multi-process agent system. The
  loop half is a Python process; the structured half (Rasa) is TWO
  separate processes (rasa server + action server) that talk over HTTP.
  That's not a quirk of this homework — it's how production agent
  systems are always structured. Teaching students to see the processes,
  watch their logs in separate terminals, and curl localhost:5005 is
  the whole point of Ex6.

  If the student didn't start Rasa yet, we could auto-spawn it (`make
  ex6-auto` does exactly that). But auto-spawn hides the lesson. So
  `ex6-real` refuses to guess — it tells you "Rasa isn't up, here's how
  to start it" and exits. Students who repeatedly see the three-terminal
  layout internalise why it's structured that way.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

REPO = Path(__file__).resolve().parent.parent
RASA_URL = "http://localhost:5005"
ACTIONS_URL = "http://localhost:5055"


class _C:
    _on = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

    @classmethod
    def _w(cls, code: str, s: str) -> str:
        return f"\033[{code}m{s}\033[0m" if cls._on else s

    @classmethod
    def g(cls, s: str) -> str:
        return cls._w("32", s)

    @classmethod
    def r(cls, s: str) -> str:
        return cls._w("31", s)

    @classmethod
    def y(cls, s: str) -> str:
        return cls._w("33", s)

    @classmethod
    def d(cls, s: str) -> str:
        return cls._w("2", s)

    @classmethod
    def b(cls, s: str) -> str:
        return cls._w("1", s)

    @classmethod
    def cyan(cls, s: str) -> str:
        return cls._w("36", s)


def probe(url: str, timeout: float = 3.0) -> tuple[bool, str]:
    """Return (is_up, detail)."""
    try:
        with urllib_request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")[:120].strip()
            return True, f"HTTP {resp.status} — {body}"
    except HTTPError as e:
        return True, f"HTTP {e.code} (reachable but not 200)"
    except URLError as e:
        return False, f"connection failed: {e}"
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def print_bootstrap_message(rasa_detail: str, actions_detail: str) -> None:
    """Pedagogical message when Rasa isn't up."""
    print()
    print(_C.y("━" * 72))
    print(_C.b("  Ex6 — Rasa isn't running yet"))
    print(_C.y("━" * 72))
    print()
    print(f"  Probed {_C.cyan(RASA_URL + '/version')}")
    print(f"    {_C.r('✗')} {rasa_detail}")
    print()
    print(f"  Probed {_C.cyan(ACTIONS_URL + '/health')}")
    print(f"    {_C.r('✗')} {actions_detail}")
    print()
    print(_C.b("  You need TWO extra terminals open before this scenario can run."))
    print()
    print("    " + _C.cyan("Terminal 1") + _C.d(" (action server):   ") + _C.b("make rasa-actions"))
    print(
        "    "
        + _C.cyan("Terminal 2")
        + _C.d(" (rasa server):     ")
        + _C.b("make rasa-serve")
        + _C.d("   (trains if needed)")
    )
    print("    " + _C.cyan("Terminal 3") + _C.d(" (this one):        ") + _C.b("make ex6-real"))
    print()
    print(_C.b("  What to expect:"))
    print(
        "    • Terminal 1 prints "
        + _C.d("'Action endpoint is up and running'")
        + " and then waits."
    )
    print(
        "    • Terminal 2 prints training progress for ~30-60s, then "
        + _C.d("'Rasa server is up and running'")
        + "."
    )
    print("    • Come back here and re-run " + _C.cyan("make ex6-real") + ".")
    print()
    print(_C.b("  First time? Install rasa-pro:"))
    print("    Rasa is an opt-in dep (~400MB). If " + _C.cyan("make rasa-actions") + " fails with")
    print('    "rasa not found" or similar, run:')
    print()
    print("      " + _C.cyan("make setup-rasa"))
    print()
    print("    (Takes 1-2 minutes. One-time.)")
    print()
    print(_C.b("  Why two terminals (not one auto-spawned process)?"))
    print("    Real agent systems coordinate across process boundaries. Watching the")
    print("    Rasa server's logs in its own terminal is the fastest way to debug")
    print("    dialog flow issues. " + _C.cyan("docs/rasa-setup.md") + " has the full explanation.")
    print()
    print(_C.b("  In a hurry? ") + "There's an auto-spawn shortcut: " + _C.cyan("make ex6-auto"))
    print(_C.d("    (Spawns both Rasa processes, runs the scenario, tears them down."))
    print(_C.d("    Fine for quick demos but hides what the three-terminal version"))
    print(_C.d("    teaches. Use ex6-real while you're learning.)"))
    print()
    print(_C.b("  Don't have a Rasa Pro license yet?"))
    print("    You can progress on Ex6 using the mock server instead: " + _C.cyan("make ex6"))
    print(
        "    The mock matches Rasa's HTTP shape so your "
        + _C.cyan("normalise_booking_payload")
        + " and"
    )
    print("    structured_half code validate against it. License signup instructions:")
    print("    " + _C.cyan("docs/rasa-setup.md") + " → 'Getting a Rasa Pro developer license'")
    print()
    print(_C.y("━" * 72))
    print()


def _print_notimpl_bootstrap(tail: str) -> None:
    """Friendly message when the scenario runs but hits a TODO stub."""
    print()
    print(_C.y("━" * 72))
    print(_C.b("  Ex6 — Rasa is up, but YOUR code isn't complete yet"))
    print(_C.y("━" * 72))
    print()
    print("  The two Rasa services are reachable. Your scenario started, but")
    print("  hit a NotImplementedError in one of your starter files.")
    print()
    print(_C.b("  The stack trace above tells you which file + line."))
    print()
    print("  Most likely candidates (implement in order):")
    print()
    print("    1. " + _C.cyan("starter/rasa_half/validator.py"))
    print("       → implement " + _C.b("normalise_booking_payload()"))
    print()
    print("    2. " + _C.cyan("starter/rasa_half/structured_half.py"))
    print("       → implement " + _C.b("RasaStructuredHalf.run()"))
    print()
    print("  When both are done, re-run " + _C.cyan("make ex6-real") + ".")
    print()
    print("  Need the reference pattern? sovereign-agent ships one at")
    print("    " + _C.cyan("sovereign-agent/examples/pub_booking/run.py"))
    print()
    print(_C.y("━" * 72))
    print()


def main() -> int:
    # Probe both services. We want to tell the student precisely what's
    # up and what's not so they can fix the exact problem.
    rasa_up, rasa_detail = probe(f"{RASA_URL}/version")
    actions_up, actions_detail = probe(f"{ACTIONS_URL}/health")

    if rasa_up and actions_up:
        print()
        print(_C.g("✓") + f" Rasa is up at {RASA_URL}")
        print(_C.d(f"    {rasa_detail}"))
        print(_C.g("✓") + f" Action server is up at {ACTIONS_URL}")
        print(_C.d(f"    {actions_detail}"))
        print()
        print(_C.b("▶ Running Ex6 scenario..."))
        print()
        # Capture output so we can detect NotImplementedError and turn
        # it into a friendly message. Students staring at a raw stack
        # trace don't realise the fix is to finish their TODOs.
        proc = subprocess.run(
            [sys.executable, "-m", "starter.rasa_half.run", "--real"],
            cwd=REPO,
            env={**os.environ},
            capture_output=True,
            text=True,
        )
        # Always print the subprocess output verbatim first so students
        # see everything their scenario did.
        if proc.stdout:
            print(proc.stdout, end="")
        if proc.stderr:
            print(proc.stderr, end="", file=sys.stderr)

        # If a NotImplementedError came out of the scenario, wrap with
        # pedagogical framing.
        combined = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0 and "NotImplementedError" in combined:
            tail_lines = [ln for ln in combined.splitlines() if "NotImplementedError" in ln]
            _print_notimpl_bootstrap("\n".join(tail_lines))

        return proc.returncode

    # At least one side is down → pedagogical message, exit 1
    print_bootstrap_message(rasa_detail, actions_detail)
    return 1


if __name__ == "__main__":
    sys.exit(main())
