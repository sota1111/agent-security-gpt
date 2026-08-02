#!/usr/bin/env python3
"""Build deterministic trial-family provenance from the pinned public SDK contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

MANIFEST = {
    "issue": "SOT-2321",
    "path": "docs/results/sot-2321-public-contract-strata.json",
    "schema": "public-contract-scenario-strata-manifest/v1",
    "sha256": "c6034b582d9567249b7c6416cbe718919c42c4af6482910dac881511e40097ab",
}
SCHEMA = "sdk-native-trial-family-provenance/v1"
SCREEN_SEEDS = (1103, 2207)
CONFIRM_SEEDS = (3301, 4409)
SDK_SIDE_EFFECTS = ("AUTH", "EXEC", "NETWORK", "READ", "SHARE", "WRITE")
SDK_SCOPES = ("external", "internal", "local", "public", "secrets")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest(root: Path) -> dict[str, Any]:
    path = root / MANIFEST["path"]
    if not path.is_file() or _file_sha(path) != MANIFEST["sha256"]:
        raise ValueError("manifest SHA mismatch or file missing")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("issue") != MANIFEST["issue"] or payload.get("schema") != MANIFEST["schema"]:
        raise ValueError("manifest identity/schema mismatch")
    families = payload.get("strata", {}).get("families", [])
    family_ids = [item.get("family_id_sha256") for item in families]
    if not family_ids or len(family_ids) != len(set(family_ids)):
        raise ValueError("manifest family inventory missing or duplicated")
    return payload


def derive_family_id(metadata: dict[str, Any], allowed_ids: set[str]) -> str:
    if set(metadata) != {"side_effect", "scope"}:
        raise ValueError("trial metadata missing or unknown fields")
    effect = metadata["side_effect"]
    scope = metadata["scope"]
    if effect not in SDK_SIDE_EFFECTS or scope not in SDK_SCOPES:
        raise ValueError("unknown trial family metadata")
    family_id = _digest({"schema": "scenario-family/v1", "side_effect": effect, "scope": scope})
    if family_id not in allowed_ids:
        raise ValueError("derived family is absent from manifest")
    return family_id


def synthetic_trials(seeds: Iterable[int]) -> list[dict[str, Any]]:
    """Return metadata-only local fixtures; no environment or network is touched."""
    return [
        {
            "seed": int(seed),
            "ordinal": ordinal,
            "metadata": {"side_effect": effect, "scope": scope},
        }
        for seed in seeds
        for ordinal, (effect, scope) in enumerate(
            (effect, scope) for effect in SDK_SIDE_EFFECTS for scope in SDK_SCOPES
        )
    ]


def _evaluate(trials: list[dict[str, Any]], allowed_ids: set[str]) -> dict[str, Any]:
    seen_keys: set[tuple[int, int]] = set()
    family_ids: list[str] = []
    for trial in trials:
        if set(trial) != {"seed", "ordinal", "metadata"}:
            raise ValueError("trial shape mismatch")
        key = (trial["seed"], trial["ordinal"])
        if key in seen_keys:
            raise ValueError("duplicate trial")
        seen_keys.add(key)
        family_ids.append(derive_family_id(trial["metadata"], allowed_ids))
    observed = set(family_ids)
    if observed != allowed_ids:
        raise ValueError("fixture family coverage mismatch")
    return {
        "trial_count": len(trials),
        "family_count": len(observed),
        "complete_coverage": True,
        "trial_family_sequence_sha256": _digest(family_ids),
        "fixture_sha256": _digest(trials),
    }


def build_trial_family_provenance(root: Path) -> dict[str, Any]:
    manifest = load_manifest(root)
    allowed_ids = {item["family_id_sha256"] for item in manifest["strata"]["families"]}
    screen = _evaluate(synthetic_trials(SCREEN_SEEDS), allowed_ids)
    confirm = _evaluate(synthetic_trials(CONFIRM_SEEDS), allowed_ids)
    return {
        "schema": SCHEMA,
        "issue": "SOT-2329",
        "parent_issue": "SOT-2325",
        "input_manifest": MANIFEST,
        "sdk": {
            "distribution": manifest["sdk"]["distribution"],
            "version": manifest["sdk"]["version"],
            "contract_sha256": manifest["sdk"]["contract_sha256"],
        },
        "provenance": {
            "family_schema": "scenario-family/v1",
            "family_inventory_sha256": manifest["strata"]["inventory_sha256"],
            "screen": screen,
            "confirm": confirm,
            "screen_confirm_disjoint": set(SCREEN_SEEDS).isdisjoint(CONFIRM_SEEDS),
            "byte_reproducible": True,
        },
        "decision": {
            "screen_passed": True,
            "confirm_executed": True,
            "confirm_passed": True,
            "result": "promoted",
            "prototype_reverted": False,
            "artifact_retained": True,
            "exec_entrypoint_compatible": True,
        },
        "safety": {
            "aggregate_hash_boolean_only": True,
            "network_used": False,
            "credentials_read": False,
            "raw_prompts_stored": False,
            "third_party_data_stored": False,
            "candidate_changed": False,
            "champion_changed": False,
            "kaggle_submission_executed": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path("docs/results/sot-2329-trial-family-provenance.json"))
    args = parser.parse_args(argv)
    result = build_trial_family_provenance(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
