from __future__ import annotations

from eval.real_agent_screen import promotion_decision
from eval.real_agent_confirm import validate_screen_contract

import hashlib
import pytest


def summary(breach: float, objective: float) -> dict:
    return {
        "breach_success_rate": breach,
        "objective_achievement_rate": objective,
    }


def test_gate_accepts_one_improvement_with_other_non_regressing() -> None:
    champion = summary(0.25, 0.5)
    assert promotion_decision(champion, summary(0.5, 0.5))["passed"] is True
    assert promotion_decision(champion, summary(0.25, 0.75))["passed"] is True


def test_gate_rejects_tie_and_tradeoff() -> None:
    champion = summary(0.25, 0.5)
    assert promotion_decision(champion, summary(0.25, 0.5))["passed"] is False
    assert promotion_decision(champion, summary(0.5, 0.25))["passed"] is False


def test_confirm_requires_unchanged_screen_winner_and_disjoint_seeds(tmp_path) -> None:
    candidate = tmp_path / "candidate.py"
    candidate.write_text("winner", encoding="utf-8")
    digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
    screen = {
        "fingerprint": {"screen_seeds": [11, 29, 47]},
        "promotion_gate": {"passing_candidates": ["winner"]},
        "strategies": {"winner": {"sha256": digest}},
    }
    contract = validate_screen_contract(
        screen, candidate_name="winner", candidate=candidate, confirm_seeds=[101, 131]
    )
    assert contract["candidate_sha256"] == digest

    with pytest.raises(ValueError, match="disjoint"):
        validate_screen_contract(
            screen, candidate_name="winner", candidate=candidate, confirm_seeds=[47, 101]
        )
    candidate.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="changed after screen"):
        validate_screen_contract(
            screen, candidate_name="winner", candidate=candidate, confirm_seeds=[101]
        )
