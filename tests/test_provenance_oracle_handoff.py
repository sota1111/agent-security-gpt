from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from eval.provenance_oracle_handoff import build_handoff


ROOT = Path(__file__).resolve().parents[1]


def request() -> dict:
    return json.loads((ROOT / "docs/results/sot-2331-handoff-input.json").read_text())


def test_checked_in_handoff_is_deterministic_and_fail_closed() -> None:
    actual = build_handoff(ROOT, request())
    expected = json.loads((ROOT / "docs/results/sot-2331-submission-handoff.json").read_text())
    assert actual == expected
    assert actual["promotion"] is False
    assert actual["new_artifact"] is False
    assert actual["fingerprint_changed"] is False
    assert actual["submission_eligible"] is False
    assert actual["submission_owner"] == "SOT-2325"
    assert actual["kaggle_submission_executed"] is False


@pytest.mark.parametrize("issue", ["SOT-2329", "SOT-2330"])
def test_nonterminal_child_fails_closed(issue: str) -> None:
    data = request()
    next(x for x in data["children"] if x["issue"] == issue)["state"] = "In Progress"
    with pytest.raises(ValueError, match="child issues must be terminal"):
        build_handoff(ROOT, data)


def test_hash_mismatch_fails_closed() -> None:
    data = request()
    data["children"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="artifact SHA mismatch"):
        build_handoff(ROOT, data)


def test_unfixed_candidate_fails_closed_even_with_changed_fingerprint() -> None:
    data = request()
    data["current_submission_fingerprint_sha256"] = "1" * 64
    result = build_handoff(ROOT, data)
    assert result["fingerprint_changed"] is True
    assert result["new_artifact"] is False
    assert result["submission_eligible"] is False


def test_inconclusive_oracle_fails_closed_for_fixed_candidate() -> None:
    data = request()
    data["candidate"] = {"id": "candidate-a", "sha256": "2" * 64, "evaluation_condition_sha256": "3" * 64}
    data["current_submission_fingerprint_sha256"] = "1" * 64
    result = build_handoff(ROOT, data)
    assert result["new_artifact"] is True
    assert result["promotion"] is False
    assert result["submission_eligible"] is False


@pytest.mark.parametrize(
    ("oracle_result", "screen_passed", "confirm_executed", "prototype_reverted", "eligible"),
    [
        ("rejected", False, False, True, True),
        ("promoted", True, True, False, True),
    ],
)
def test_terminal_decision_branches_are_explicit(
    tmp_path: Path,
    oracle_result: str,
    screen_passed: bool,
    confirm_executed: bool,
    prototype_reverted: bool,
    eligible: bool,
) -> None:
    data = copy.deepcopy(request())
    record = next(x for x in data["children"] if x["issue"] == "SOT-2330")
    payload = json.loads((ROOT / record["path"]).read_text())
    payload["decision"].update(result=oracle_result, prototype_reverted=prototype_reverted)
    payload["screen"]["passed"] = screen_passed
    payload["confirm"]["executed"] = confirm_executed
    artifact = tmp_path / f"{oracle_result}.json"
    artifact.write_text(json.dumps(payload, sort_keys=True))
    record["path"] = str(artifact)
    record["sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    data["candidate"] = {"id": "candidate-a", "sha256": "2" * 64, "evaluation_condition_sha256": "3" * 64}
    data["current_submission_fingerprint_sha256"] = "1" * 64
    result = build_handoff(ROOT, data)
    assert result["oracle_result"] == oracle_result
    assert result["submission_eligible"] is eligible
    assert result["promotion"] is (oracle_result == "promoted")


def test_false_promoted_terminal_reference_fails_closed(tmp_path: Path) -> None:
    data = copy.deepcopy(request())
    record = next(x for x in data["children"] if x["issue"] == "SOT-2330")
    payload = json.loads((ROOT / record["path"]).read_text())
    payload["inputs"]["trial_family_provenance"]["terminal_result"] = "rejected"
    artifact = tmp_path / "oracle.json"
    artifact.write_text(json.dumps(payload, sort_keys=True))
    record["path"] = str(artifact)
    record["sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="pinned terminal provenance"):
        build_handoff(ROOT, data)


def test_ledger_matches_handoff_result() -> None:
    ledger = [json.loads(line) for line in (ROOT / "docs/ai/experiment_ledger.jsonl").read_text().splitlines()]
    entry = next(x for x in ledger if x["axis"] == "provenance oracle parent submission handoff")
    assert entry["result"] == build_handoff(ROOT, request())["oracle_result"]
