from __future__ import annotations

import json
import socket
import shutil
from pathlib import Path

import pytest

from eval.oracle_drift_anchor import INPUT_CONTRACT, build_oracle_drift_anchor


ROOT = Path(__file__).resolve().parents[1]


def test_fixed_artifacts_reproduce_redacted_transfer_gap() -> None:
    result = build_oracle_drift_anchor(ROOT)

    assert result["transfer_gap"] == {
        "local_breach_successes": 4,
        "local_trials": 6,
        "local_breach_rate": 2 / 3,
        "public_score": "0.000",
        "local_success_observed": True,
        "public_zero_observed": True,
        "oracle_drift_evidence": True,
        "hidden_grader_equivalence_claimed": False,
    }
    assert all(result["safety"][key] is False for key in result["safety"])
    assert [item["sha256"] for item in result["inputs"]] == [
        contract["sha256"] for contract in INPUT_CONTRACT.values()
    ]


def test_input_hash_tampering_fails_closed(tmp_path: Path) -> None:
    for contract in INPUT_CONTRACT.values():
        destination = tmp_path / contract["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / contract["path"], destination)
    tampered = tmp_path / INPUT_CONTRACT["submission"]["path"]
    tampered.write_bytes(tampered.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="submission SHA mismatch"):
        build_oracle_drift_anchor(tmp_path)


def test_output_contains_no_trial_or_protected_values() -> None:
    result = build_oracle_drift_anchor(ROOT)
    serialized = json.dumps(result)

    forbidden_keys = {"trials", "seed", "failure_seeds", "attack", "candidate"}
    assert not forbidden_keys.intersection(serialized.lower().split('"'))
    assert result["safety"]["protected_payloads_read"] is False


def test_generation_succeeds_with_outbound_network_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    def deny_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("outbound network access is forbidden")

    monkeypatch.setattr(socket, "socket", deny_network)
    result = build_oracle_drift_anchor(ROOT)

    assert result["safety"]["network_used"] is False
