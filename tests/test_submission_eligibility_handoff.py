from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from eval.submission_eligibility_handoff import build_handoff


ROOT = Path(__file__).resolve().parents[1]


def request() -> dict:
    return json.loads((ROOT / "docs/results/sot-2294-handoff-input.json").read_text())


def test_checked_in_handoff_is_reproducible_and_ineligible() -> None:
    actual = build_handoff(ROOT, request())
    expected = json.loads((ROOT / "docs/results/sot-2294-submission-handoff.json").read_text())
    assert actual == expected
    assert actual["submission_eligible"] is False
    assert actual["artifact_identity"]["candidate_sha256"] is None
    assert actual["artifact_identity"]["fingerprint_changed"] is False
    assert actual["kaggle_submission_executed"] is False


@pytest.mark.parametrize("issue", ["SOT-2292", "SOT-2293"])
def test_nonterminal_child_fails_closed(issue: str) -> None:
    data = request()
    next(item for item in data["children"] if item["issue"] == issue)["state"] = "In Progress"
    with pytest.raises(ValueError, match="child issues must be terminal"):
        build_handoff(ROOT, data)


def test_artifact_sha_mutation_fails_closed() -> None:
    data = request()
    data["children"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="artifact SHA mismatch"):
        build_handoff(ROOT, data)


def test_missing_evaluation_conditions_fail_closed(tmp_path: Path) -> None:
    data = copy.deepcopy(request())
    source = json.loads((ROOT / data["children"][0]["path"]).read_text())
    source.pop("evaluation_conditions")
    artifact = tmp_path / "anchor.json"
    artifact.write_text(json.dumps(source))
    data["children"][0]["path"] = str(artifact)
    import hashlib
    data["children"][0]["sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="evaluation conditions are missing"):
        build_handoff(ROOT, data)


def test_same_previous_fingerprint_is_never_eligible() -> None:
    result = build_handoff(ROOT, request())
    assert "artifact_fingerprint_unchanged_from_previous_submission" in result["ineligibility_reasons"]


def test_no_candidate_maps_screen_confirm_and_exec_to_not_applicable() -> None:
    contract = build_handoff(ROOT, request())["evaluation_contract"]
    assert contract["screen_confirm"] == "not_applicable_no_eligible_candidate"
    assert contract["exec_compatibility"] == "not_applicable_no_promotion"
    assert contract["nonpromotion_actions"] == ["revert_candidate_code", "record_result_in_docs"]
