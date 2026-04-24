"""CI-side authoritative grader.

Run by `.github/workflows/grade.yml` at the submission deadline.

Depends on tests/private/ being materialised from the grader repo
(see grade.yml for the checkout-and-copy step).

Differences from check_submit.py (the local advisory grader):
  * Runs private tests as well as public.
  * Runs dataflow_probe.py — plants fabrications into the student's
    Ex5 run and confirms their dataflow check catches each.
  * Runs the LLM-as-judge for the reasoning layer. The judge MUST be
    a DIFFERENT model than anything the student used (see B6 appendix
    of the design doc).
  * Uploads a JSON report to the grading dashboard via
    STUDENT_GITHUB_USERNAME from the student's .env.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from grader.check_submit import (
    render_markdown,
    run_behavioural,
    run_mechanical,
    run_reasoning,
)
from grader.rubric import CheckResult, GradeReport, LayerResult


def run_private_tests(layer: LayerResult) -> None:
    """Extend the behavioural layer with tests/private/ results.

    Private tests probe subtler failure modes (e.g. parallel-safe flags,
    idempotence of the dataflow check, state transitions on cancellation).
    Scored as 1 point per test in the private layer.

    If tests/private/ is empty (we're running locally or the materialise
    step failed), this is a no-op.
    """
    import subprocess

    private_dir = Path("tests/private")
    if not private_dir.exists() or not any(private_dir.glob("test_*.py")):
        layer.checks.append(
            CheckResult(
                name="private_tests_materialised",
                passed=False,
                points_earned=0,
                points_possible=10,
                detail="tests/private/ empty — running as if local",
            )
        )
        return

    rc = subprocess.run(
        ["uv", "run", "pytest", "tests/private/", "-q", "--tb=short"],
        capture_output=True,
        text=True,
    )
    layer.checks.append(
        CheckResult(
            name="private_tests_pass",
            passed=rc.returncode == 0,
            points_earned=10 if rc.returncode == 0 else 0,
            points_possible=10,
            detail=f"rc={rc.returncode}",
        )
    )


def run_dataflow_probe(layer: LayerResult) -> None:
    """Plant fabrications into Ex5, confirm student's check catches each."""
    from grader.dataflow_probe import probe_ex5

    result = probe_ex5()
    layer.checks.append(
        CheckResult(
            name="dataflow_catches_planted_fabrications",
            passed=result.all_caught,
            points_earned=result.score,
            points_possible=result.max_score,
            detail=result.detail,
        )
    )


def run_llm_judge(layer: LayerResult) -> None:
    """LLM-as-judge for reasoning answers.

    MUST use a model different from what the student is likely to have
    run (the student defaults are Qwen3 + Llama-3.3). We use GPT-4o
    or Claude as the judge; see the B6 appendix.
    """
    # TODO in the grader repo: implement the judge. For the homework
    # repo itself we ship a stub that reports "scored by CI".
    layer.checks.append(
        CheckResult(
            name="llm_judge_scored",
            passed=False,
            points_earned=0,
            points_possible=9,
            detail="LLM judge runs in the grader repo, not here.",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--student-repo", default=".", help="Path to the student's repo")
    parser.add_argument("--output", type=Path, help="Write JSON report here")
    args = parser.parse_args()

    if args.student_repo != ".":
        os.chdir(args.student_repo)

    mechanical = run_mechanical(None)
    behavioural = run_behavioural(None)
    reasoning = run_reasoning(None)

    # Augment with CI-only checks.
    run_private_tests(behavioural)
    run_dataflow_probe(behavioural)
    run_llm_judge(reasoning)

    report = GradeReport(
        mechanical=mechanical,
        behavioural=behavioural,
        reasoning=reasoning,
    )
    for c in mechanical.checks:
        if c.name == "all_scenarios_have_integrity_check" and not c.passed:
            report.penalties.append(("missing_integrity_check", 10.0))

    if args.output:
        import json

        args.output.write_text(
            json.dumps(
                {
                    "raw_score": report.raw_score,
                    "final_score": report.final_score,
                    "possible": report.possible,
                },
                indent=2,
            )
        )

    print(render_markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
