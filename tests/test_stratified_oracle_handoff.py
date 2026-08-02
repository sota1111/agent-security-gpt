from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from eval.stratified_oracle_handoff import build_handoff


ROOT = Path(__file__).resolve().parents[1]


def request() -> dict:
    return json.loads((ROOT / "docs/results/sot-2323-handoff-input.json").read_text())


def test_checked_in_handoff_is_deterministic_and_ineligible() -> None:
    actual = build_handoff(ROOT, request())
    expected = json.loads((ROOT / "docs/results/sot-2323-submission-handoff.json").read_text())
    assert actual == expected
    assert actual["decision"]["result"] == "inconclusive"
    assert actual["decision"]["promotion"] is False
    assert actual["new_artifact"] is False
    assert actual["submission_eligible"] is False
    assert actual["submission_owner"] == "SOT-2317"
    assert actual["wrapper_execution_allowed_for_this_issue"] is False
    assert actual["kaggle_submission_executed"] is False


@pytest.mark.parametrize("issue", ["SOT-2321", "SOT-2322"])
def test_nonterminal_child_fails_closed(issue: str) -> None:
    data = request()
    next(item for item in data["children"] if item["issue"] == issue)["state"] = "In Progress"
    with pytest.raises(ValueError, match="child issues must be terminal"):
        build_handoff(ROOT, data)


def test_artifact_hash_mutation_fails_closed() -> None:
    data = request()
    data["children"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="artifact SHA mismatch"):
        build_handoff(ROOT, data)


def test_false_promotion_fails_closed(tmp_path: Path) -> None:
    data = copy.deepcopy(request())
    record = next(item for item in data["children"] if item["issue"] == "SOT-2322")
    payload = json.loads((ROOT / record["path"]).read_text())
    payload["decision"]["result"] = "promoted"
    artifact = tmp_path / "evaluation.json"
    artifact.write_text(json.dumps(payload, sort_keys=True))
    record["path"] = str(artifact)
    record["sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="promotion lacks a stratified screen"):
        build_handoff(ROOT, data)


def test_unchanged_fingerprint_cannot_be_submission_eligible() -> None:
    result = build_handoff(ROOT, request())
    assert result["artifact_identity"]["fingerprint_changed"] is False
    assert "artifact_fingerprint_unchanged_from_previous_submission" in result["ineligibility_reasons"]


def test_ledger_and_decision_result_agree() -> None:
    ledger = [json.loads(line) for line in (ROOT / "docs/ai/experiment_ledger.jsonl").read_text().splitlines()]
    entry = next(item for item in ledger if item["axis"] == "stratified oracle submission eligibility handoff")
    assert entry["result"] == build_handoff(ROOT, request())["decision"]["result"]


def test_cli_runs_offline_from_arbitrary_cwd(tmp_path: Path) -> None:
    output = tmp_path / "handoff.json"
    env = {**os.environ, "PYTHONPATH": str(ROOT), "NO_PROXY": "*", "no_proxy": "*"}
    subprocess.run(
        [
            sys.executable,
            "-m",
            "eval.stratified_oracle_handoff",
            "--root",
            str(ROOT),
            "--request",
            str(ROOT / "docs/results/sot-2323-handoff-input.json"),
            "--output",
            str(output),
        ],
        cwd=tmp_path,
        env=env,
        check=True,
    )
    assert json.loads(output.read_text()) == build_handoff(ROOT, request())
