from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.real_agent import TrialResult, build_payload, main, summarize


def trial(phase: str, seed: int, breaches: int, objectives: int) -> TrialResult:
    return TrialResult(
        phase=phase,
        strategy="champion",
        agent="gemma",
        seed=seed,
        findings=objectives,
        breaches=breaches,
        objectives=objectives,
        breach_success=breaches > 0,
        objective_achieved=objectives > 0,
    )


def test_rates_use_trials_as_denominator() -> None:
    summary = summarize(
        [
            trial("screen", 1, 4, 4),
            trial("screen", 2, 0, 0),
            trial("screen", 3, 1, 2),
        ]
    )
    assert summary["trials"] == 3
    assert summary["breach_successes"] == 2
    assert summary["objective_successes"] == 2
    assert summary["breach_success_rate"] == pytest.approx(2 / 3)
    assert summary["objective_achievement_rate"] == pytest.approx(2 / 3)
    assert summary["total_breaches"] == 5
    assert summary["total_validated_findings"] == 6


def test_payload_keeps_phase_seed_and_gap_provenance(tmp_path: Path) -> None:
    champion = tmp_path / "attack.py"
    champion.write_text("champion", encoding="utf-8")
    results = [
        trial("screen", 11, 1, 1),
        trial("confirm", 101, 0, 1),
        trial("confirm", 131, 1, 1),
    ]
    payload = build_payload(
        results=results,
        screen_seeds=[11],
        confirm_seeds=[101, 131],
        champion=champion,
        agent="gemma",
        model_path=None,
        model_id="test-model",
        budget_s=1,
        proxy_coverage_rate=1,
    )
    assert payload["fingerprint"]["seed_sets_disjoint"] is True
    assert payload["real_agent"]["screen"]["breach_successes"] == 1
    assert payload["real_agent"]["confirm"]["trials"] == 2
    assert payload["transfer_gap"]["confirm"]["proxy_coverage_minus_breach_rate"] == 0.5
    assert payload["promotion_gate"]["coverage_only_promotion_allowed"] is False
    assert [item["phase"] for item in payload["trials"]] == [
        "screen",
        "confirm",
        "confirm",
    ]


def test_cli_rejects_overlapping_phase_seeds(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(
            [
                "--screen-seeds",
                "11,29",
                "--confirm-seeds",
                "29,101",
                "--proxy-coverage-rate",
                "1",
                "--output",
                str(tmp_path / "result.json"),
            ]
        )
