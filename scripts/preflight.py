"""Preflight checks — scoped to this homework repo.

Runs as `make verify` step 1 (step 2 is nebius_smoke.py). Exits 0 if all
checks pass; 1 otherwise with a line per failure pointing at the right doc.

Modelled on sovereign-agent's own preflight but adapted to the homework's
surface area.
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


# ── colours (auto-disabled when not a TTY) ──────────────────────────
_TTY = sys.stdout.isatty()
GREEN = "\033[92m" if _TTY else ""
YELLOW = "\033[93m" if _TTY else ""
RED = "\033[91m" if _TTY else ""
BLUE = "\033[94m" if _TTY else ""
BOLD = "\033[1m" if _TTY else ""
DIM = "\033[2m" if _TTY else ""
RESET = "\033[0m" if _TTY else ""


def ok(msg: str) -> None:
    print(f"{GREEN}  ✓  {msg}{RESET}")


def warn(msg: str) -> None:
    print(f"{YELLOW}  ⚠  {msg}{RESET}")


def fail(msg: str) -> None:
    print(f"{RED}  ✗  {msg}{RESET}")


def hint(msg: str) -> None:
    print(f"{DIM}       → {msg}{RESET}")


def section(title: str) -> None:
    print(f"\n{BLUE}{BOLD}  {title}{RESET}")
    print(f"{BLUE}{BOLD}{'─' * 58}{RESET}")


# ── .env loader ─────────────────────────────────────────────────────


def load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if v and v[0] in "\"'" and v[0] == v[-1]:
            v = v[1:-1]
        result[k] = v
    return result


# ── individual checks ───────────────────────────────────────────────


def check_python() -> int:
    v = sys.version_info
    if (v.major, v.minor) == (3, 12):
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
        return 0
    fail(f"Python {v.major}.{v.minor} — homework needs 3.12 exactly")
    hint("See docs/setup-<your-os>.md for Python installation steps.")
    return 1


def check_uv() -> int:
    if shutil.which("uv") is None:
        fail("uv not on PATH")
        hint("See SETUP.md §3 for three install options.")
        return 1
    try:
        r = subprocess.run(["uv", "--version"], capture_output=True, text=True, timeout=5)
        ok(f"uv available — {r.stdout.strip()}")
        return 0
    except Exception as e:  # noqa: BLE001
        fail(f"uv present but broken: {e}")
        return 1


def check_uv_lock() -> int:
    if (REPO_ROOT / "uv.lock").exists():
        ok("uv.lock present (reproducible installs)")
        return 0
    warn("uv.lock missing — run `make setup` or `uv sync` to create it")
    return 0  # soft


def check_dotenv() -> tuple[int, dict[str, str]]:
    env_path = REPO_ROOT / ".env"
    example_path = REPO_ROOT / ".env.example"
    if not env_path.exists():
        fail(".env does not exist")
        if example_path.exists():
            hint(f"Copy the template: cp {example_path.name} .env")
            hint("Then edit .env and set NEBIUS_KEY to your real key.")
        return 1, {}
    contents = load_dotenv(env_path)
    ok(f".env present ({len(contents)} key(s) defined)")
    return 0, contents


def _is_placeholder(value: str) -> bool:
    if not value:
        return True
    v = value.strip().lower()
    return any(
        tok in v
        for tok in ["your-nebius-key", "your-key", "replace-me", "changeme", "todo", "xxxx"]
    )


def _mask(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}…{value[-4:]}"


def check_nebius_key(env: dict[str, str]) -> int:
    key_var = env.get("SOVEREIGN_AGENT_LLM_API_KEY_ENV", "NEBIUS_KEY")
    value = env.get(key_var, os.environ.get(key_var, "")).strip()
    if not value:
        fail(f"{key_var} is not set in .env (or the shell)")
        hint("Get one at https://tokenfactory.nebius.com (see docs/nebius-signup.md)")
        return 1
    if _is_placeholder(value):
        fail(f"{key_var} is still a placeholder value ({_mask(value)})")
        hint("Edit .env and paste your real key.")
        return 1
    ok(f"{key_var} set ({_mask(value)})")
    # Export into the process environment for downstream scripts.
    os.environ[key_var] = value
    return 0


def check_sovereign_agent() -> int:
    try:
        sa = importlib.import_module("sovereign_agent")
    except ImportError as e:
        fail(f"sovereign_agent not importable: {e}")
        hint("Run: uv sync --all-groups")
        return 1
    version = getattr(sa, "__version__", "unknown")
    if version != "0.2.0":
        warn(f"sovereign-agent version is {version}, homework pinned to 0.2.0")
    ok(f"sovereign-agent imports (v{version})")
    return 0


def check_starter_imports() -> int:
    """Every starter package must be importable — a SyntaxError here means
    you can't proceed even on the offline exercises."""
    errors = 0
    for mod in [
        "starter.edinburgh_research",
        "starter.edinburgh_research.tools",
        "starter.edinburgh_research.integrity",
        "starter.rasa_half.structured_half",
        "starter.rasa_half.validator",
        "starter.handoff_bridge.bridge",
        "starter.voice_pipeline.manager_persona",
        "starter.voice_pipeline.voice_loop",
    ]:
        try:
            importlib.import_module(mod)
            ok(f"{mod} imports")
        except Exception as e:  # noqa: BLE001
            fail(f"{mod} fails to import: {type(e).__name__}: {e}")
            errors += 1
    return errors


def check_pytest_collects() -> int:
    r = subprocess.run(
        ["uv", "run", "pytest", "--collect-only", "-q"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if r.returncode == 0:
        ok("pytest collects cleanly")
        return 0
    fail("pytest collection failed")
    for line in (r.stderr + r.stdout).splitlines()[-8:]:
        hint(line)
    return 1


# ── main ────────────────────────────────────────────────────────────


def main() -> int:
    sys.path.insert(0, str(REPO_ROOT))

    print(f"\n{BOLD}{BLUE}  homework-pub-booking — preflight{RESET}")

    errors = 0

    section("Python and uv")
    errors += check_python()
    errors += check_uv()
    errors += check_uv_lock()

    section(".env and API keys")
    env_err, dotenv_contents = check_dotenv()
    errors += env_err
    for k, v in dotenv_contents.items():
        os.environ.setdefault(k, v)
    errors += check_nebius_key(dotenv_contents)

    section("sovereign-agent and starter scaffolds")
    errors += check_sovereign_agent()
    errors += check_starter_imports()

    section("pytest")
    errors += check_pytest_collects()

    print()
    if errors == 0:
        print(f"{GREEN}{BOLD}  ✓  Preflight OK — now running nebius_smoke.py{RESET}")
        return 0
    noun = "error" if errors == 1 else "errors"
    print(f"{RED}{BOLD}  ✗  Preflight found {errors} {noun} — see above.{RESET}")
    hint("docs/troubleshooting.md is organised by error message.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
