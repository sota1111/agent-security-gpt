#!/usr/bin/env python3
"""Reproduce redacted oracle-drift evidence from three immutable artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


INPUT_CONTRACT = {
    "transfer_gap": {
        "path": "docs/results/sot-2269-post-submission-transfer-gap.json",
        "sha256": "ddd01bba1fa5c1e91fd4548e10b7ca3b17848f22f96dbc87f5a1a5225c1f8be5",
        "issue": "SOT-2269",
        "schema": "post-submission-transfer-gap/v1",
    },
    "submission": {
        "path": "docs/results/sot-2250-kaggle-submission.json",
        "sha256": "c902e9dc20fb5047ce096fbb8ed76d12916a84bbe42624bc6bb3caa397cd8acd",
        "issue": "SOT-2250",
        "schema": "kaggle-submission-proof/v1",
    },
    "handoff": {
        "path": "docs/results/sot-2271-submission-handoff.json",
        "sha256": "d369c6d8fdaf12992dc319271e0b8c6bc609512cd314a98c3d8eeae45f90a98d",
        "issue": "SOT-2271",
        "schema": "kaggle-submission-handoff/v1",
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_pinned(root: Path, name: str) -> dict[str, Any]:
    contract = INPUT_CONTRACT[name]
    path = root / contract["path"]
    actual_sha = sha256(path)
    if actual_sha != contract["sha256"]:
        raise ValueError(f"{name} SHA mismatch: expected {contract['sha256']}, got {actual_sha}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("issue") != contract["issue"] or payload.get("schema") != contract["schema"]:
        raise ValueError(f"{name} identity mismatch")
    return payload


def build_oracle_drift_anchor(root: Path) -> dict[str, Any]:
    """Build evidence using only persisted aggregates, booleans, IDs, and hashes."""
    gap = _load_pinned(root, "transfer_gap")
    submission = _load_pinned(root, "submission")
    handoff = _load_pinned(root, "handoff")

    gap_fp = gap["fingerprint"]
    selected = submission["selected_artifact"]
    handoff_selected = handoff["selected_artifact"]
    boundary = {item["boundary"]: item for item in gap["boundary_summary"]}
    identity_hashes = [
        gap_fp["champion_sha256"],
        gap_fp["submitted_artifact_sha256"],
        selected["sha256"],
        selected["kernel_payload_sha256"],
        handoff_selected["sha256"],
    ]
    fingerprint_matches = (
        gap_fp["submission_fingerprint"]
        == submission["submission"]["artifact_fingerprint"]
        == handoff["parent_submission"]["artifact_fingerprint"]
    )
    public_scores = [gap_fp["public_score"], submission["submission"]["existing_public_score"]]
    local_trials = boundary["breach"]["trials"]
    local_successes = boundary["breach"]["reached"]
    local_rate = boundary["breach"]["reach_rate"]
    if not (
        len(set(identity_hashes)) == 1
        and fingerprint_matches
        and len(set(public_scores)) == 1
        and gap_fp["screen_record_sha256"] == submission["validation_lineage"]["screen_result_sha256"]
        and gap_fp["confirm_record_sha256"] == submission["validation_lineage"]["confirm_result_sha256"]
        and handoff["validation_lineage"]["diagnostic_result_sha256"]
        == INPUT_CONTRACT["transfer_gap"]["sha256"]
        and handoff_selected["kernel_payload_byte_identical"] is True
        and handoff_selected["kernel_declared_sha_matches"] is True
    ):
        raise ValueError("cross-artifact identity or lineage mismatch")
    if local_trials <= 0 or local_successes <= 0 or public_scores[0] != "0.000":
        raise ValueError("expected local-success/public-zero evaluation condition is absent")

    return {
        "schema": "oracle-drift-anchor/v1",
        "issue": "SOT-2292",
        "inputs": [
            {
                "id": value["issue"],
                "path": value["path"],
                "schema": value["schema"],
                "sha256": value["sha256"],
            }
            for value in INPUT_CONTRACT.values()
        ],
        "evaluation_conditions": {
            "sdk_version": gap_fp["sdk_version_recorded"],
            "agent": gap_fp["agent"],
            "model_id": gap_fp["model_id"],
            "environment": gap_fp["environment"],
            "guardrail": gap_fp["guardrail"],
            "scoring_path": gap_fp["scoring_path"],
            "budget_s": gap_fp["budget_s"],
            "temperature": gap_fp["temperature"],
            "sampling": gap_fp["sampling"],
        },
        "artifact_identity": {
            "sha256": identity_hashes[0],
            "all_artifact_hashes_match": True,
            "submission_fingerprint_sha256": gap_fp["submission_fingerprint"],
            "all_submission_fingerprints_match": True,
        },
        "transfer_gap": {
            "local_breach_successes": local_successes,
            "local_trials": local_trials,
            "local_breach_rate": local_rate,
            "public_score": public_scores[0],
            "local_success_observed": True,
            "public_zero_observed": True,
            "oracle_drift_evidence": local_rate > 0 and public_scores[0] == "0.000",
            "hidden_grader_equivalence_claimed": False,
        },
        "safety": {
            "network_used": False,
            "credentials_read": False,
            "protected_payloads_read": False,
            "fixture_values_read": False,
            "candidate_created_or_evaluated": False,
            "champion_changed": False,
            "kaggle_submission_executed": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output", type=Path,
        default=Path("docs/results/sot-2292-oracle-drift-anchor.json"),
    )
    args = parser.parse_args(argv)
    payload = build_oracle_drift_anchor(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
