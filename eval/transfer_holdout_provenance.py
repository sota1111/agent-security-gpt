#!/usr/bin/env python3
"""Build a deterministic transfer-holdout provenance manifest from fixed artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SHA256 = re.compile(r"^[0-9a-f]{64}$")
INPUT_CONTRACT = (
    ("SOT-2250", "docs/results/sot-2250-kaggle-submission.json", "kaggle-submission-proof/v1", "c902e9dc20fb5047ce096fbb8ed76d12916a84bbe42624bc6bb3caa397cd8acd"),
    ("SOT-2269", "docs/results/sot-2269-post-submission-transfer-gap.json", "post-submission-transfer-gap/v1", "ddd01bba1fa5c1e91fd4548e10b7ca3b17848f22f96dbc87f5a1a5225c1f8be5"),
    ("SOT-2271", "docs/results/sot-2271-submission-handoff.json", "kaggle-submission-handoff/v1", "d369c6d8fdaf12992dc319271e0b8c6bc609512cd314a98c3d8eeae45f90a98d"),
    ("SOT-2292", "docs/results/sot-2292-oracle-drift-anchor.json", "oracle-drift-anchor/v1", "19797c087f749594b3bdc3db7fa8b032b5177626dfdbf7aa12e2ca8b0c53912b"),
    ("SOT-2293", "docs/results/sot-2293-promotion-decision.json", "oracle-drift-promotion-decision/v1", "44530e3a04a588a0b442c97d4cc2a5a4be961ed075be20f8b17a760fbb6ab828"),
    ("SOT-2294", "docs/results/sot-2294-submission-handoff.json", "cycle-submission-eligibility-handoff/v1", "6689f1a497bd37ac49326628a297299eb9ff5c1d12cc6c304fa994be572f10a7"),
)


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return _digest_bytes(encoded)


def _fail(reason: str) -> None:
    raise ValueError(reason)


def _load_inputs(root: Path) -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    for issue, relative_path, schema, expected_sha in INPUT_CONTRACT:
        if not SHA256.fullmatch(expected_sha):
            _fail(f"{issue} contract SHA is invalid")
        path = root / relative_path
        if not path.is_file():
            _fail(f"{issue} artifact is missing")
        if _digest_bytes(path.read_bytes()) != expected_sha:
            _fail(f"{issue} artifact SHA mismatch")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("issue") != issue or payload.get("schema") != schema:
            _fail(f"{issue} artifact identity mismatch")
        loaded[issue] = payload
    return loaded


def build_transfer_holdout_provenance(root: Path) -> dict[str, Any]:
    """Validate the fixed lineage and return aggregate/hash/boolean-only evidence."""
    data = _load_inputs(root)
    submission, gap, handoff = data["SOT-2250"], data["SOT-2269"], data["SOT-2271"]
    anchor, decision, final_handoff = data["SOT-2292"], data["SOT-2293"], data["SOT-2294"]

    contract_by_issue = {issue: sha for issue, _, _, sha in INPUT_CONTRACT}
    expected_lineage = {
        "SOT-2250": submission["selected_artifact"]["sha256"],
        "SOT-2269": gap["fingerprint"]["champion_sha256"],
        "SOT-2271": handoff["selected_artifact"]["sha256"],
        "SOT-2292": anchor["artifact_identity"]["sha256"],
        "SOT-2294": final_handoff["artifact_identity"]["champion_sha256"],
    }
    lineage_hashes_match = len(set(expected_lineage.values())) == 1
    if not lineage_hashes_match:
        _fail("artifact lineage mismatch")
    if handoff["validation_lineage"].get("diagnostic_result_sha256") != contract_by_issue["SOT-2269"]:
        _fail("diagnostic lineage reference mismatch")
    if decision.get("anchor", {}).get("sha256") != contract_by_issue["SOT-2292"]:
        _fail("anchor lineage reference mismatch")
    child_hashes = {item.get("issue"): item.get("sha256") for item in final_handoff.get("child_results", [])}
    if child_hashes != {"SOT-2292": contract_by_issue["SOT-2292"], "SOT-2293": contract_by_issue["SOT-2293"]}:
        _fail("handoff child lineage mismatch")

    fingerprints = {
        submission["submission"]["artifact_fingerprint"],
        gap["fingerprint"]["submission_fingerprint"],
        handoff["parent_submission"]["artifact_fingerprint"],
        anchor["artifact_identity"]["submission_fingerprint_sha256"],
        final_handoff["artifact_identity"]["current_fingerprint"],
    }
    if len(fingerprints) != 1:
        _fail("artifact fingerprint mismatch")

    conditions = anchor.get("evaluation_conditions")
    projected_conditions = {
        "sdk_version": gap["fingerprint"]["sdk_version_recorded"],
        "agent": gap["fingerprint"]["agent"],
        "model_id": gap["fingerprint"]["model_id"],
        "environment": gap["fingerprint"]["environment"],
        "guardrail": gap["fingerprint"]["guardrail"],
        "scoring_path": gap["fingerprint"]["scoring_path"],
        "budget_s": gap["fingerprint"]["budget_s"],
        "temperature": gap["fingerprint"]["temperature"],
        "sampling": gap["fingerprint"]["sampling"],
    }
    if conditions != projected_conditions:
        _fail("evaluation conditions mismatch")
    conditions_sha = _digest_json(conditions)
    if final_handoff.get("evaluation_contract", {}).get("evaluation_conditions_sha256") != conditions_sha:
        _fail("evaluation conditions hash mismatch")

    breach = next((item for item in gap.get("boundary_summary", []) if item.get("boundary") == "breach"), None)
    local = anchor.get("transfer_gap", {})
    if not breach or (breach.get("reached"), breach.get("trials"), breach.get("reach_rate")) != (
        local.get("local_breach_successes"), local.get("local_trials"), local.get("local_breach_rate")
    ):
        _fail("local proxy mismatch")
    public_scores = {
        submission["submission"]["existing_public_score"],
        gap["fingerprint"]["public_score"],
        local.get("public_score"),
        decision.get("public_kpi", {}).get("score"),
    }
    if len(public_scores) != 1:
        _fail("Public KPI mismatch")

    submission_flags = [
        anchor["safety"].get("kaggle_submission_executed"),
        decision.get("kaggle_submission_executed"),
        final_handoff.get("kaggle_submission_executed"),
    ]
    if any(value is not False for value in submission_flags):
        _fail("Kaggle submission safety evidence mismatch")

    artifact_sha = next(iter(expected_lineage.values()))
    fingerprint_sha = next(iter(fingerprints)).removeprefix("sha256:")
    public_score = next(iter(public_scores))
    return {
        "schema": "transfer-holdout-provenance/v1",
        "issue": "SOT-2310",
        "input_artifact_count": len(INPUT_CONTRACT),
        "input_contract_sha256": _digest_json(INPUT_CONTRACT),
        "boundaries": {
            "lineage": {
                "valid": True,
                "artifact_sha256": artifact_sha,
                "input_hashes_match": True,
                "cross_references_match": True,
            },
            "fingerprint": {"valid": True, "sha256": fingerprint_sha, "all_match": True},
            "local_proxy": {
                "valid": True,
                "conditions_sha256": conditions_sha,
                "successes": breach["reached"],
                "trials": breach["trials"],
                "rate": breach["reach_rate"],
            },
            "public_kpi": {
                "valid": True,
                "score_milli": int(round(float(public_score) * 1000)),
                "passed": decision["public_kpi"]["passed"] is True,
            },
        },
        "fail_closed": {"valid": True, "reason_count": 0, "reasons_sha256": _digest_json([])},
        "safety": {
            "network_used": False,
            "credentials_read": False,
            "protected_payloads_read": False,
            "fixture_values_read": False,
            "kaggle_submission_executed": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path("docs/results/sot-2310-transfer-holdout-provenance.json"))
    args = parser.parse_args(argv)
    manifest = build_transfer_holdout_provenance(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
