"""Live 1-token Nebius round-trip. Confirms the key + endpoint work.

This is step 2 of `make verify`. Cost: <£0.001.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

_TTY = sys.stdout.isatty()
GREEN = "\033[92m" if _TTY else ""
RED = "\033[91m" if _TTY else ""
YELLOW = "\033[93m" if _TTY else ""
BOLD = "\033[1m" if _TTY else ""
DIM = "\033[2m" if _TTY else ""
RESET = "\033[0m" if _TTY else ""


def _load_dotenv() -> None:
    path = REPO_ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if v and v[0] in "\"'" and v[0] == v[-1]:
            v = v[1:-1]
        os.environ.setdefault(k, v)


async def probe() -> int:
    _load_dotenv()

    key_var = os.environ.get("SOVEREIGN_AGENT_LLM_API_KEY_ENV", "NEBIUS_KEY")
    key = os.environ.get(key_var, "")
    if not key:
        print(f"{RED}  ✗  {key_var} not set. Re-run `make verify` after fixing .env.{RESET}")
        return 1

    base_url = os.environ.get(
        "SOVEREIGN_AGENT_LLM_BASE_URL",
        "https://api.tokenfactory.nebius.com/v1/",
    )
    # Cheapest small model on Nebius — used only for the probe.
    model = "google/gemma-3-27b-it-fast"

    try:
        from openai import AsyncOpenAI
    except ImportError:
        print(f"{RED}  ✗  openai package not installed. Run `make setup`.{RESET}")
        return 1

    client = AsyncOpenAI(api_key=key, base_url=base_url)
    try:
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Reply with just: OK"}],
                max_tokens=3,
                temperature=0,
            ),
            timeout=20.0,
        )
    except TimeoutError:
        print(f"{RED}  ✗  LLM endpoint timed out after 20s.{RESET}")
        print(f"{DIM}       → Check your network. Corporate proxies need HTTPS_PROXY set.{RESET}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"{RED}  ✗  LLM call failed: {type(exc).__name__}: {exc}{RESET}")
        if "401" in str(exc) or "Unauthorized" in str(exc).lower():
            print(f"{DIM}       → Your NEBIUS_KEY is invalid or expired. Edit .env.{RESET}")
        elif "404" in str(exc):
            print(f"{DIM}       → Endpoint URL wrong. Check SOVEREIGN_AGENT_LLM_BASE_URL.{RESET}")
        else:
            print(f"{DIM}       → See docs/troubleshooting.md.{RESET}")
        return 1

    content = (resp.choices[0].message.content or "").strip()
    if not content:
        print(
            f"{YELLOW}  ⚠  LLM returned empty content but didn't error. Probably rate-limited.{RESET}"
        )
        return 0
    print(f"{GREEN}  ✓  LLM reachable — {base_url}{RESET}")
    print(f"{DIM}       model: {model}, reply: {content!r}{RESET}")
    print()
    print(f"{GREEN}{BOLD}  ✓  All checks passed — ready to start the homework!{RESET}")
    print()
    print("  Next steps:")
    print(f"    {GREEN}make ex5{RESET}        run Ex5 offline")
    print(f"    {GREEN}make ex5-real{RESET}   run Ex5 against the real LLM")
    print(f"    {GREEN}make test{RESET}       run the public test suite")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(probe()))
