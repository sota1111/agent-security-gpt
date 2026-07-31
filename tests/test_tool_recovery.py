from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from eval.tool_recovery import (
    normalized_validation_error,
    redacted_result,
)


def test_normalizes_missing_and_extra_arguments() -> None:
    schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
        "additionalProperties": False,
    }
    assert normalized_validation_error(schema, {}) == {
        "category": "missing_required_argument",
        "retryable": True,
        "missing": ["query"],
    }
    assert normalized_validation_error(schema, {"query": "x", "id": "y"}) == {
        "category": "unexpected_argument",
        "retryable": True,
        "extra": ["id"],
    }
    assert normalized_validation_error(schema, {"query": "x"}) is None


def test_redacted_result_never_keeps_plaintext() -> None:
    secret = "synthetic-secret-value"
    result = redacted_result(secret)
    assert secret not in json.dumps(result)
    assert result["redacted"] == "[REDACTED]"
    assert result["utf8_length"] == len(secret)


def test_diagnostic_proves_recovery_without_persisting_payload(
    tmp_path: Path,
) -> None:
    trajectory_path = Path(
        "docs/results/sot-2152-real-agent-failure-trajectories.json"
    )
    output = tmp_path / "diagnostic.json"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "eval.tool_recovery",
            "--trajectory",
            str(trajectory_path),
            "--output",
            str(output),
        ],
        check=True,
    )
    diagnostic = json.loads(output.read_text(encoding="utf-8"))
    serialized = json.dumps(diagnostic)

    assert diagnostic["root_cause"]["affected_screen_seeds"] == [11, 29, 47]
    assert diagnostic["tool_schemas"]["web.search"]["parameters_json_schema"][
        "required"
    ] == ["query"]
    probes = [
        contract["verified_probe"]
        for contract in diagnostic["recovery_contracts"]
    ]
    assert all(probe["success"] for probe in probes)
    assert probes[-1]["protected_payload_reached"] is True
    assert diagnostic["redaction"]["plaintext_payloads_persisted"] is False

    assert "super_secret_" not in serialized
    assert diagnostic["redaction"]["plaintext_payloads_persisted"] is False
