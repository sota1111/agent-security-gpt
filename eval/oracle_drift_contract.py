#!/usr/bin/env python3
"""Fail-closed promotion contract for fixed oracle-drift evaluation artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ANCHOR = {
    "path": "docs/results/sot-2292-oracle-drift-anchor.json",
    "sha256": "19797c087f749594b3bdc3db7fa8b032b5177626dfdbf7aa12e2ca8b0c53912b",
    "schema": "oracle-drift-anchor/v1",
    "issue": "SOT-2292",
}
REJECTED_WITHOUT_NEW_EVIDENCE = {
    "predicate-reach-across-scenarios",
    "tool-result-to-scored-sink-continuation",
    "seed-robust-action-path",
}
REQUIRED_CONDITIONS = {
    "sdk_version", "agent", "model_id", "environment", "guardrail",
    "scoring_path", "budget_s", "temperature", "sampling",
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fail(reason: str) -> None:
    raise ValueError(reason)


def load_anchor(root: Path) -> dict[str, Any]:
    path = root / ANCHOR["path"]
    if _digest(path) != ANCHOR["sha256"]:
        _fail("anchor SHA mismatch")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != ANCHOR["schema"] or payload.get("issue") != ANCHOR["issue"]:
        _fail("anchor identity mismatch")
    if set(payload.get("evaluation_conditions", {})) != REQUIRED_CONDITIONS:
        _fail("anchor evaluation conditions incomplete")
    return payload


def evaluate_contract(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    """Validate a fixed candidate request and return a fail-closed decision."""
    anchor = load_anchor(root)
    axes = request.get("axes")
    if not isinstance(axes, list):
        _fail("axes must be a list")

    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    for axis in axes:
        axis_id = axis.get("id", "<missing>")
        if axis_id in REJECTED_WITHOUT_NEW_EVIDENCE and not axis.get("new_evidence"):
            excluded.append({"id": axis_id, "reason": "rejected_without_new_evidence"})
            continue
        if axis.get("implemented") is not True:
            excluded.append({"id": axis_id, "reason": "not_implemented"})
            continue
        candidate_id, candidate_sha = axis.get("candidate_id"), axis.get("candidate_sha256")
        if not candidate_id or not isinstance(candidate_sha, str) or not SHA256.fullmatch(candidate_sha):
            _fail(f"{axis_id} missing fixed candidate identity")
        if axis.get("evaluation_conditions") != anchor["evaluation_conditions"]:
            _fail(f"{axis_id} evaluation conditions mismatch or incomplete")
        eligible.append(axis)

    if len(eligible) > 1:
        _fail("contract accepts at most one fixed candidate")
    if not eligible:
        return {
            "schema": "oracle-drift-promotion-decision/v1",
            "issue": "SOT-2293",
            "anchor": ANCHOR,
            "eligible_candidate_count": 0,
            "excluded_axes": excluded,
            "local_proxy": anchor["transfer_gap"],
            "public_kpi": {"score": anchor["transfer_gap"]["public_score"], "passed": False},
            "promotion": False,
            "reason": "no_eligible_fixed_candidate",
            "candidate_code_retained": False,
            "required_actions": ["revert_candidate_code", "record_result_in_docs"],
            "kaggle_submission_executed": False,
        }

    candidate = eligible[0]
    screen, confirm = request.get("screen"), request.get("confirm")
    if not isinstance(screen, dict) or not isinstance(confirm, dict):
        _fail("screen and confirm records are required")
    identity = (candidate["candidate_id"], candidate["candidate_sha256"])
    for stage, record in (("screen", screen), ("confirm", confirm)):
        if (record.get("candidate_id"), record.get("candidate_sha256")) != identity:
            _fail(f"{stage} candidate identity mismatch")
        if record.get("evaluation_conditions") != anchor["evaluation_conditions"]:
            _fail(f"{stage} evaluation conditions mismatch")
    if set(screen.get("seeds", [])) & set(confirm.get("seeds", [])):
        _fail("screen and confirm seeds must be disjoint")
    if not screen.get("seeds") or not confirm.get("seeds"):
        _fail("screen and confirm seeds are required")

    local = request.get("local_proxy")
    public = request.get("public_kpi")
    if not isinstance(local, dict) or not isinstance(public, dict):
        _fail("local_proxy and public_kpi must be separate records")
    promotable = all((
        local.get("passed") is True,
        public.get("passed") is True,
        request.get("exec_compatible") is True,
    ))
    if not promotable:
        if request.get("candidate_code_retained") is not False:
            _fail("non-promotion requires candidate code revert")
        if request.get("docs_recorded") is not True:
            _fail("non-promotion requires docs record")
    return {
        "schema": "oracle-drift-promotion-decision/v1",
        "issue": "SOT-2293",
        "anchor": ANCHOR,
        "eligible_candidate_count": 1,
        "candidate_id": identity[0],
        "candidate_sha256": identity[1],
        "local_proxy": local,
        "public_kpi": public,
        "screen_confirm_independent": True,
        "exec_compatible": request.get("exec_compatible") is True,
        "promotion": promotable,
        "reason": "all_gates_passed" if promotable else "public_or_exec_gate_failed",
        "candidate_code_retained": promotable,
        "required_actions": [] if promotable else ["revert_candidate_code", "record_result_in_docs"],
        "kaggle_submission_executed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    request = json.loads(args.request.read_text(encoding="utf-8"))
    decision = evaluate_contract(args.root, request)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
