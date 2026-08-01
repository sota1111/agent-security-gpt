from __future__ import annotations

import json
import importlib.util
import sys
from pathlib import Path

import pytest

from eval.real_agent import (
    TrialResult,
    _argument_names,
    _structural_shape,
    build_grading_contract_map,
    build_payload,
    candidate_axes,
    deterministic_projection,
    main,
    normalize_diagnostic,
    sdk_symbols,
    summarize,
)


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
    assert payload["diagnostic_scope"]["hidden_test_reproduction_claimed"] is False
    assert payload["diagnostic_scope"]["promotion_decision_made"] is False
    assert len(payload["candidate_axes"]) == 2
    assert [item["phase"] for item in payload["trials"]] == [
        "screen",
        "confirm",
        "confirm",
    ]


def test_candidate_axes_are_grounded_in_observed_failure_stages() -> None:
    results = [
        TrialResult(
            **{
                **trial("screen", 11, 0, 0).__dict__,
                "failure_stage": "no_tool_attempt",
            }
        ),
        TrialResult(
            **{
                **trial("screen", 29, 0, 0).__dict__,
                "failure_stage": "guardrail_blocked",
            }
        ),
    ]
    axes = candidate_axes(results)
    assert [axis["id"] for axis in axes[:2]] == [
        "sdk-native-tool-call-elicitation",
        "beatable-guardrail-indirect-chain",
    ]
    assert axes[0]["observation"]["seeds"] == [11]
    assert axes[1]["observation"]["seeds"] == [29]
    assert all(axis["unaddressed_by_champion"] for axis in axes)


def test_deterministic_projection_removes_volatile_sdk_ids() -> None:
    diagnostic = normalize_diagnostic(
        {
            "call_id": "random",
            "decision": {"tool_name": "fs.read", "call_id": "also-random"},
            "events": [{"timestamp": "now", "action": "allow"}],
        }
    )
    result = TrialResult(
        **{
            **trial("screen", 11, 0, 0).__dict__,
            "failure_stage": "tool_execution_without_objective",
            "evidence": diagnostic,
        }
    )
    projection = deterministic_projection(result)
    assert projection["evidence"] == {
        "decision": {"tool_name": "fs.read"},
        "events": [{"action": "allow"}],
    }


def test_real_agent_artifact_helpers_discard_protected_values() -> None:
    protected = "credential-value-that-must-not-be-serialized"
    evidence = {
        "arguments": {"path": protected, "nested": {"token": protected}},
        "history": [{"content": protected}],
    }

    assert _argument_names(evidence["arguments"]) == ["nested", "path"]
    shape = _structural_shape(evidence)
    assert protected not in json.dumps(shape, sort_keys=True)
    assert shape["fields"]["arguments"]["fields"]["path"] == {"type": "str"}


def test_contract_map_exposes_opaque_fixture_gap_without_secret_values() -> None:
    # The deterministic attack harness installs a minimal fake aicomp_sdk in
    # sys.modules. Restore the installed public SDK before contract inspection.
    for name in list(sys.modules):
        if name == "aicomp_sdk" or name.startswith("aicomp_sdk."):
            sys.modules.pop(name)
    sdk_symbols.cache_clear()
    root = Path(__file__).resolve().parents[1]
    payload = build_grading_contract_map(
        champion=root / "attack.py",
        kernel=root / "kaggle/kernel/submit.py",
        seeds=[11, 29, 101],
    )

    local = [
        item for item in payload["scenario_evidence"]
        if item["scenario"] == "local_mapping_fixture"
    ]
    sdk = [
        item for item in payload["scenario_evidence"]
        if item["scenario"] == "public_sdk_opaque_contract"
    ]
    assert {item["candidate_count"] for item in local} == {1}
    assert {item["candidate_count"] for item in sdk} == {1}
    assert len(payload["hypotheses"]) >= 2
    assert len(payload["next_screen_rules"]) == 3
    assert payload["redaction"] == {
        "fixture_payloads_read": False,
        "credentials_read": False,
        "target_sink_and_argument_identifiers_hashed": True,
        "tool_identifiers_and_argument_identifiers_hashed": True,
    }
    serialized = json.dumps(payload, sort_keys=True)
    sdk_spec = importlib.util.find_spec("aicomp_sdk")
    assert sdk_spec is not None and sdk_spec.origin is not None
    fixture_credentials = json.loads(
        (Path(sdk_spec.origin).parent / "fixtures/file_seed/credentials.json").read_text()
    )
    assert all(str(value) not in serialized for value in fixture_credentials.values())


def test_contract_map_requires_multiple_unique_seeds(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least two unique seeds"):
        build_grading_contract_map(
            champion=tmp_path / "attack.py",
            kernel=tmp_path / "submit.py",
            seeds=[11, 11],
        )


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
