#!/usr/bin/env python3
"""Build the cycle-six handoff from pinned stratified-oracle artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SHA256 = re.compile(r"^[0-9a-f]{64}$")
TERMINAL_STATES = {"Done", "In Review"}
REQUIRED_CHILDREN = {"SOT-2321", "SOT-2322"}


def _fail(reason: str) -> None:
    raise ValueError(reason)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_pinned(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    path_value, expected = record.get("path"), record.get("sha256")
    if not isinstance(path_value, str) or not isinstance(expected, str) or not SHA256.fullmatch(expected):
        _fail("artifact path and SHA-256 must be fixed")
    path = root / path_value
    if not path.is_file() or _digest(path) != expected:
        _fail(f"artifact SHA mismatch: {path_value}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("issue") != record.get("issue") or payload.get("schema") != record.get("schema"):
        _fail(f"artifact identity mismatch: {path_value}")
    return payload


def build_handoff(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    """Validate terminal artifacts and return a deterministic, fail-closed handoff."""
    children = request.get("children")
    if (
        not isinstance(children, list)
        or len(children) != len(REQUIRED_CHILDREN)
        or {item.get("issue") for item in children} != REQUIRED_CHILDREN
    ):
        _fail("exactly SOT-2321 and SOT-2322 child results are required")
    if any(item.get("state") not in TERMINAL_STATES for item in children):
        _fail("all child issues must be terminal")

    artifacts = {item["issue"]: _load_pinned(root, item) for item in children}
    manifest, evaluation = artifacts["SOT-2321"], artifacts["SOT-2322"]
    manifest_record = next(item for item in children if item["issue"] == "SOT-2321")
    if evaluation.get("inputs", {}).get("manifest") != {
        key: manifest_record[key] for key in ("issue", "path", "schema", "sha256")
    }:
        _fail("evaluation does not reference the pinned strata manifest")
    if manifest.get("parent_issue") != "SOT-2317" or manifest.get("gates") != {
        "manifest_only": True,
        "screen_before_confirm": True,
    }:
        _fail("strata manifest acceptance contract is invalid")
    if manifest.get("safety", {}).get("kaggle_submission_executed") is not False:
        _fail("manifest submission safety mismatch")
    if evaluation.get("safety", {}).get("kaggle_submission_executed") is not False:
        _fail("evaluation submission safety mismatch")
    if evaluation.get("safety", {}).get("network_used") is not False:
        _fail("evaluation network safety mismatch")
    if evaluation.get("safety", {}).get("protected_payloads_read") is not False:
        _fail("evaluation protected-payload safety mismatch")
    if evaluation.get("safety", {}).get("champion_changed") is not False:
        _fail("evaluation champion safety mismatch")

    champion_sha = evaluation.get("inputs", {}).get("champion_sha256")
    if not isinstance(champion_sha, str) or not SHA256.fullmatch(champion_sha):
        _fail("champion SHA is not fixed")
    if _digest(root / "attack.py") != champion_sha:
        _fail("working champion does not match the evaluation")
    manifest_champion = next(
        (item for item in manifest.get("inputs", []) if item.get("path") == "attack.py"), None
    )
    if not manifest_champion or manifest_champion.get("sha256") != champion_sha:
        _fail("manifest and evaluation champion mismatch")

    result = evaluation.get("decision", {}).get("result")
    if result not in {"promoted", "rejected", "inconclusive"}:
        _fail("evaluation result is incomplete")
    if result == "inconclusive" and evaluation.get("decision", {}).get("fail_closed") is not True:
        _fail("inconclusive evaluation is not fail closed")
    promotion = result == "promoted"
    if promotion:
        if evaluation.get("screen", {}).get("stratified_executed") is not True:
            _fail("promotion lacks a stratified screen")
        if evaluation.get("aggregate_vs_stratified", {}).get("worst_stratum_passed") is not True:
            _fail("promotion lacks a passing worst-stratum gate")
        if evaluation.get("confirm", {}).get("executed") is not True:
            _fail("promotion lacks independent confirm")
        if evaluation.get("decision", {}).get("candidate_code_retained") is not True:
            _fail("promoted candidate is not retained")
    elif evaluation.get("decision", {}).get("candidate_code_retained") is not False:
        _fail("non-promotion retained candidate code")

    provenance_record = next(
        (item for item in manifest.get("inputs", []) if item.get("issue") == "SOT-2310"), None
    )
    if not provenance_record:
        _fail("manifest lacks pinned fingerprint provenance")
    provenance = _load_pinned(root, provenance_record)
    current_fingerprint = provenance.get("boundaries", {}).get("fingerprint", {}).get("sha256")
    previous_fingerprint = request.get("previous_submission_fingerprint_sha256")
    if not isinstance(current_fingerprint, str) or not SHA256.fullmatch(current_fingerprint):
        _fail("current fingerprint is not fixed")
    if not isinstance(previous_fingerprint, str) or not SHA256.fullmatch(previous_fingerprint):
        _fail("previous submission fingerprint is not fixed")

    fingerprint_changed = current_fingerprint != previous_fingerprint
    reasons: list[str] = []
    if not promotion:
        reasons.append(f"oracle_{result}")
    if not fingerprint_changed:
        reasons.append("artifact_fingerprint_unchanged_from_previous_submission")
    submission_eligible = promotion and fingerprint_changed

    return {
        "schema": "stratified-oracle-submission-handoff/v1",
        "issue": "SOT-2323",
        "parent_issue": "SOT-2317",
        "cycle": 6,
        "child_results": children,
        "decision": {
            "result": result,
            "reason": evaluation["decision"].get("reason"),
            "promotion": promotion,
            "fail_closed": evaluation["decision"].get("fail_closed") is True,
        },
        "artifact_identity": {
            "candidate_sha256": champion_sha if promotion else None,
            "champion_sha256": champion_sha,
            "current_fingerprint_sha256": current_fingerprint,
            "previous_submission_fingerprint_sha256": previous_fingerprint,
            "fingerprint_changed": fingerprint_changed,
        },
        "evaluation_contract": {
            "screen_stratified": evaluation.get("screen", {}).get("stratified_executed"),
            "confirm_executed": evaluation.get("confirm", {}).get("executed"),
            "seeds_disjoint": evaluation.get("confirm", {}).get("seeds_disjoint"),
            "aggregate_vs_stratified": evaluation.get("aggregate_vs_stratified", {}).get("disagreement"),
            "exec_compatibility": "not_applicable_no_promotion" if not promotion else "required",
        },
        "new_artifact": submission_eligible,
        "submission_eligible": submission_eligible,
        "ineligibility_reasons": reasons,
        "submission_owner": "SOT-2317",
        "wrapper_execution_allowed_for_this_issue": False,
        "kaggle_submission_executed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    handoff = build_handoff(args.root, json.loads(args.request.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
