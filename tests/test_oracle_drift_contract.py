from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from eval.oracle_drift_contract import evaluate_contract, load_anchor


ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 64


def fixed_request() -> dict:
    conditions = load_anchor(ROOT)["evaluation_conditions"]
    candidate = {
        "id": "new-fixed-axis", "implemented": True, "candidate_id": "candidate-1",
        "candidate_sha256": SHA, "evaluation_conditions": conditions,
    }
    stage = {"candidate_id": "candidate-1", "candidate_sha256": SHA,
             "evaluation_conditions": conditions}
    return {
        "axes": [candidate],
        "screen": {**stage, "seeds": [11, 29]},
        "confirm": {**stage, "seeds": [101, 131]},
        "local_proxy": {"metric": "breach_rate", "value": 0.8, "passed": True},
        "public_kpi": {"metric": "public_score", "value": "0.000", "passed": False},
        "exec_compatible": True, "candidate_code_retained": False, "docs_recorded": True,
    }


def test_fixed_redacted_fixture_reproduces_nonpromotion() -> None:
    request = json.loads((ROOT / "docs/results/sot-2293-evaluation-request.json").read_text())
    decision = evaluate_contract(ROOT, request)
    expected = json.loads((ROOT / "docs/results/sot-2293-promotion-decision.json").read_text())
    assert decision == expected
    assert decision["eligible_candidate_count"] == 0
    assert decision["promotion"] is False


def test_unfixed_sha_is_rejected() -> None:
    request = fixed_request()
    request["axes"][0]["candidate_sha256"] = "unfixed"
    with pytest.raises(ValueError, match="missing fixed candidate identity"):
        evaluate_contract(ROOT, request)


def test_missing_conditions_are_rejected() -> None:
    request = fixed_request()
    request["axes"][0]["evaluation_conditions"].pop("budget_s")
    with pytest.raises(ValueError, match="conditions mismatch or incomplete"):
        evaluate_contract(ROOT, request)


def test_same_seed_reuse_is_rejected() -> None:
    request = fixed_request()
    request["confirm"]["seeds"] = [29, 101]
    with pytest.raises(ValueError, match="must be disjoint"):
        evaluate_contract(ROOT, request)


def test_local_only_success_cannot_promote_and_requires_revert_docs() -> None:
    decision = evaluate_contract(ROOT, fixed_request())
    assert decision["local_proxy"]["passed"] is True
    assert decision["public_kpi"]["passed"] is False
    assert decision["promotion"] is False
    assert decision["required_actions"] == ["revert_candidate_code", "record_result_in_docs"]


def test_nonpromotion_fails_if_candidate_code_is_retained() -> None:
    request = fixed_request()
    request["candidate_code_retained"] = True
    with pytest.raises(ValueError, match="requires candidate code revert"):
        evaluate_contract(ROOT, request)


def test_promotion_requires_exec_compatibility() -> None:
    request = fixed_request()
    request["public_kpi"] = {"metric": "public_score", "value": "0.100", "passed": True}
    request["exec_compatible"] = False
    assert evaluate_contract(ROOT, request)["promotion"] is False
    request["exec_compatible"] = True
    request["candidate_code_retained"] = True
    request["docs_recorded"] = False
    assert evaluate_contract(ROOT, request)["promotion"] is True


def test_previously_rejected_axes_need_new_evidence() -> None:
    request = {"axes": [{"id": "seed-robust-action-path", "implemented": True}]}
    decision = evaluate_contract(ROOT, request)
    assert decision["excluded_axes"] == [
        {"id": "seed-robust-action-path", "reason": "rejected_without_new_evidence"}
    ]
