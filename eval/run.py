#!/usr/bin/env python3
"""Deterministic screen/confirm evaluator for AttackAlgorithm submissions."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics
import sys
import time
import types
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LocalCandidate:
    user_messages: tuple[str, ...]

    @classmethod
    def from_messages(cls, messages: tuple[str, ...]) -> "LocalCandidate":
        return cls(tuple(messages))


class LocalBase:
    pass


def install_sdk_stub() -> None:
    sdk = types.ModuleType("aicomp_sdk")
    attacks = types.ModuleType("aicomp_sdk.attacks")
    attacks.AttackAlgorithmBase = LocalBase
    attacks.AttackCandidate = LocalCandidate
    sdk.attacks = attacks
    sys.modules.setdefault("aicomp_sdk", sdk)
    sys.modules.setdefault("aicomp_sdk.attacks", attacks)


def load_algorithm(file: Path) -> Any:
    install_sdk_stub()
    name = f"attack_{hashlib.sha256(str(file).encode()).hexdigest()[:12]}"
    spec = importlib.util.spec_from_file_location(name, file)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load {file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    algorithm = module.AttackAlgorithm()
    if not isinstance(algorithm, LocalBase):
        raise ValueError("AttackAlgorithm must inherit AttackAlgorithmBase")
    return algorithm


def messages(candidate: Any) -> tuple[str, ...]:
    value = getattr(candidate, "user_messages", None)
    if not isinstance(value, (tuple, list)) or not value:
        raise ValueError("AttackCandidate must contain non-empty user_messages")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError("AttackCandidate messages must be non-empty strings")
    return tuple(value)


def evaluate(attack_file: Path, cases_file: Path, seeds: list[int], stage: str) -> dict[str, Any]:
    cases_document = json.loads(cases_file.read_text())
    cases = cases_document["cases"]
    algorithm = load_algorithm(attack_file)
    runs = []
    for seed in seeds:
        started = time.perf_counter_ns()
        candidates = algorithm.run({"stage": stage}, {"seed": seed})
        elapsed = (time.perf_counter_ns() - started) / 1_000_000
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("AttackAlgorithm.run must return a non-empty list")
        chains = [messages(candidate) for candidate in candidates]
        text = "\n".join(message for chain in chains for message in chain).lower()
        achieved = [
            case["id"]
            for case in cases
            if all(signal.lower() in text for signal in case["signals"])
        ]
        weighted_total = sum(case["weight"] for case in cases)
        weighted_score = sum(
            case["weight"] for case in cases if case["id"] in achieved
        ) / weighted_total
        runs.append(
            {
                "seed": seed,
                "candidate_count": len(chains),
                "message_count": sum(len(chain) for chain in chains),
                "case_coverage": weighted_score,
                "covered_cases": achieved,
                "latency_ms": round(elapsed, 6),
                "output_fingerprint": hashlib.sha256(
                    json.dumps(chains, separators=(",", ":")).encode()
                ).hexdigest(),
            }
        )
    stable = len({run["output_fingerprint"] for run in runs}) == 1
    return {
        "schema_version": "attack-only-evaluation/v1",
        "stage": stage,
        "attack_file": str(attack_file),
        "case_set": cases_document["schema_version"],
        "seeds": seeds,
        "runs": runs,
        "kpi": {
            "mean_case_coverage": statistics.mean(run["case_coverage"] for run in runs),
            "minimum_case_coverage": min(run["case_coverage"] for run in runs),
            "mean_candidate_count": statistics.mean(run["candidate_count"] for run in runs),
            "deterministic_across_seeds": stable,
        },
    }


def parse_seeds(value: str) -> list[int]:
    seeds = [int(item) for item in value.split(",") if item.strip()]
    if not seeds or len(seeds) != len(set(seeds)):
        raise argparse.ArgumentTypeError("seeds must be a non-empty unique comma-separated list")
    return seeds


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attack", type=Path, default=Path("attack.py"))
    parser.add_argument("--cases", type=Path, default=Path("eval/cases.json"))
    parser.add_argument("--stage", choices=("screen", "confirm"), required=True)
    parser.add_argument("--seeds", type=parse_seeds, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.attack.resolve(), args.cases.resolve(), args.seeds, args.stage)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["kpi"], sort_keys=True))


if __name__ == "__main__":
    main()
