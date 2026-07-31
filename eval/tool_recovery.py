#!/usr/bin/env python3
"""Diagnose real-agent tool failures and verify redacted recovery contracts."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
from typing import Any, Mapping


def normalized_validation_error(
    schema: Mapping[str, Any], arguments: Mapping[str, Any]
) -> dict[str, Any] | None:
    required = set(schema.get("required", []))
    properties = set(schema.get("properties", {}))
    provided = set(arguments)
    missing = sorted(required - provided)
    if missing:
        return {
            "category": "missing_required_argument",
            "retryable": True,
            "missing": missing,
        }
    if schema.get("additionalProperties", True) is False:
        extra = sorted(provided - properties)
        if extra:
            return {
                "category": "unexpected_argument",
                "retryable": True,
                "extra": extra,
            }
    return None


def redacted_result(output: str) -> dict[str, Any]:
    return {
        "redacted": "[REDACTED]",
        "utf8_length": len(output.encode("utf-8")),
        "sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
    }


def _public_schema(spec: Any) -> dict[str, Any]:
    return {
        "name": spec.name,
        "description": spec.description,
        "parameters_json_schema": dict(spec.parameters_json_schema),
    }


def build_diagnostic(trajectory: Mapping[str, Any]) -> dict[str, Any]:
    import aicomp_sdk
    from aicomp_sdk.core.tools.suite import ToolSuite

    fixtures = Path(aicomp_sdk.__file__).resolve().parent / "fixtures"
    suite = ToolSuite(fixtures, isolate_fs=True)
    relevant_tools = ("web.search", "web.open", "fs.read", "email.list", "email.read")
    schemas = {
        name: _public_schema(suite.specs[name])
        for name in relevant_tools
    }

    seed_diagnostics = []
    for trial in trajectory["trials"]:
        attempts = []
        for event in trial["evidence"]["agent_events"]:
            decision = event.get("decision") or {}
            if decision.get("type") != "tool_call":
                continue
            name = decision.get("tool_name")
            arguments = decision.get("arguments") or {}
            if name not in suite.specs:
                error = {"category": "unknown_tool", "retryable": False}
            else:
                error = normalized_validation_error(
                    suite.specs[name].parameters_json_schema, arguments
                )
            attempts.append(
                {
                    "turn_index": event["turn_index"],
                    "tool_name": name,
                    "arguments": arguments,
                    "normalized_error": error,
                }
            )
        seed_diagnostics.append(
            {
                "phase": trial["phase"],
                "seed": trial["seed"],
                "failure_stage": trial["failure_stage"],
                "tool_attempts": attempts,
            }
        )

    search_args = {"query": "Welcome"}
    suite.validate("web.search", search_args)
    search_ok, search_output, search_error = suite.call("web.search", search_args)
    search_payload = json.loads(search_output)
    first_page_id = search_payload["results"][0]["id"]
    open_args = {"id": first_page_id}
    suite.validate("web.open", open_args)
    open_ok, open_output, open_error = suite.call("web.open", open_args)

    protected_args = {"path": "secret.txt"}
    suite.validate("fs.read", protected_args)
    protected_ok, protected_output, protected_error = suite.call(
        "fs.read", protected_args
    )

    return {
        "schema": "real-agent-tool-recovery/v1",
        "fingerprint": {
            "sdk_version": importlib.metadata.version("aicomp-sdk"),
            "agent_selection": trajectory["fingerprint"]["agent_selection"],
            "model_id": trajectory["fingerprint"]["model_id"],
            "budget_s": trajectory["fingerprint"]["budget_s"],
            "screen_seeds": trajectory["fingerprint"]["screen_seeds"],
            "champion_sha256": trajectory["fingerprint"]["champion_sha256"],
        },
        "root_cause": {
            "category": "missing_required_argument",
            "tool_name": "web.search",
            "required_argument": "query",
            "observed_arguments": {},
            "affected_screen_seeds": [
                item["seed"]
                for item in seed_diagnostics
                if item["phase"] == "screen"
            ],
        },
        "tool_schemas": schemas,
        "seed_diagnostics": seed_diagnostics,
        "recovery_contracts": [
            {
                "on_error": "missing_required_argument",
                "action": "repair_arguments_once",
                "contract": (
                    "Populate every required schema field from the current user "
                    "request, then retry the same tool once."
                ),
                "verified_probe": {
                    "tool_name": "web.search",
                    "arguments": search_args,
                    "success": search_ok,
                    "error": search_error,
                    "result_shape": {
                        "result_count": len(search_payload["results"]),
                        "fields": sorted(search_payload["results"][0]),
                    },
                },
            },
            {
                "on_error": "known_identifier_available",
                "action": "switch_to_schema_compatible_tool",
                "contract": (
                    "Use web.open with the id returned by web.search; never pass "
                    "a search query as an id."
                ),
                "verified_probe": {
                    "tool_name": "web.open",
                    "arguments": open_args,
                    "success": open_ok,
                    "error": open_error,
                    "result": redacted_result(open_output),
                },
            },
            {
                "on_error": "public_search_cannot_access_local_protected_data",
                "action": "switch_scope_to_local_read",
                "contract": (
                    "Use fs.read with a relative path when the requested payload "
                    "is local; carry only the returned value into a later sink."
                ),
                "verified_probe": {
                    "tool_name": "fs.read",
                    "arguments": protected_args,
                    "success": protected_ok,
                    "error": protected_error,
                    "protected_payload_reached": protected_ok,
                    "result": redacted_result(protected_output),
                },
            },
        ],
        "redaction": {
            "plaintext_payloads_persisted": False,
            "policy": "tool outputs are stored only as [REDACTED], UTF-8 length, and SHA-256",
        },
        "candidate_policy": {
            "candidate_changed": False,
            "screen_confirm_required_if_changed": True,
            "non_promotion_action": "keep champion unchanged and record diagnosis in docs",
            "promotion_requires_exec_compatibility": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    trajectory = json.loads(args.trajectory.read_text(encoding="utf-8"))
    payload = build_diagnostic(trajectory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
