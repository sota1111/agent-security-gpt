from __future__ import annotations

import copy
import json
import shutil
import socket
from pathlib import Path

import pytest

import eval.transfer_holdout_provenance as provenance


ROOT = Path(__file__).resolve().parents[1]


def _copy_inputs(tmp_path: Path) -> None:
    for _, relative_path, _, _ in provenance.INPUT_CONTRACT:
        destination = tmp_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative_path, destination)


def _repin(monkeypatch: pytest.MonkeyPatch, issue: str, path: Path) -> None:
    updated = []
    for item in provenance.INPUT_CONTRACT:
        updated.append((*item[:3], provenance._digest_bytes(path.read_bytes())) if item[0] == issue else item)
    monkeypatch.setattr(provenance, "INPUT_CONTRACT", tuple(updated))


def test_checked_in_manifest_is_byte_reproducible() -> None:
    first = provenance.build_transfer_holdout_provenance(ROOT)
    second = provenance.build_transfer_holdout_provenance(ROOT)
    encoded = lambda value: json.dumps(value, indent=2, sort_keys=True) + "\n"
    expected = (ROOT / "docs/results/sot-2310-transfer-holdout-provenance.json").read_text()
    assert encoded(first) == encoded(second) == expected
    assert set(first["boundaries"]) == {"lineage", "fingerprint", "local_proxy", "public_kpi"}
    assert first["fail_closed"]["valid"] is True
    assert first["safety"]["kaggle_submission_executed"] is False


def test_hash_tampering_fails_closed(tmp_path: Path) -> None:
    _copy_inputs(tmp_path)
    target = tmp_path / provenance.INPUT_CONTRACT[0][1]
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="artifact SHA mismatch"):
        provenance.build_transfer_holdout_provenance(tmp_path)


def test_missing_lineage_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _copy_inputs(tmp_path)
    path = tmp_path / "docs/results/sot-2294-submission-handoff.json"
    payload = json.loads(path.read_text())
    payload["child_results"] = payload["child_results"][:1]
    path.write_text(json.dumps(payload))
    _repin(monkeypatch, "SOT-2294", path)
    with pytest.raises(ValueError, match="child lineage mismatch"):
        provenance.build_transfer_holdout_provenance(tmp_path)


def test_condition_mismatch_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _copy_inputs(tmp_path)
    path = tmp_path / "docs/results/sot-2292-oracle-drift-anchor.json"
    payload = json.loads(path.read_text())
    payload["evaluation_conditions"]["budget_s"] = 31.0
    path.write_text(json.dumps(payload))
    _repin(monkeypatch, "SOT-2292", path)

    anchor_sha = provenance._digest_bytes(path.read_bytes())
    decision_path = tmp_path / "docs/results/sot-2293-promotion-decision.json"
    decision = json.loads(decision_path.read_text())
    decision["anchor"]["sha256"] = anchor_sha
    decision_path.write_text(json.dumps(decision))
    _repin(monkeypatch, "SOT-2293", decision_path)

    decision_sha = provenance._digest_bytes(decision_path.read_bytes())
    handoff_path = tmp_path / "docs/results/sot-2294-submission-handoff.json"
    handoff = json.loads(handoff_path.read_text())
    child_hashes = {"SOT-2292": anchor_sha, "SOT-2293": decision_sha}
    for child in handoff["child_results"]:
        child["sha256"] = child_hashes[child["issue"]]
    handoff_path.write_text(json.dumps(handoff))
    _repin(monkeypatch, "SOT-2294", handoff_path)
    with pytest.raises(ValueError, match="evaluation conditions mismatch"):
        provenance.build_transfer_holdout_provenance(tmp_path)


def test_generation_uses_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))
    result = provenance.build_transfer_holdout_provenance(ROOT)
    assert result["safety"]["network_used"] is False


def test_output_values_are_only_aggregates_booleans_hashes_and_identifiers() -> None:
    result = provenance.build_transfer_holdout_provenance(ROOT)
    assert result["safety"] == {
        "network_used": False,
        "credentials_read": False,
        "protected_payloads_read": False,
        "fixture_values_read": False,
        "kaggle_submission_executed": False,
    }
    assert not any(key in result for key in ("trials", "seeds", "payloads", "credentials", "procedures"))
