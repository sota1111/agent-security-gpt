from __future__ import annotations

import importlib.metadata
import json
import shutil
import socket
from pathlib import Path

import pytest

import eval.public_contract_strata as strata


ROOT = Path(__file__).resolve().parents[1]
SDK_ROOT = Path(importlib.metadata.distribution(strata.SDK_DISTRIBUTION).locate_file(""))


def _copy_sdk_sources(tmp_path: Path) -> Path:
    for relative_path, _, _ in strata.SDK_SOURCE_CONTRACT:
        destination = tmp_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SDK_ROOT / relative_path, destination)
    return tmp_path


def test_checked_in_manifest_is_byte_reproducible() -> None:
    first = strata.build_public_contract_strata(ROOT)
    second = strata.build_public_contract_strata(ROOT)
    encoded = lambda value: json.dumps(value, indent=2, sort_keys=True) + "\n"
    expected = (ROOT / "docs/results/sot-2321-public-contract-strata.json").read_text()
    assert encoded(first) == encoded(second) == expected
    assert first["strata"]["count"] == 30
    assert len({item["family_id_sha256"] for item in first["strata"]["families"]}) == 30


def test_repo_input_sha_mismatch_fails_closed(tmp_path: Path) -> None:
    for _, relative_path, _, _ in strata.INPUT_CONTRACT:
        destination = tmp_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative_path, destination)
    (tmp_path / "attack.py").write_bytes(b"changed")
    with pytest.raises(ValueError, match="input SHA mismatch"):
        strata.build_public_contract_strata(tmp_path)


def test_repo_input_schema_mismatch_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    contract = list(strata.INPUT_CONTRACT)
    contract[1] = (*contract[1][:2], "wrong-schema/v1", contract[1][3])
    monkeypatch.setattr(strata, "INPUT_CONTRACT", tuple(contract))
    with pytest.raises(ValueError, match="identity/schema mismatch"):
        strata.build_public_contract_strata(ROOT)


def test_sdk_version_mismatch_fails_closed() -> None:
    with pytest.raises(ValueError, match="SDK version mismatch"):
        strata.build_public_contract_strata(ROOT, sdk_version="3.1.3")


def test_sdk_source_sha_mismatch_fails_closed(tmp_path: Path) -> None:
    sdk_root = _copy_sdk_sources(tmp_path)
    target = sdk_root / strata.SDK_SOURCE_CONTRACT[0][0]
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="SDK source SHA mismatch"):
        strata.build_public_contract_strata(ROOT, sdk_root=sdk_root, sdk_version=strata.SDK_VERSION)


def test_generation_is_offline_and_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: pytest.fail("network used"))
    result = strata.build_public_contract_strata(ROOT)
    encoded = json.dumps(result)
    assert result["safety"] == {
        "network_used": False,
        "credentials_read": False,
        "protected_payloads_read": False,
        "private_fixtures_read": False,
        "candidate_changed": False,
        "champion_changed": False,
        "kaggle_submission_executed": False,
    }
    assert not any(
        term in encoded.lower()
        for term in ("credential_value", "protected_value", "private_fixture_content", "user_message")
    )
    assert all(set(item) == {"family_id_sha256", "definition_sha256"} for item in result["strata"]["families"])
