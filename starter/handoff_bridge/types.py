"""Shared Ex7 bridge result types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sovereign_agent.halves import HalfResult

BridgeOutcome = Literal["completed", "failed", "max_rounds_exceeded"]


@dataclass
class BridgeResult:
    outcome: BridgeOutcome
    rounds: int
    final_half_result: HalfResult | None
    summary: str


__all__ = [
    "BridgeOutcome",
    "BridgeResult",
]