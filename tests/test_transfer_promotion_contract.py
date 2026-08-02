from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.transfer_promotion_contract import evaluate_contract, load_manifest


ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 64
FINGERPRINT = "b" * 64


def fixed_request() -> dict:
    conditions = load_manifest(ROOT)["boundaries"]["local_proxy"]["conditions_sha256"]
    candidate = {
        "id": "parent-fixed-candidate",
        "parent_fixed": True,
        "sha256": SHA,
        "fingerprint_sha256": FINGERPRINT,
        "conditions_sha256": conditions,
    }
    identity = {
        "candidate_id": candidate["id"],
        "candidate_sha256": SHA,
        "fingerprint_sha256": FINGERPRINT,
        "conditions_sha256": conditions,
        "passed": True,
    }
    return {
        "candidates": [candidate],
        "evidence": {
            "screen": {**identity, "seeds": [11, 29]},
            "confirm": {**identity, "seeds": [101, 131]},
            "exec": identity,
            "transfer": identity,
        },
        "candidate_code_retained": True,
        "ledger_result_recorded": True,
    }


def test_checked_in_no_candidate_decision_is_reproducible() -> None:
    request = json.loads((ROOT / "docs/results/sot-2311-evaluation-request.json").read_text())
    decision = evaluate_contract(ROOT, request)
    expected = json.loads((ROOT / "docs/results/sot-2311-promotion-decision.json").read_text())
    assert decision == expected
    assert decision["eligible_candidate_count"] == 0
    assert decision["candidate_code_retained"] is False
    assert decision["kaggle_submission_executed"] is False


def test_local_proxy_alone_cannot_promote() -> None:
    request = fixed_request()
    request["evidence"]["transfer"]["passed"] = False
    request["candidate_code_retained"] = False
    assert evaluate_contract(ROOT, request)["promotion"] is False


def test_unfixed_candidate_is_never_evaluated() -> None:
    request = fixed_request()
    request["candidates"][0]["parent_fixed"] = False
    request.pop("evidence")
    request["candidate_code_retained"] = False
    decision = evaluate_contract(ROOT, request)
    assert decision["excluded_candidates"] == [
        {"id": "parent-fixed-candidate", "reason": "not_fixed_by_parent"}
    ]


@pytest.mark.parametrize("missing", ["screen", "confirm", "exec", "transfer"])
def test_missing_required_evidence_fails_closed(missing: str) -> None:
    request = fixed_request()
    request["evidence"].pop(missing)
    with pytest.raises(ValueError, match="evidence incomplete"):
        evaluate_contract(ROOT, request)


def test_manifest_tamper_fails_closed(tmp_path: Path) -> None:
    target = tmp_path / "docs/results/sot-2310-transfer-holdout-provenance.json"
    target.parent.mkdir(parents=True)
    target.write_bytes((ROOT / "docs/results/sot-2310-transfer-holdout-provenance.json").read_bytes() + b"\n")
    with pytest.raises(ValueError, match="manifest SHA mismatch"):
        load_manifest(tmp_path)


def test_conditions_and_identity_mismatch_fail_closed() -> None:
    request = fixed_request()
    request["evidence"]["confirm"]["conditions_sha256"] = "c" * 64
    with pytest.raises(ValueError, match="confirm evaluation conditions mismatch"):
        evaluate_contract(ROOT, request)
    request = fixed_request()
    request["evidence"]["exec"]["candidate_sha256"] = "d" * 64
    with pytest.raises(ValueError, match="exec candidate identity mismatch"):
        evaluate_contract(ROOT, request)


def test_screen_confirm_must_be_independent() -> None:
    request = fixed_request()
    request["evidence"]["confirm"]["seeds"] = [29, 101]
    with pytest.raises(ValueError, match="must be disjoint"):
        evaluate_contract(ROOT, request)


def test_same_champion_fingerprint_cannot_promote() -> None:
    request = fixed_request()
    manifest = load_manifest(ROOT)
    request["candidates"][0]["fingerprint_sha256"] = manifest["boundaries"]["fingerprint"]["sha256"]
    request.pop("evidence")
    request["candidate_code_retained"] = False
    decision = evaluate_contract(ROOT, request)
    assert decision["promotion"] is False
    assert decision["excluded_candidates"][0]["reason"] == "same_champion_fingerprint"


def test_nonpromotion_requires_revert_and_ledger() -> None:
    request = fixed_request()
    request["evidence"]["transfer"]["passed"] = False
    with pytest.raises(ValueError, match="candidate code revert"):
        evaluate_contract(ROOT, request)
    request["candidate_code_retained"] = False
    request["ledger_result_recorded"] = False
    with pytest.raises(ValueError, match="ledger result"):
        evaluate_contract(ROOT, request)


def test_zero_eligible_candidates_still_requires_ledger() -> None:
    request = {"candidates": [], "candidate_code_retained": False, "ledger_result_recorded": False}
    with pytest.raises(ValueError, match="ledger result"):
        evaluate_contract(ROOT, request)


def test_all_distinct_gates_are_required_for_promotion() -> None:
    decision = evaluate_contract(ROOT, fixed_request())
    assert decision["promotion"] is True
    assert decision["gates"] == {"screen": True, "confirm": True, "exec": True, "transfer": True}
