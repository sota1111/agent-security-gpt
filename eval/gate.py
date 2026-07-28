#!/usr/bin/env python3
"""Run screen→confirm and emit a machine-readable promotion decision."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from eval.run import evaluate, parse_seeds


def provenance(file: Path) -> dict[str, str]:
    resolved = file.resolve()
    return {
        "path": str(file),
        "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
    }


def passes(candidate: dict, champion: dict) -> bool:
    candidate_kpi = candidate["kpi"]
    champion_kpi = champion["kpi"]
    coverage_improved = (
        candidate_kpi["minimum_context_coverage"]
        > champion_kpi["minimum_context_coverage"]
        and candidate_kpi["mean_context_coverage"]
        >= champion_kpi["mean_context_coverage"]
    )
    diversity_improved = (
        candidate_kpi["minimum_context_coverage"]
        >= champion_kpi["minimum_context_coverage"]
        and candidate_kpi["mean_context_coverage"]
        >= champion_kpi["mean_context_coverage"]
        and candidate_kpi["mean_candidate_overlap"]
        < champion_kpi["mean_candidate_overlap"]
    )
    return candidate_kpi["deterministic_across_seeds"] and (
        coverage_improved or diversity_improved
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--champion", type=Path, default=Path("attack.py"))
    parser.add_argument("--cases", type=Path, default=Path("eval/cases.json"))
    parser.add_argument("--screen-seeds", type=parse_seeds)
    parser.add_argument("--confirm-seeds", type=parse_seeds)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    cases_document = json.loads(args.cases.read_text())
    screen_seeds = args.screen_seeds or cases_document["screen_seeds"]
    confirm_seeds = args.confirm_seeds or cases_document["confirm_seeds"]
    if set(screen_seeds) & set(confirm_seeds):
        parser.error("screen and confirm seeds must be disjoint")

    champion_screen = evaluate(args.champion.resolve(), args.cases.resolve(), screen_seeds, "screen")
    candidate_screen = evaluate(args.candidate.resolve(), args.cases.resolve(), screen_seeds, "screen")
    screen_passed = passes(candidate_screen, champion_screen)
    document = {
        "schema_version": "context-aware-attack-gate/v2",
        "provenance": {
            "incumbent_champion": provenance(args.champion),
            "candidate": provenance(args.candidate),
        },
        "criteria": {
            "deterministic": True,
            "coverage": "minimum strictly improves and mean does not regress",
            "diversity_alternative": "coverage does not regress and mean candidate overlap strictly decreases",
            "candidate_count": "diagnostic only; never a promotion criterion",
            "seed_sets_disjoint": True,
        },
        "screen": {"passed": screen_passed, "champion": champion_screen, "candidate": candidate_screen},
        "confirm": None,
        "outcome": "reject",
        "required_actions": ["revert_candidate_code", "record_result_in_docs"],
    }
    if screen_passed:
        champion_confirm = evaluate(
            args.champion.resolve(), args.cases.resolve(), confirm_seeds, "confirm"
        )
        candidate_confirm = evaluate(
            args.candidate.resolve(), args.cases.resolve(), confirm_seeds, "confirm"
        )
        confirm_passed = passes(candidate_confirm, champion_confirm)
        document["confirm"] = {
            "passed": confirm_passed,
            "champion": champion_confirm,
            "candidate": candidate_confirm,
        }
        if confirm_passed:
            document["outcome"] = "promote"
            document["required_actions"] = [
                "verify_exec_compatibility",
                "run_kaggle_proof",
                "replace_champion",
            ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"outcome": document["outcome"], "required_actions": document["required_actions"]}))


if __name__ == "__main__":
    main()
