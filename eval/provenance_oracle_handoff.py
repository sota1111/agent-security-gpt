#!/usr/bin/env python3
"""Build the SOT-2331 parent handoff from pinned provenance-oracle artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SHA256 = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_CHILDREN = {"SOT-2329", "SOT-2330"}
TERMINAL_STATES = {"Done", "In Review"}


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
    children = request.get("children")
    if not isinstance(children, list) or len(children) != 2 or {x.get("issue") for x in children} != REQUIRED_CHILDREN:
        _fail("exactly SOT-2329 and SOT-2330 child results are required")
    if any(item.get("state") not in TERMINAL_STATES for item in children):
        _fail("all child issues must be terminal")

    artifacts = {item["issue"]: _load_pinned(root, item) for item in children}
    provenance, oracle = artifacts["SOT-2329"], artifacts["SOT-2330"]
    provenance_record = next(item for item in children if item["issue"] == "SOT-2329")
    expected_reference = {key: provenance_record[key] for key in ("issue", "path", "schema", "sha256")}
    actual_reference = dict(oracle.get("inputs", {}).get("trial_family_provenance", {}))
    terminal_result = actual_reference.pop("terminal_result", None)
    if actual_reference != expected_reference or terminal_result != provenance.get("decision", {}).get("result"):
        _fail("oracle does not reference the pinned terminal provenance artifact")

    for payload in (provenance, oracle):
        safety = payload.get("safety", {})
        if safety.get("aggregate_hash_boolean_only") is not True or safety.get("kaggle_submission_executed") is not False:
            _fail("artifact safety contract mismatch")
    result = oracle.get("decision", {}).get("result")
    if result not in {"promoted", "rejected", "inconclusive"}:
        _fail("oracle result is incomplete")
    if result == "inconclusive" and oracle.get("decision", {}).get("fail_closed") is not True:
        _fail("inconclusive oracle is not fail closed")
    if result == "promoted":
        if oracle.get("screen", {}).get("passed") is not True or oracle.get("confirm", {}).get("executed") is not True:
            _fail("promotion lacks screen and confirm evidence")
        if oracle.get("decision", {}).get("prototype_reverted") is not False:
            _fail("promoted prototype was reverted")
    elif oracle.get("decision", {}).get("prototype_reverted") is not True:
        _fail("non-promoted prototype was not reverted")

    candidate = request.get("candidate")
    candidate_fixed = isinstance(candidate, dict) and all(
        isinstance(candidate.get(key), str) and candidate.get(key) for key in ("id", "sha256", "evaluation_condition_sha256")
    ) and bool(SHA256.fullmatch(candidate["sha256"])) and bool(SHA256.fullmatch(candidate["evaluation_condition_sha256"]))
    champion_sha = request.get("champion_sha256")
    if not isinstance(champion_sha, str) or not SHA256.fullmatch(champion_sha) or _digest(root / "attack.py") != champion_sha:
        _fail("champion SHA is not fixed to the working entrypoint")
    previous = request.get("previous_submission_fingerprint_sha256")
    current = request.get("current_submission_fingerprint_sha256")
    if not isinstance(previous, str) or not SHA256.fullmatch(previous) or not isinstance(current, str) or not SHA256.fullmatch(current):
        _fail("submission fingerprints must be fixed")

    promotion = result == "promoted" and candidate_fixed
    fingerprint_changed = current != previous
    new_artifact = candidate_fixed and fingerprint_changed
    oracle_certain = result in {"promoted", "rejected"}
    submission_eligible = candidate_fixed and oracle_certain and fingerprint_changed
    reasons: list[str] = []
    if not candidate_fixed:
        reasons.append("candidate_not_fixed_by_parent_input")
    if not oracle_certain:
        reasons.append("oracle_inconclusive")
    if not fingerprint_changed:
        reasons.append("submission_fingerprint_unchanged")

    return {
        "schema": "provenance-oracle-parent-handoff/v1",
        "issue": "SOT-2331",
        "parent_issue": "SOT-2325",
        "child_results": children,
        "oracle_result": result,
        "eligible_candidate": candidate if candidate_fixed else None,
        "eligible_candidate_count": int(candidate_fixed),
        "promotion": promotion,
        "new_artifact": new_artifact,
        "fingerprint_changed": fingerprint_changed,
        "submission_eligible": submission_eligible,
        "champion_sha256": champion_sha,
        "current_submission_fingerprint_sha256": current,
        "previous_submission_fingerprint_sha256": previous,
        "ineligibility_reasons": reasons,
        "nonpromotion_prototype_reverted": oracle["decision"]["prototype_reverted"],
        "exec_compatibility": oracle["decision"]["exec_entrypoint_compatible"],
        "submission_owner": "SOT-2325",
        "wrapper_execution_allowed_for_this_issue": False,
        "kaggle_submission_executed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = build_handoff(args.root, json.loads(args.request.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
