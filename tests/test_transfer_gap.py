from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.transfer_gap import BOUNDARIES, boundary_reach, build_transfer_gap


def trial(*, seed: int, objective: bool, breach: bool) -> dict:
    return {
        "strategy": "protocol-only-context",
        "seed": seed,
        "objective_achieved": objective,
        "breach_success": breach,
        "failure_stage": "breach_achieved" if breach else "tool_execution_without_objective",
        "evidence": {
            "evaluation_error": None,
            "agent_events": [
                {"decision": {"type": "tool_call", "tool_name": "redacted"}}
            ],
            "guardrail_events": [{}],
            "validated_findings": [{}] if objective else [],
        },
    }


def write_json(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_boundary_reach_is_ordered_and_stops_at_predicate() -> None:
    reach = boundary_reach(trial(seed=29, objective=False, breach=False), artifact_matches=True)
    assert list(reach) == list(BOUNDARIES)
    assert reach == {
        "artifact_identity": True,
        "sdk_load": True,
        "agent_trajectory": True,
        "predicate": False,
        "breach": False,
    }


def test_build_transfer_gap_finds_first_drop_without_copying_payloads(tmp_path: Path, monkeypatch) -> None:
    champion = tmp_path / "attack.py"
    champion.write_text("champion", encoding="utf-8")
    digest = __import__("hashlib").sha256(champion.read_bytes()).hexdigest()
    submission = write_json(tmp_path / "submission.json", {
        "selected_artifact": {"sha256": digest},
        "submission": {
            "artifact_fingerprint": f"sha256:{digest}",
            "existing_submission_ref": "ref",
            "existing_public_score": "0.000",
        },
    })
    screen = write_json(tmp_path / "screen.json", {
        "fingerprint": {
            "sdk_version": "3.1.2", "agent_selection": "gemma",
            "model_id": "model", "budget_s": 30, "environment": "gym",
            "guardrail": "guardrail", "scoring_path": "eval_attack",
            "temperature": 0, "sampling": False,
        },
        "strategies": {"protocol-only-context": {"sha256": digest}},
        "trials": [trial(seed=11, objective=True, breach=True)],
    })
    confirm = write_json(tmp_path / "confirm.json", {
        "fingerprint": {"candidate": {"sha256": digest}},
        "confirm": {"trials": [trial(seed=101, objective=False, breach=False)]},
    })
    monkeypatch.setattr("eval.transfer_gap.importlib.metadata.version", lambda _: "3.1.2")

    payload = build_transfer_gap(
        champion=champion, submission_record=submission,
        screen_record=screen, confirm_record=confirm,
    )

    assert payload["diagnosis"]["first_observed_unreached_boundary"] == "predicate"
    assert payload["diagnosis"]["failure_seeds"] == [101]
    assert payload["promotion_gate"]["status"] == "N/A"
    serialized = json.dumps(payload)
    assert "protected-payload" not in serialized
    assert payload["redaction"]["trial_payloads_copied"] is False


def test_artifact_mismatch_fails_closed(tmp_path: Path) -> None:
    champion = tmp_path / "attack.py"
    champion.write_text("champion", encoding="utf-8")
    paths = [write_json(tmp_path / f"{name}.json", {}) for name in ("s", "x", "c")]
    with pytest.raises((KeyError, ValueError)):
        build_transfer_gap(
            champion=champion, submission_record=paths[0],
            screen_record=paths[1], confirm_record=paths[2],
        )
