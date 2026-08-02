#!/usr/bin/env python3
"""Build the cycle-four submission handoff from pinned, redacted artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SHA256 = re.compile(r"^[0-9a-f]{64}$")
FINGERPRINT = re.compile(r"^sha256:[0-9a-f]{64}$")
TERMINAL_STATES = {"Done", "In Review"}
REQUIRED_CHILDREN = {"SOT-2292", "SOT-2293"}


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
        _fail("exactly SOT-2292 and SOT-2293 child results are required")
    if any(item.get("state") not in TERMINAL_STATES for item in children):
        _fail("all child issues must be terminal")

    artifacts = {item["issue"]: _load_pinned(root, item) for item in children}
    anchor, decision = artifacts["SOT-2292"], artifacts["SOT-2293"]
    conditions = anchor.get("evaluation_conditions")
    if not isinstance(conditions, dict) or not conditions:
        _fail("evaluation conditions are missing")
    if decision.get("anchor", {}).get("sha256") != next(
        item["sha256"] for item in children if item["issue"] == "SOT-2292"
    ):
        _fail("promotion decision does not reference the pinned oracle-drift anchor")
    if anchor.get("safety", {}).get("kaggle_submission_executed") is not False:
        _fail("child submission safety evidence missing")
    if decision.get("kaggle_submission_executed") is not False:
        _fail("promotion decision submission safety evidence missing")

    champion_sha = anchor.get("artifact_identity", {}).get("sha256")
    if not isinstance(champion_sha, str) or not SHA256.fullmatch(champion_sha):
        _fail("champion SHA is not fixed")
    if _digest(root / "attack.py") != champion_sha:
        _fail("working champion does not match the anchored SHA")

    previous = _load_pinned(root, request.get("previous_submission", {}))
    previous_fingerprint = previous.get("submission", {}).get("artifact_fingerprint")
    current_fingerprint = anchor.get("artifact_identity", {}).get("submission_fingerprint_sha256")
    if not isinstance(previous_fingerprint, str) or not FINGERPRINT.fullmatch(previous_fingerprint):
        _fail("previous submission fingerprint is missing")
    if not isinstance(current_fingerprint, str) or not FINGERPRINT.fullmatch(current_fingerprint):
        _fail("current artifact fingerprint is missing")

    eligible_count = decision.get("eligible_candidate_count")
    promotion = decision.get("promotion")
    if not isinstance(eligible_count, int) or not isinstance(promotion, bool):
        _fail("promotion decision is incomplete")
    candidate_sha = decision.get("candidate_sha256") if eligible_count else None
    if candidate_sha is not None and (not isinstance(candidate_sha, str) or not SHA256.fullmatch(candidate_sha)):
        _fail("candidate SHA is not fixed")

    if eligible_count:
        if decision.get("screen_confirm_independent") is not True:
            _fail("screen/confirm independence evidence missing")
        if decision.get("exec_compatible") is not True:
            _fail("exec compatibility evidence missing")
    elif promotion:
        _fail("promotion cannot succeed without an eligible fixed candidate")

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
        "schema": "cycle-submission-eligibility-handoff/v1",
        "issue": "SOT-2294",
        "parent_issue": "SOT-2291",
        "cycle": 4,
        "child_results": children,
        "artifact_identity": {
            "candidate_sha256": candidate_sha,
            "champion_sha256": champion_sha,
            "current_fingerprint": current_fingerprint,
            "previous_submission_fingerprint": previous_fingerprint,
            "fingerprint_changed": fingerprint_changed,
        },
        "evaluation_contract": {
            "evaluation_conditions_sha256": hashlib.sha256(
                json.dumps(conditions, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            "screen_confirm": "not_applicable_no_eligible_candidate" if not eligible_count else "independent",
            "exec_compatibility": "not_applicable_no_promotion" if not promotion else "pass",
            "nonpromotion_actions": decision.get("required_actions", []),
        },
        "promotion": promotion,
        "submission_eligible": submission_eligible,
        "ineligibility_reasons": reasons,
        "submission_owner": "SOT-2291",
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
