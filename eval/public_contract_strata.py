#!/usr/bin/env python3
"""Build a deterministic scenario-strata manifest from pinned public contracts."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
from pathlib import Path
from typing import Any

SDK_DISTRIBUTION = "aicomp-sdk"
SDK_VERSION = "3.1.2"
SDK_SOURCE_CONTRACT = (
    ("aicomp_sdk/core/tools/models.py", "python-source/v1", "61539f52cddbd40e86dfc3cc41e3548bfca78d5de2b469559b67fed90e1f3acd"),
    ("aicomp_sdk/core/env/api.py", "python-source/v1", "60f1e4424ec3dee73186f87ed1184d2ca1dbc4c2a0022004decec8b6e94c7cb1"),
    ("aicomp_sdk/attacks/contracts.py", "python-source/v1", "d5ebfee31480fa2ce1e592e9874bf4fee5616868d2bf22d219652b91d9b210ef"),
    ("aicomp_sdk/scoring.py", "python-source/v1", "13a0969ea6c64b257c46d47490b4259ade3a4965f19d2d6c6fe0ed151f618d4f"),
)
INPUT_CONTRACT = (
    ("SOT-2317", "attack.py", "python-source/v1", "6b1e7d8129bfbcc0ed61484e337cdb537ac743faef650b876446cfd957d0f6f0"),
    ("SOT-2310", "docs/results/sot-2310-transfer-holdout-provenance.json", "transfer-holdout-provenance/v1", "345d337a0895ea1588869ddbe6366aa1392fd517ebc9a05aa0d571c336284415"),
    ("SOT-2292", "docs/results/sot-2292-oracle-drift-anchor.json", "oracle-drift-anchor/v1", "19797c087f749594b3bdc3db7fa8b032b5177626dfdbf7aa12e2ca8b0c53912b"),
    ("SOT-2250", "docs/results/sot-2250-kaggle-submission.json", "kaggle-submission-proof/v1", "c902e9dc20fb5047ce096fbb8ed76d12916a84bbe42624bc6bb3caa397cd8acd"),
    ("SOT-2269", "docs/results/sot-2269-post-submission-transfer-gap.json", "post-submission-transfer-gap/v1", "ddd01bba1fa5c1e91fd4548e10b7ca3b17848f22f96dbc87f5a1a5225c1f8be5"),
)
EXPECTED_EFFECTS = ("AUTH", "EXEC", "NETWORK", "READ", "SHARE", "WRITE")
EXPECTED_SCOPES = ("external", "internal", "local", "public", "secrets")


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return _digest_bytes(encoded)


def _validate_repo_inputs(root: Path) -> list[dict[str, str]]:
    records = []
    for issue, relative_path, schema, expected_sha in INPUT_CONTRACT:
        path = root / relative_path
        if not path.is_file() or _digest_bytes(path.read_bytes()) != expected_sha:
            raise ValueError(f"{issue} input SHA mismatch or file missing")
        if path.suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("issue") != issue or payload.get("schema") != schema:
                raise ValueError(f"{issue} input identity/schema mismatch")
        records.append({"issue": issue, "path": relative_path, "schema": schema, "sha256": expected_sha})
    return records


def _validate_sdk(sdk_root: Path | None = None, sdk_version: str | None = None) -> list[dict[str, str]]:
    version = sdk_version if sdk_version is not None else importlib.metadata.version(SDK_DISTRIBUTION)
    if version != SDK_VERSION:
        raise ValueError("SDK version mismatch")
    package_root = sdk_root or Path(importlib.metadata.distribution(SDK_DISTRIBUTION).locate_file(""))
    records = []
    for relative_path, schema, expected_sha in SDK_SOURCE_CONTRACT:
        path = package_root / relative_path
        if not path.is_file() or _digest_bytes(path.read_bytes()) != expected_sha:
            raise ValueError(f"SDK source SHA mismatch: {relative_path}")
        records.append({"path": relative_path, "schema": schema, "sha256": expected_sha})
    models_path = package_root / SDK_SOURCE_CONTRACT[0][0]
    tree = ast.parse(models_path.read_text(encoding="utf-8"))
    enum_values: dict[str, tuple[str, ...]] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in {"ToolSideEffect", "ToolScope"}:
            enum_values[node.name] = tuple(
                sorted(
                    child.value.value
                    for child in node.body
                    if isinstance(child, ast.Assign)
                    and isinstance(child.value, ast.Constant)
                    and isinstance(child.value.value, str)
                )
            )
    effects = enum_values.get("ToolSideEffect", ())
    scopes = enum_values.get("ToolScope", ())
    if effects != EXPECTED_EFFECTS or scopes != EXPECTED_SCOPES:
        raise ValueError("SDK public enum shape mismatch")
    return records


def build_public_contract_strata(
    root: Path, *, sdk_root: Path | None = None, sdk_version: str | None = None
) -> dict[str, Any]:
    """Validate fixed inputs and return a hash-only scenario-family inventory."""
    inputs = _validate_repo_inputs(root)
    sdk_sources = _validate_sdk(sdk_root, sdk_version)
    definitions = [
        {"side_effect": effect, "scope": scope}
        for effect in EXPECTED_EFFECTS
        for scope in EXPECTED_SCOPES
    ]
    strata = [
        {
            "family_id_sha256": _digest_json({"schema": "scenario-family/v1", **definition}),
            "definition_sha256": _digest_json(definition),
        }
        for definition in definitions
    ]
    return {
        "schema": "public-contract-scenario-strata-manifest/v1",
        "issue": "SOT-2321",
        "parent_issue": "SOT-2317",
        "sdk": {
            "distribution": SDK_DISTRIBUTION,
            "version": SDK_VERSION,
            "source_count": len(sdk_sources),
            "sources": sdk_sources,
            "contract_sha256": _digest_json(sdk_sources),
        },
        "inputs": inputs,
        "input_count": len(inputs),
        "input_contract_sha256": _digest_json(inputs),
        "strata": {
            "schema": "tool-side-effect-scope-cartesian/v1",
            "count": len(strata),
            "definitions_sha256": _digest_json(definitions),
            "inventory_sha256": _digest_json(strata),
            "families": strata,
        },
        "gates": {"screen_before_confirm": True, "manifest_only": True},
        "safety": {
            "network_used": False,
            "credentials_read": False,
            "protected_payloads_read": False,
            "private_fixtures_read": False,
            "candidate_changed": False,
            "champion_changed": False,
            "kaggle_submission_executed": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path("docs/results/sot-2321-public-contract-strata.json"))
    args = parser.parse_args(argv)
    manifest = build_public_contract_strata(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
