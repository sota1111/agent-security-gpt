#!/usr/bin/env python3
"""Run screen→confirm and emit a machine-readable promotion decision."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.run import evaluate, parse_seeds


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--champion", type=Path, default=Path("attack.py"))
    parser.add_argument("--cases", type=Path, default=Path("eval/cases.json"))
    parser.add_argument("--screen-seeds", type=parse_seeds, default=[11, 29, 47])
    parser.add_argument("--confirm-seeds", type=parse_seeds, default=[101, 131, 173, 211, 257])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    champion_screen = evaluate(args.champion.resolve(), args.cases.resolve(), args.screen_seeds, "screen")
    candidate_screen = evaluate(args.candidate.resolve(), args.cases.resolve(), args.screen_seeds, "screen")
    screen_passed = (
        candidate_screen["kpi"]["deterministic_across_seeds"]
        and candidate_screen["kpi"]["minimum_case_coverage"]
        > champion_screen["kpi"]["minimum_case_coverage"]
    )
    document = {
        "schema_version": "attack-only-gate/v1",
        "screen": {"passed": screen_passed, "champion": champion_screen, "candidate": candidate_screen},
        "confirm": None,
        "outcome": "reject",
        "required_actions": ["revert_candidate_code", "record_result_in_docs"],
    }
    if screen_passed:
        champion_confirm = evaluate(
            args.champion.resolve(), args.cases.resolve(), args.confirm_seeds, "confirm"
        )
        candidate_confirm = evaluate(
            args.candidate.resolve(), args.cases.resolve(), args.confirm_seeds, "confirm"
        )
        confirm_passed = (
            candidate_confirm["kpi"]["deterministic_across_seeds"]
            and candidate_confirm["kpi"]["minimum_case_coverage"]
            > champion_confirm["kpi"]["minimum_case_coverage"]
        )
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
