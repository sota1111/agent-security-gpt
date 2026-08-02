from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

import eval.trial_family_provenance as provenance

ROOT = Path(__file__).resolve().parents[1]


def test_checked_in_artifact_is_byte_reproducible_and_complete() -> None:
    first = provenance.build_trial_family_provenance(ROOT)
    second = provenance.build_trial_family_provenance(ROOT)
    encoded = json.dumps(first, indent=2, sort_keys=True) + "\n"
    assert first == second
    assert encoded == (ROOT / "docs/results/sot-2329-trial-family-provenance.json").read_text()
    assert first["provenance"]["screen"]["family_count"] == 30
    assert first["provenance"]["confirm"]["family_count"] == 30
    assert first["provenance"]["screen_confirm_disjoint"] is True


@pytest.mark.parametrize(
    "metadata, match",
    [
        ({"scope": "local"}, "missing or unknown"),
        ({"side_effect": "READ", "scope": "unknown"}, "unknown trial family"),
        ({"side_effect": "READ", "scope": "local", "extra": True}, "missing or unknown"),
    ],
)
def test_missing_or_unknown_metadata_fails_closed(metadata: dict[str, object], match: str) -> None:
    manifest = provenance.load_manifest(ROOT)
    allowed = {item["family_id_sha256"] for item in manifest["strata"]["families"]}
    with pytest.raises(ValueError, match=match):
        provenance.derive_family_id(metadata, allowed)


def test_duplicate_trial_fails_closed() -> None:
    manifest = provenance.load_manifest(ROOT)
    allowed = {item["family_id_sha256"] for item in manifest["strata"]["families"]}
    trials = provenance.synthetic_trials(provenance.SCREEN_SEEDS)
    with pytest.raises(ValueError, match="duplicate trial"):
        provenance._evaluate(trials + [trials[0]], allowed)


def test_manifest_sha_mismatch_fails_closed(tmp_path: Path) -> None:
    target = tmp_path / provenance.MANIFEST["path"]
    target.parent.mkdir(parents=True)
    target.write_bytes((ROOT / provenance.MANIFEST["path"]).read_bytes() + b"\n")
    with pytest.raises(ValueError, match="manifest SHA mismatch"):
        provenance.load_manifest(tmp_path)


def test_generation_is_offline_and_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))
    result = provenance.build_trial_family_provenance(ROOT)
    encoded = json.dumps(result).lower()
    assert result["safety"]["aggregate_hash_boolean_only"] is True
    assert not any(term in encoded for term in ("prompt_text", "credential_value", "third_party_payload"))
    assert result["safety"]["kaggle_submission_executed"] is False
