#!/usr/bin/env python3
"""Build the cycle-five submission handoff from pinned transfer-aware results."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SHA256 = re.compile(r"^[0-9a-f]{64}$")
TERMINAL_STATES = {"Done", "In Review"}
REQUIRED_CHILDREN = {"SOT-2310", "SOT-2311"}


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
    """Validate all inputs and return one deterministic, fail-closed handoff."""
    children = request.get("children")
    if not isinstance(children, list) or {item.get("issue") for item in children} != REQUIRED_CHILDREN:
        _fail("exactly SOT-2310 and SOT-2311 child results are required")
    if any(item.get("state") not in TERMINAL_STATES for item in children):
        _fail("all child issues must be terminal")

    artifacts = {item["issue"]: _load_pinned(root, item) for item in children}
    manifest, decision = artifacts["SOT-2310"], artifacts["SOT-2311"]
    manifest_record = next(item for item in children if item["issue"] == "SOT-2310")
    if decision.get("manifest") != {
        "issue": manifest_record["issue"],
        "path": manifest_record["path"],
        "schema": manifest_record["schema"],
        "sha256": manifest_record["sha256"],
    }:
        _fail("promotion decision does not reference the pinned transfer manifest")
    if manifest.get("fail_closed", {}).get("valid") is not True:
        _fail("transfer manifest acceptance is not valid")
    if manifest.get("safety", {}).get("kaggle_submission_executed") is not False:
        _fail("transfer manifest submission safety mismatch")
    if decision.get("kaggle_submission_executed") is not False:
        _fail("promotion decision submission safety mismatch")

    lineage = manifest.get("boundaries", {}).get("lineage", {})
    fingerprints = manifest.get("boundaries", {}).get("fingerprint", {})
    local_proxy = manifest.get("boundaries", {}).get("local_proxy", {})
    champion_sha = lineage.get("artifact_sha256")
    current_fingerprint = fingerprints.get("sha256")
    if not isinstance(champion_sha, str) or not SHA256.fullmatch(champion_sha):
        _fail("champion SHA is not fixed")
    if not isinstance(current_fingerprint, str) or not SHA256.fullmatch(current_fingerprint):
        _fail("current fingerprint is not fixed")
    if _digest(root / "attack.py") != champion_sha:
        _fail("working champion does not match the transfer manifest")
    previous_fingerprint = request.get("previous_submission_fingerprint_sha256")
    if not isinstance(previous_fingerprint, str) or not SHA256.fullmatch(previous_fingerprint):
        _fail("previous submission fingerprint is not fixed")

    eligible_count = decision.get("eligible_candidate_count")
    promotion = decision.get("promotion")
    if not isinstance(eligible_count, int) or eligible_count < 0 or not isinstance(promotion, bool):
        _fail("promotion decision is incomplete")
    candidate_sha = decision.get("candidate_sha256") if eligible_count else None
    if candidate_sha is not None and (not isinstance(candidate_sha, str) or not SHA256.fullmatch(candidate_sha)):
        _fail("candidate SHA is not fixed")
    if promotion and eligible_count != 1:
        _fail("promotion requires exactly one eligible candidate")
    if promotion and decision.get("screen_confirm_independent") is not True:
        _fail("promotion acceptance lacks independent screen/confirm evidence")
    if promotion and decision.get("gates") != {"screen": True, "confirm": True, "exec": True, "transfer": True}:
        _fail("promotion acceptance gates are incomplete")
    if not promotion and decision.get("candidate_code_retained") is not False:
        _fail("non-promotion retained candidate code")
    if decision.get("ledger_result_recorded") is not True:
        _fail("promotion result is not recorded in the ledger")

    fingerprint_changed = current_fingerprint != previous_fingerprint
    reasons: list[str] = []
    if eligible_count == 0:
        reasons.append("no_eligible_fixed_candidate")
    if not promotion:
        reasons.append("candidate_not_promoted")
    if not fingerprint_changed:
        reasons.append("artifact_fingerprint_unchanged_from_previous_submission")
    submission_eligible = eligible_count == 1 and promotion and fingerprint_changed

    return {
        "schema": "transfer-aware-submission-handoff/v1",
        "issue": "SOT-2312",
        "parent_issue": "SOT-2309",
        "cycle": 5,
        "child_results": children,
        "artifact_identity": {
            "candidate_sha256": candidate_sha,
            "champion_sha256": champion_sha,
            "current_fingerprint_sha256": current_fingerprint,
            "previous_submission_fingerprint_sha256": previous_fingerprint,
            "fingerprint_changed": fingerprint_changed,
        },
        "evaluation_contract": {
            "conditions_sha256": local_proxy.get("conditions_sha256"),
            "screen_confirm": "independent" if promotion else "not_applicable_no_promotion",
            "exec_compatibility": "pass" if promotion else "not_applicable_no_promotion",
            "transfer_gate": "pass" if promotion else "not_applicable_no_promotion",
        },
        "promotion": promotion,
        "submission_eligible": submission_eligible,
        "ineligibility_reasons": reasons,
        "new_artifact": submission_eligible,
        "no_promotion_no_new_artifact": not promotion,
        "submission_owner": "SOT-2309",
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
