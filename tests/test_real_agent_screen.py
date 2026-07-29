from __future__ import annotations

from eval.real_agent_screen import promotion_decision


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
