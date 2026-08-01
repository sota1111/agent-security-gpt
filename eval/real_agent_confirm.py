#!/usr/bin/env python3
"""Blind-confirm one screen winner on disjoint official-SDK agent seeds."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
from dataclasses import asdict
from pathlib import Path
from typing import Any

from eval.real_agent import deterministic_projection, load_attack, run_trial, summarize
from eval.real_agent_screen import promotion_decision
from eval.run import parse_seeds


PROMOTION_RULE = (
    "one primary metric must improve over champion and the other must not "
    "regress on disjoint confirm seeds"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_screen_contract(
    screen: dict[str, Any], *, candidate_name: str, candidate: Path, confirm_seeds: list[int]
) -> dict[str, Any]:
    """Reject confirm inputs that are not the unchanged, sole screen winner."""
    screen_seeds = screen["fingerprint"]["screen_seeds"]
    if set(screen_seeds) & set(confirm_seeds):
        raise ValueError("screen and confirm seeds must be disjoint")
    passing = screen["promotion_gate"]["passing_candidates"]
    if passing != [candidate_name]:
        raise ValueError("candidate must be the sole screen-passing target")
    recorded = screen["strategies"][candidate_name]
    actual_sha = _sha256(candidate)
    if recorded["sha256"] != actual_sha:
        raise ValueError("candidate source changed after screen")
    return {
        "seeds": screen_seeds,
        "passing_candidates": passing,
        "candidate_sha256": actual_sha,
    }


def build_payload(
    *,
    screen_path: Path,
    screen: dict[str, Any],
    champion: Path,
    candidate_name: str,
    candidate: Path,
    confirm_seeds: list[int],
    results: list,
    repeats: list,
    agent: str,
    model_path: Path | None,
    model_id: str,
    budget_s: float,
) -> dict[str, Any]:
    screen_contract = validate_screen_contract(
        screen,
        candidate_name=candidate_name,
        candidate=candidate,
        confirm_seeds=confirm_seeds,
    )
    summaries = {
        name: summarize([result for result in results if result.strategy == name])
        for name in ("champion", candidate_name)
    }
    decision = promotion_decision(summaries["champion"], summaries[candidate_name])
    repeat_projections = [deterministic_projection(result) for result in repeats]
    reproducible = repeat_projections[0] == repeat_projections[1]
    promoted = bool(decision["passed"] and reproducible)
    return {
        "schema": "real-agent-candidate-confirm/v1",
        "issue": "SOT-2249",
        "screen": {
            "artifact": str(screen_path),
            "artifact_sha256": _sha256(screen_path),
            **screen_contract,
        },
        "confirm": {
            "scenario": "fresh official-SDK gym environment per strategy/seed",
            "candidate_selected_before_confirm": True,
            "seeds": confirm_seeds,
            "disjoint_from_screen": True,
            "budget_s_per_trial": budget_s,
            "matched_budget": True,
            "summaries": summaries,
            "trials": [asdict(result) for result in results],
        },
        "fingerprint": {
            "agent_selection": agent,
            "model_id": model_id,
            "model_path": str(model_path.resolve()) if model_path else None,
            "environment": "gym",
            "guardrail": "aicomp_sdk.attacks.baselines.guardrail_rules.Guardrail",
            "scoring_path": "aicomp_sdk.evaluation.ops.eval_attack",
            "sdk_version": importlib.metadata.version("aicomp-sdk"),
            "python_version": platform.python_version(),
            "temperature": 0,
            "sampling": False,
            "champion": {"source": str(champion), "sha256": _sha256(champion)},
            "candidate": {"source": str(candidate), "sha256": _sha256(candidate)},
        },
        "promotion_gate": {
            "rule": PROMOTION_RULE,
            "precommitted_before_confirm": True,
            "primary_metrics": ["breach_success_rate", "objective_achievement_rate"],
            "coverage_or_shape_can_promote": False,
            "reproducibility_required": True,
            "decision": decision,
            "promoted": promoted,
            "reason": (
                "confirm primary-KPI gate and fixed-seed reproducibility passed"
                if promoted
                else "confirm primary-KPI improvement did not reproduce or fixed-seed outcomes differed"
            ),
        },
        "reproducibility": {
            "strategy": candidate_name,
            "seed": repeats[0].seed,
            "runs": repeat_projections,
            "deterministic_fields_match": reproducible,
        },
        "redaction": {
            "tool_argument_values_stored": False,
            "tool_result_values_stored": False,
            "fixture_credentials_stored": False,
            "protected_payloads_stored": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen-result", type=Path, required=True)
    parser.add_argument("--champion", type=Path, default=Path("attack.py"))
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--candidate-name", default="protocol-only-context")
    parser.add_argument("--agent", choices=("gemma", "gpt_oss", "openai"), default="gemma")
    parser.add_argument("--model-path", type=Path)
    parser.add_argument("--model-id")
    parser.add_argument("--confirm-seeds", type=parse_seeds, required=True)
    parser.add_argument("--repro-check-seed", type=int, required=True)
    parser.add_argument("--budget", type=float, default=30.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.budget <= 0:
        parser.error("--budget must be positive")
    if args.repro_check_seed not in args.confirm_seeds:
        parser.error("repro-check seed must belong to confirm seeds")

    screen_path = args.screen_result.resolve()
    champion = args.champion.resolve()
    candidate = args.candidate.resolve()
    screen = json.loads(screen_path.read_text(encoding="utf-8"))
    try:
        validate_screen_contract(
            screen,
            candidate_name=args.candidate_name,
            candidate=candidate,
            confirm_seeds=args.confirm_seeds,
        )
    except (KeyError, TypeError, ValueError) as error:
        parser.error(str(error))

    strategies = {
        "champion": load_attack(champion),
        args.candidate_name: load_attack(candidate),
    }
    results = [
        run_trial(
            attack_cls,
            phase="confirm",
            strategy=name,
            agent=args.agent,
            seed=seed,
            budget_s=args.budget,
            model_path=args.model_path,
        )
        for name, attack_cls in strategies.items()
        for seed in args.confirm_seeds
    ]
    repeats = [
        run_trial(
            strategies[args.candidate_name],
            phase="reproducibility",
            strategy=args.candidate_name,
            agent=args.agent,
            seed=args.repro_check_seed,
            budget_s=args.budget,
            model_path=args.model_path,
        )
        for _ in range(2)
    ]
    payload = build_payload(
        screen_path=screen_path,
        screen=screen,
        champion=champion,
        candidate_name=args.candidate_name,
        candidate=candidate,
        confirm_seeds=args.confirm_seeds,
        results=results,
        repeats=repeats,
        agent=args.agent,
        model_path=args.model_path,
        model_id=args.model_id or (args.model_path.name if args.model_path else args.agent),
        budget_s=args.budget,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload["promotion_gate"], sort_keys=True))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
