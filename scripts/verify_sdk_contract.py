#!/usr/bin/env python3
"""Fail fast when the installed competition SDK no longer matches this repository."""

from __future__ import annotations

import importlib.metadata

from aicomp_sdk.attacks import AttackAlgorithmBase, AttackCandidate
from aicomp_sdk.evaluation.ops import eval_attack


MINIMUM_SDK_VERSION = (3, 1, 2)


def version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split(".")[:3])


def main() -> None:
    version = importlib.metadata.version("aicomp-sdk")
    if version_tuple(version) < MINIMUM_SDK_VERSION:
        raise RuntimeError(f"aicomp-sdk {version} is older than required 3.1.2")
    if not callable(getattr(AttackAlgorithmBase, "run", None)):
        raise RuntimeError("AttackAlgorithmBase.run is unavailable")
    if not callable(eval_attack):
        raise RuntimeError("aicomp_sdk.evaluation.ops.eval_attack is unavailable")
    if not (
        callable(getattr(AttackCandidate, "from_messages", None))
        or hasattr(AttackCandidate, "model_fields")
    ):
        raise RuntimeError("AttackCandidate constructor contract is unavailable")
    print(f"official SDK contract PASS: aicomp-sdk {version}")


if __name__ == "__main__":
    main()
