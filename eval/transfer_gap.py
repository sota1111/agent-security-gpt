#!/usr/bin/env python3
"""Locate the first post-submission scoring boundary not reached by a champion."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
from typing import Any


BOUNDARIES = (
    "artifact_identity",
    "sdk_load",
    "agent_trajectory",
    "predicate",
    "breach",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tool_decisions(trial: dict[str, Any]) -> list[dict[str, Any]]:
    events = trial.get("evidence", {}).get("agent_events", [])
    return [
        event
        for event in events
        if (event.get("decision") or {}).get("type") == "tool_call"
    ]


def boundary_reach(trial: dict[str, Any], *, artifact_matches: bool) -> dict[str, bool]:
    """Project a redacted SDK trial onto the ordered scoring boundaries."""
    evaluation_error = trial.get("evidence", {}).get("evaluation_error")
    return {
        "artifact_identity": artifact_matches,
        "sdk_load": artifact_matches and evaluation_error is None,
        "agent_trajectory": artifact_matches
        and evaluation_error is None
        and bool(_tool_decisions(trial)),
        "predicate": bool(trial.get("objective_achieved")),
        "breach": bool(trial.get("breach_success")),
    }


def _first_unreached(reach: dict[str, bool]) -> str | None:
    return next((name for name in BOUNDARIES if not reach[name]), None)


def _confirm_trials(payload: dict[str, Any], strategy: str) -> list[dict[str, Any]]:
    return [
        trial
        for trial in payload["confirm"]["trials"]
        if trial["strategy"] == strategy
    ]


def build_transfer_gap(
    *,
    champion: Path,
    submission_record: Path,
    screen_record: Path,
    confirm_record: Path,
    strategy: str = "protocol-only-context",
) -> dict[str, Any]:
    """Build a deterministic, secret-free boundary report from preserved SDK trials."""
    submission = json.loads(submission_record.read_text(encoding="utf-8"))
    screen = json.loads(screen_record.read_text(encoding="utf-8"))
    confirm = json.loads(confirm_record.read_text(encoding="utf-8"))
    champion_digest = sha256(champion)
    submitted_digest = submission["selected_artifact"]["sha256"]
    screen_digest = screen["strategies"][strategy]["sha256"]
    confirm_digest = confirm["fingerprint"]["candidate"]["sha256"]
    artifact_matches = len(
        {champion_digest, submitted_digest, screen_digest, confirm_digest}
    ) == 1
    if not artifact_matches:
        raise ValueError("champion, submission, screen, and confirm artifacts differ")

    scenarios = [
        ("matched_screen", screen["trials"]),
        ("independent_confirm", _confirm_trials(confirm, strategy)),
    ]
    trials: list[dict[str, Any]] = []
    for scenario, source_trials in scenarios:
        for trial in source_trials:
            if trial["strategy"] != strategy:
                continue
            reach = boundary_reach(trial, artifact_matches=artifact_matches)
            trials.append(
                {
                    "scenario": scenario,
                    "seed": trial["seed"],
                    "boundary_reach": reach,
                    "first_unreached_boundary": _first_unreached(reach),
                    "failure_stage": trial["failure_stage"],
                    "evidence_counts": {
                        "agent_events": len(
                            trial.get("evidence", {}).get("agent_events", [])
                        ),
                        "tool_decisions": len(_tool_decisions(trial)),
                        "guardrail_events": len(
                            trial.get("evidence", {}).get("guardrail_events", [])
                        ),
                        "validated_findings": len(
                            trial.get("evidence", {}).get("validated_findings", [])
                        ),
                    },
                }
            )
    if len({trial["scenario"] for trial in trials}) < 2:
        raise ValueError("at least two SDK scenarios are required")
    if len({trial["seed"] for trial in trials}) < 2:
        raise ValueError("at least two independent seeds are required")

    boundary_summary = []
    for boundary in BOUNDARIES:
        reached = sum(trial["boundary_reach"][boundary] for trial in trials)
        boundary_summary.append(
            {
                "boundary": boundary,
                "reached": reached,
                "trials": len(trials),
                "reach_rate": reached / len(trials),
            }
        )
    first_drop = next(
        item["boundary"]
        for item in boundary_summary
        if item["reached"] < item["trials"]
    )
    seeds_by_failure = sorted(
        trial["seed"]
        for trial in trials
        if trial["first_unreached_boundary"] == first_drop
    )

    return {
        "schema": "post-submission-transfer-gap/v1",
        "issue": "SOT-2269",
        "fingerprint": {
            "champion_path": str(champion),
            "champion_sha256": champion_digest,
            "submitted_artifact_sha256": submitted_digest,
            "submission_fingerprint": submission["submission"]["artifact_fingerprint"],
            "submission_ref": submission["submission"]["existing_submission_ref"],
            "public_score": submission["submission"]["existing_public_score"],
            "screen_record_sha256": sha256(screen_record),
            "confirm_record_sha256": sha256(confirm_record),
            "sdk_version_recorded": screen["fingerprint"]["sdk_version"],
            "sdk_version_replay": importlib.metadata.version("aicomp-sdk"),
            "agent": screen["fingerprint"]["agent_selection"],
            "model_id": screen["fingerprint"]["model_id"],
            "budget_s": screen["fingerprint"]["budget_s"],
            "environment": screen["fingerprint"]["environment"],
            "guardrail": screen["fingerprint"]["guardrail"],
            "scoring_path": screen["fingerprint"]["scoring_path"],
            "temperature": screen["fingerprint"]["temperature"],
            "sampling": screen["fingerprint"]["sampling"],
            "scenario_seeds": {
                scenario: [trial["seed"] for trial in trials if trial["scenario"] == scenario]
                for scenario, _ in scenarios
            },
        },
        "boundary_order": list(BOUNDARIES),
        "definitions": {
            "artifact_identity": "champion, promoted candidate, and submitted payload hashes match",
            "sdk_load": "official SDK evaluation completed without a recorded execution error",
            "agent_trajectory": "the SDK debug trace contains at least one parsed tool decision",
            "predicate": "eval_attack retained a canonical predicate-bearing finding",
            "breach": "is_breach accepted a retained finding",
        },
        "boundary_summary": boundary_summary,
        "trials": trials,
        "diagnosis": {
            "first_observed_unreached_boundary": first_drop,
            "failure_seeds": seeds_by_failure,
            "public_score_explanation": (
                "The submitted bytes reach SDK loading and tool trajectories locally, but predicate "
                "reach is seed-dependent (4/6). A hidden scenario distribution concentrated on the "
                "same predicate-miss mode can therefore produce 0.000; hidden grader equivalence is "
                "not claimed."
            ),
        },
        "next_screen_axes": [
            {
                "id": "predicate-reach-across-scenarios",
                "evidence": {"boundary": first_drop, "seeds": seeds_by_failure},
                "screen": "vary public SDK scenarios on matched seeds and require predicate reach without breach regression",
                "implemented": False,
            },
            {
                "id": "tool-result-to-scored-sink-continuation",
                "evidence": {
                    "failure_stage": "tool_execution_without_objective",
                    "seeds": seeds_by_failure,
                },
                "screen": "retain successful source-result provenance through the scored sink action",
                "implemented": False,
            },
            {
                "id": "seed-robust-action-path",
                "evidence": {
                    "successful_seeds": sorted(
                        trial["seed"] for trial in trials if trial["boundary_reach"]["breach"]
                    ),
                    "failed_seeds": seeds_by_failure,
                },
                "screen": "reduce trajectory branching so the same predicate-bearing path completes across independent seeds",
                "implemented": False,
            },
        ],
        "promotion_gate": {
            "candidate_changed": False,
            "status": "N/A",
            "reason": "diagnostic-only issue; SOT-2270 owns matched screen and independent-seed confirm",
        },
        "redaction": {
            "credentials_read": False,
            "protected_payloads_read": False,
            "fixture_secret_values_persisted": False,
            "trial_payloads_copied": False,
            "stored_evidence": "counts, booleans, public model/SDK configuration, and hashes only",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--champion", type=Path, default=Path("attack.py"))
    parser.add_argument(
        "--submission-record", type=Path,
        default=Path("docs/results/sot-2250-kaggle-submission.json")
    )
    parser.add_argument(
        "--screen-record", type=Path,
        default=Path("docs/results/sot-2248-scenario-generalized-candidate-screen.json")
    )
    parser.add_argument(
        "--confirm-record", type=Path,
        default=Path("docs/results/sot-2249-scenario-generalized-candidate-confirm.json")
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("docs/results/sot-2269-post-submission-transfer-gap.json")
    )
    args = parser.parse_args(argv)
    payload = build_transfer_gap(
        champion=args.champion,
        submission_record=args.submission_record,
        screen_record=args.screen_record,
        confirm_record=args.confirm_record,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload["diagnosis"], sort_keys=True))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
