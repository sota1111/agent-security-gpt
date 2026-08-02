from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from eval.transfer_submission_handoff import build_handoff


ROOT = Path(__file__).resolve().parents[1]


def request() -> dict:
    return json.loads((ROOT / "docs/results/sot-2312-handoff-input.json").read_text())


def test_checked_in_handoff_is_deterministic_and_ineligible() -> None:
    actual = build_handoff(ROOT, request())
    expected = json.loads((ROOT / "docs/results/sot-2312-submission-handoff.json").read_text())
    assert actual == expected
    assert actual["submission_eligible"] is False
    assert actual["new_artifact"] is False
    assert actual["no_promotion_no_new_artifact"] is True
    assert actual["submission_owner"] == "SOT-2309"
    assert actual["wrapper_execution_allowed_for_this_issue"] is False
    assert actual["kaggle_submission_executed"] is False


@pytest.mark.parametrize("issue", ["SOT-2310", "SOT-2311"])
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


def test_child_acceptance_failure_fails_closed(tmp_path: Path) -> None:
    data = copy.deepcopy(request())
    record = next(item for item in data["children"] if item["issue"] == "SOT-2310")
    payload = json.loads((ROOT / record["path"]).read_text())
    payload["fail_closed"]["valid"] = False
    artifact = tmp_path / "manifest.json"
    artifact.write_text(json.dumps(payload, sort_keys=True))
    record["path"] = str(artifact)
    record["sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    decision = next(item for item in data["children"] if item["issue"] == "SOT-2311")
    decision_payload = json.loads((ROOT / decision["path"]).read_text())
    decision_payload["manifest"] = {key: record[key] for key in ("issue", "path", "schema", "sha256")}
    decision_artifact = tmp_path / "decision.json"
    decision_artifact.write_text(json.dumps(decision_payload, sort_keys=True))
    decision["path"] = str(decision_artifact)
    decision["sha256"] = hashlib.sha256(decision_artifact.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="acceptance is not valid"):
        build_handoff(ROOT, data)


def test_unchanged_fingerprint_cannot_be_submission_eligible() -> None:
    result = build_handoff(ROOT, request())
    assert result["artifact_identity"]["fingerprint_changed"] is False
    assert "artifact_fingerprint_unchanged_from_previous_submission" in result["ineligibility_reasons"]


def test_no_candidate_or_promotion_is_not_a_successful_new_artifact() -> None:
    result = build_handoff(ROOT, request())
    assert result["artifact_identity"]["candidate_sha256"] is None
    assert result["promotion"] is False
    assert result["submission_eligible"] is False
    assert result["new_artifact"] is False
