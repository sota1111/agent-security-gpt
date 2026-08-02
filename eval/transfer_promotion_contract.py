#!/usr/bin/env python3
"""Fail-closed promotion contract over the fixed SOT-2310 transfer manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


MANIFEST = {
    "issue": "SOT-2310",
    "path": "docs/results/sot-2310-transfer-holdout-provenance.json",
    "schema": "transfer-holdout-provenance/v1",
    "sha256": "345d337a0895ea1588869ddbe6366aa1392fd517ebc9a05aa0d571c336284415",
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_STAGES = ("screen", "confirm", "exec", "transfer")


def _fail(reason: str) -> None:
    raise ValueError(reason)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest(root: Path) -> dict[str, Any]:
    path = root / MANIFEST["path"]
    if not path.is_file() or _digest(path) != MANIFEST["sha256"]:
        _fail("transfer manifest SHA mismatch")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("issue") != MANIFEST["issue"] or payload.get("schema") != MANIFEST["schema"]:
        _fail("transfer manifest identity mismatch")
    boundaries = payload.get("boundaries")
    if not isinstance(boundaries, dict) or set(boundaries) != {
        "lineage", "fingerprint", "local_proxy", "public_kpi"
    }:
        _fail("transfer manifest boundaries incomplete")
    if any(boundaries[name].get("valid") is not True for name in boundaries):
        _fail("transfer manifest contains invalid boundary")
    if payload.get("fail_closed", {}).get("valid") is not True:
        _fail("transfer manifest is not fail-closed")
    if payload.get("safety", {}).get("kaggle_submission_executed") is not False:
        _fail("transfer manifest submission safety mismatch")
    return payload


def evaluate_contract(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic decision; malformed or incomplete evidence raises."""
    manifest = load_manifest(root)
    candidates = request.get("candidates")
    if not isinstance(candidates, list):
        _fail("candidates must be a list")

    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    seen: set[str] = set()
    expected_conditions = manifest["boundaries"]["local_proxy"]["conditions_sha256"]
    champion_sha = manifest["boundaries"]["lineage"]["artifact_sha256"]
    champion_fingerprint = manifest["boundaries"]["fingerprint"]["sha256"]

    for candidate in candidates:
        if not isinstance(candidate, dict):
            _fail("candidate must be an object")
        candidate_id = candidate.get("id")
        if not isinstance(candidate_id, str) or not candidate_id or candidate_id in seen:
            _fail("candidate identity missing or duplicated")
        seen.add(candidate_id)
        if candidate.get("parent_fixed") is not True:
            excluded.append({"id": candidate_id, "reason": "not_fixed_by_parent"})
            continue
        candidate_sha = candidate.get("sha256")
        fingerprint = candidate.get("fingerprint_sha256")
        if not isinstance(candidate_sha, str) or not SHA256.fullmatch(candidate_sha):
            _fail(f"{candidate_id} candidate SHA missing or invalid")
        if not isinstance(fingerprint, str) or not SHA256.fullmatch(fingerprint):
            _fail(f"{candidate_id} fingerprint missing or invalid")
        if candidate.get("conditions_sha256") != expected_conditions:
            _fail(f"{candidate_id} evaluation conditions mismatch")
        if candidate_sha == champion_sha or fingerprint == champion_fingerprint:
            excluded.append({"id": candidate_id, "reason": "same_champion_fingerprint"})
            continue
        eligible.append(candidate)

    if len(eligible) > 1:
        _fail("contract accepts at most one eligible candidate")
    if not eligible:
        if request.get("candidate_code_retained") is not False:
            _fail("no eligible candidate requires no retained candidate code")
        if request.get("ledger_result_recorded") is not True:
            _fail("non-promotion requires ledger result")
        return {
            "schema": "transfer-aware-promotion-decision/v1",
            "issue": "SOT-2311",
            "manifest": MANIFEST,
            "candidate_count": len(candidates),
            "eligible_candidate_count": 0,
            "excluded_candidates": excluded,
            "promotion": False,
            "reason": "no_eligible_fixed_candidate",
            "candidate_code_retained": False,
            "ledger_result_recorded": True,
            "kaggle_submission_executed": False,
        }

    candidate = eligible[0]
    evidence = request.get("evidence")
    if not isinstance(evidence, dict) or set(evidence) != set(REQUIRED_STAGES):
        _fail("screen/confirm/exec/transfer evidence incomplete")
    identity = (candidate["id"], candidate["sha256"], candidate["fingerprint_sha256"])
    for stage in REQUIRED_STAGES:
        record = evidence[stage]
        if not isinstance(record, dict):
            _fail(f"{stage} evidence must be an object")
        if (record.get("candidate_id"), record.get("candidate_sha256"), record.get("fingerprint_sha256")) != identity:
            _fail(f"{stage} candidate identity mismatch")
        if record.get("conditions_sha256") != expected_conditions:
            _fail(f"{stage} evaluation conditions mismatch")
        if record.get("passed") not in (True, False):
            _fail(f"{stage} pass result missing")

    screen_seeds = evidence["screen"].get("seeds")
    confirm_seeds = evidence["confirm"].get("seeds")
    if not isinstance(screen_seeds, list) or not screen_seeds:
        _fail("screen seeds missing")
    if not isinstance(confirm_seeds, list) or not confirm_seeds:
        _fail("confirm seeds missing")
    if set(screen_seeds) & set(confirm_seeds):
        _fail("screen and confirm seeds must be disjoint")

    promotion = all(evidence[stage]["passed"] is True for stage in REQUIRED_STAGES)
    if not promotion:
        if request.get("candidate_code_retained") is not False:
            _fail("non-promotion requires candidate code revert")
        if request.get("ledger_result_recorded") is not True:
            _fail("non-promotion requires ledger result")
    return {
        "schema": "transfer-aware-promotion-decision/v1",
        "issue": "SOT-2311",
        "manifest": MANIFEST,
        "candidate_count": len(candidates),
        "eligible_candidate_count": 1,
        "candidate_id": candidate["id"],
        "candidate_sha256": candidate["sha256"],
        "fingerprint_sha256": candidate["fingerprint_sha256"],
        "gates": {stage: evidence[stage]["passed"] for stage in REQUIRED_STAGES},
        "screen_confirm_independent": True,
        "promotion": promotion,
        "reason": "all_transfer_gates_passed" if promotion else "transfer_gate_failed",
        "candidate_code_retained": promotion,
        "ledger_result_recorded": request.get("ledger_result_recorded") is True,
        "kaggle_submission_executed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    decision = evaluate_contract(args.root, json.loads(args.request.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
