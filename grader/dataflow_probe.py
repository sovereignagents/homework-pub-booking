"""Dataflow probe — CI-side check that the student's integrity check
catches fabrications.

The probe runs the student's Ex5 scenario, then rewrites the produced
flyer.md with a known fabrication (a value that no tool ever returned)
and re-runs their verify_dataflow(). A correct implementation reports
the fabrication; a too-lenient one passes it.

Three plants per run, each worth 2 points.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass


@dataclass
class ProbeResult:
    all_caught: bool
    score: int
    max_score: int
    detail: str


FABRICATIONS = [
    ("£9999", "obvious-price plant — not in any venue+catering combo"),
    ("Castle Royal Grand Inn", "non-existent venue name"),
    ("scorching 35C", "impossible Edinburgh temperature"),
]


def probe_ex5() -> ProbeResult:
    """Plant each fabrication separately, run verify_dataflow, confirm caught.

    Returns a ProbeResult. If student's code crashes, all three plants
    are reported as NOT caught (conservative — we don't want flaky code
    to silently pass).
    """
    # Import the student's modules. If they fail to import, we can't probe.
    try:
        from starter.edinburgh_research.integrity import (
            verify_dataflow,
        )
    except Exception as exc:  # noqa: BLE001
        return ProbeResult(
            all_caught=False,
            score=0,
            max_score=6,
            detail=f"student's integrity.py failed to import: {exc}",
        )

    # First run the student's scenario to populate _TOOL_CALL_LOG with legit data.
    rc = subprocess.run(
        [sys.executable, "-m", "starter.edinburgh_research.run"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if rc.returncode != 0:
        return ProbeResult(
            all_caught=False,
            score=0,
            max_score=6,
            detail=f"make ex5 failed rc={rc.returncode}",
        )

    caught = 0
    details: list[str] = []
    for bad_value, description in FABRICATIONS:
        # Build a flyer string with the fabrication injected.
        fake_flyer = (
            f"# Booking flyer\n\n"
            f"Venue: Haymarket Tap\n"
            f"Party of 6 at 19:30, 2026-04-25.\n"
            f"Weather: cloudy, 12C.\n"
            f"Total: {bad_value}.\n"  # <- the plant
            f"Deposit: £0.\n"
        )
        result = verify_dataflow(fake_flyer)
        if not result.ok and any(bad_value.lower() in uf.lower() for uf in result.unverified_facts):
            caught += 1
            details.append(f"✓ caught {description}: {bad_value}")
        else:
            details.append(f"✗ missed {description}: {bad_value}")

    score = caught * 2  # 2 pts per plant
    return ProbeResult(
        all_caught=caught == len(FABRICATIONS),
        score=score,
        max_score=len(FABRICATIONS) * 2,
        detail="; ".join(details),
    )


if __name__ == "__main__":
    r = probe_ex5()
    print(r)
    sys.exit(0 if r.all_caught else 1)
