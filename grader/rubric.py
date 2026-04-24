"""Rubric — the single source of truth for grading.

Public part. The private part (hidden tests that contribute 30% of the
grade) lives in a separate repo and is materialised at CI time under
tests/private/. Those tests can look at the same rubric (they check
the same axes, just with trickier inputs).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ─── layer weights ──────────────────────────────────────────────────
MECHANICAL_MAX = 30
BEHAVIOURAL_MAX = 40
REASONING_MAX = 30


@dataclass
class CheckResult:
    name: str
    passed: bool
    points_earned: float
    points_possible: float
    detail: str = ""


@dataclass
class LayerResult:
    name: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def earned(self) -> float:
        return sum(c.points_earned for c in self.checks)

    @property
    def possible(self) -> float:
        return sum(c.points_possible for c in self.checks)


@dataclass
class GradeReport:
    mechanical: LayerResult
    behavioural: LayerResult
    reasoning: LayerResult
    penalties: list[tuple[str, float]] = field(default_factory=list)

    @property
    def raw_score(self) -> float:
        return self.mechanical.earned + self.behavioural.earned + self.reasoning.earned

    @property
    def penalty_total(self) -> float:
        return sum(p for _, p in self.penalties)

    @property
    def final_score(self) -> float:
        return max(0.0, self.raw_score - self.penalty_total)

    @property
    def possible(self) -> float:
        return self.mechanical.possible + self.behavioural.possible + self.reasoning.possible


# ─── Mechanical checks (30 pts total) ──────────────────────────────
MECHANICAL_CHECKS = [
    (
        "repo_has_required_top_level_files",
        2,
        "README.md, ASSIGNMENT.md, pyproject.toml, Makefile present",
    ),
    ("pyproject_pins_sovereign_agent_0_2_0", 2, "sovereign-agent==0.2.0 in dependencies"),
    ("make_setup_green", 3, "`make setup` succeeds in a clean venv"),
    ("ruff_lint_clean", 3, "`make lint` exits 0"),
    ("ruff_format_clean", 2, "`make format-check` exits 0"),
    ("pytest_collects", 3, "`pytest --collect-only` runs without errors"),
    ("public_tests_pass", 5, "All tests in tests/public/ pass"),
    ("answers_files_exist", 2, "All five answers/ex*.md files exist"),
    ("answers_not_empty", 3, "No placeholder/TODO text remains in answer bodies"),
    ("all_scenarios_have_integrity_check", 5, "Penalty: -10 if any scenario lacks one"),
]


# ─── Behavioural checks (40 pts total) ─────────────────────────────
BEHAVIOURAL_CHECKS = [
    ("ex5_scenario_runs_end_to_end", 6, "`make ex5` exits 0; flyer.md written"),
    ("ex5_dataflow_catches_planted_fabrication", 6, "Planted £9999 fabrication is flagged"),
    ("ex5_dataflow_accepts_legitimate_flyer", 3, "Unmodified flyer passes"),
    ("ex6_structured_half_accepts_valid_booking", 4, "Party=6, deposit=£200 → approved"),
    ("ex6_rejects_oversize_party", 3, "Party=12 → rejected with reason"),
    ("ex6_rejects_high_deposit", 3, "Deposit=£500 → rejected with reason"),
    ("ex7_round_trip_completes", 6, "Rejection → re-research → approval"),
    ("ex7_no_multiple_handoff_files", 2, "At most one handoff file visible at a time"),
    ("ex8_text_mode_at_least_3_turns", 4, "Conversation reaches ≥3 turns"),
    ("ex8_trace_has_utterance_events", 3, "voice.utterance_in and _out both present"),
]


# ─── Reasoning checks (30 pts total — CI only) ─────────────────────
REASONING_CHECKS = [
    ("q1_grounded_in_ex7_logs", 9, "Q1 cites real subgoal with assigned_half"),
    ("q2_integrity_scenario_specific", 9, "Q2 describes a reproducible case"),
    ("q3_names_exactly_one_primitive", 6, "Q3 names one primitive, one failure"),
    ("word_counts_within_bounds", 3, "Each answer within 100-400 words"),
    ("llm_judge_groundedness_score", 3, "Different-model judge gives ≥0.5"),
]


# Single source of truth for max totals — the grader reads these.
def mechanical_max() -> int:
    return sum(pts for _, pts, _ in MECHANICAL_CHECKS)


def behavioural_max() -> int:
    return sum(pts for _, pts, _ in BEHAVIOURAL_CHECKS)


def reasoning_max() -> int:
    return sum(pts for _, pts, _ in REASONING_CHECKS)


# Sanity at import time — catches refactoring drift.
assert mechanical_max() == MECHANICAL_MAX, (mechanical_max(), MECHANICAL_MAX)
assert behavioural_max() == BEHAVIOURAL_MAX, (behavioural_max(), BEHAVIOURAL_MAX)
assert reasoning_max() == REASONING_MAX, (reasoning_max(), REASONING_MAX)


__all__ = [
    "BEHAVIOURAL_CHECKS",
    "BEHAVIOURAL_MAX",
    "CheckResult",
    "GradeReport",
    "LayerResult",
    "MECHANICAL_CHECKS",
    "MECHANICAL_MAX",
    "REASONING_CHECKS",
    "REASONING_MAX",
    "behavioural_max",
    "mechanical_max",
    "reasoning_max",
]
