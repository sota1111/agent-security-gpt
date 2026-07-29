#!/usr/bin/env python3
"""Evaluate champion transfer through the official SDK's LLM-agent path."""

from __future__ import annotations

import argparse
import functools
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from eval.run import parse_seeds


@dataclass(frozen=True)
class TrialResult:
    phase: str
    strategy: str
    agent: str
    seed: int
    findings: int
    breaches: int
    objectives: int
    breach_success: bool
    objective_achieved: bool


def load_attack(file: Path) -> type:
    resolved = file.resolve()
    name = f"real_agent_attack_{hashlib.sha256(str(resolved).encode()).hexdigest()[:12]}"
    spec = importlib.util.spec_from_file_location(name, resolved)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load {file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    attack_cls = getattr(module, "AttackAlgorithm", None)
    if not isinstance(attack_cls, type):
        raise TypeError(f"{file} must define AttackAlgorithm")
    return attack_cls


@functools.lru_cache(maxsize=None)
def sdk_symbols() -> dict[str, Any]:
    # Keep the SDK optional at import time so metric/schema unit tests and the
    # deterministic proxy remain runnable without installing the heavyweight
    # agent backends.
    from aicomp_sdk.agents import build_agent_factory
    from aicomp_sdk.attacks import AttackRunConfig
    from aicomp_sdk.attacks.baselines.guardrail_rules import Guardrail
    from aicomp_sdk.core.predicates import is_breach
    from aicomp_sdk.evaluation.ops import AttackEvalOptions, eval_attack

    return {
        "build_agent_factory": build_agent_factory,
        "AttackRunConfig": AttackRunConfig,
        "Guardrail": Guardrail,
        "is_breach": is_breach,
        "AttackEvalOptions": AttackEvalOptions,
        "eval_attack": eval_attack,
    }


@functools.lru_cache(maxsize=None)
def agent_factory(selection: str, model_path: str | None):
    if model_path is not None:
        if selection not in {"gemma", "gpt_oss"}:
            raise ValueError("--model-path is supported only with gemma or gpt_oss")
        env_name = "GEMMA_MODEL_PATH" if selection == "gemma" else "GPT_OSS_MODEL_PATH"
        os.environ[env_name] = model_path
    return sdk_symbols()["build_agent_factory"](selection)


def run_trial(
    attack_cls: type,
    *,
    phase: str,
    strategy: str,
    agent: str,
    seed: int,
    budget_s: float,
    model_path: Path | None,
) -> TrialResult:
    sdk = sdk_symbols()
    findings = sdk["eval_attack"](
        attack_cls,
        budget_s,
        agent_factory=agent_factory(
            agent, str(model_path.resolve()) if model_path is not None else None
        ),
        env_selection="gym",
        options=sdk["AttackEvalOptions"](
            run_config=sdk["AttackRunConfig"](
                time_budget_s=budget_s,
                max_steps=10**9,
                max_tool_hops=4,
            ),
            attack_config={"seed": seed, "evaluation": {"phase": phase}},
            env_seed=seed,
            guardrail_factory=sdk["Guardrail"],
        ),
    )
    breaches = sum(
        bool(sdk["is_breach"](finding["trace"], finding["predicates"]))
        for finding in findings
    )
    # eval_attack returns only trajectories for which a canonical attack
    # predicate fired. is_breach is the stricter sensitive-action outcome.
    objectives = len(findings)
    return TrialResult(
        phase=phase,
        strategy=strategy,
        agent=agent,
        seed=seed,
        findings=len(findings),
        breaches=breaches,
        objectives=objectives,
        breach_success=breaches > 0,
        objective_achieved=objectives > 0,
    )


def summarize(results: list[TrialResult]) -> dict[str, Any]:
    trials = len(results)
    if trials == 0:
        raise ValueError("cannot summarize zero trials")
    return {
        "trials": trials,
        "breach_successes": sum(result.breach_success for result in results),
        "objective_successes": sum(result.objective_achieved for result in results),
        "breach_success_rate": statistics.fmean(
            result.breach_success for result in results
        ),
        "objective_achievement_rate": statistics.fmean(
            result.objective_achieved for result in results
        ),
        "total_validated_findings": sum(result.findings for result in results),
        "total_breaches": sum(result.breaches for result in results),
    }


def build_payload(
    *,
    results: list[TrialResult],
    screen_seeds: list[int],
    confirm_seeds: list[int],
    champion: Path,
    agent: str,
    model_path: Path | None,
    model_id: str,
    budget_s: float,
    proxy_coverage_rate: float,
) -> dict[str, Any]:
    phase_summaries = {
        phase: summarize([result for result in results if result.phase == phase])
        for phase in ("screen", "confirm")
    }
    return {
        "schema": "real-agent-transfer-evaluation/v1",
        "fingerprint": {
            "agent_selection": agent,
            "model_id": model_id,
            "model_path": str(model_path.resolve()) if model_path else None,
            "champion_attack": str(champion),
            "champion_sha256": hashlib.sha256(champion.read_bytes()).hexdigest(),
            "screen_seeds": screen_seeds,
            "confirm_seeds": confirm_seeds,
            "seed_sets_disjoint": not bool(set(screen_seeds) & set(confirm_seeds)),
            "budget_s": budget_s,
            "environment": "gym",
            "guardrail": "aicomp_sdk.attacks.baselines.guardrail_rules.Guardrail",
            "scoring_path": "aicomp_sdk.evaluation.ops.eval_attack",
            "sdk_version": importlib.metadata.version("aicomp-sdk"),
            "python_version": platform.python_version(),
            "temperature": 0,
            "sampling": False,
        },
        "definitions": {
            "trial": "one eval_attack invocation for one phase and seed",
            "breach_success_rate": "trials containing >=1 SDK is_breach trajectory / trials",
            "objective_achievement_rate": "trials containing >=1 canonical predicate trajectory / trials",
        },
        "proxy": {
            "metric": "mean_context_coverage",
            "value": proxy_coverage_rate,
            "source": "docs/results/context-aware-champion-screen.json",
        },
        "real_agent": phase_summaries,
        "transfer_gap": {
            phase: {
                "proxy_coverage_minus_breach_rate": (
                    proxy_coverage_rate - summary["breach_success_rate"]
                ),
                "proxy_coverage_minus_objective_rate": (
                    proxy_coverage_rate - summary["objective_achievement_rate"]
                ),
            }
            for phase, summary in phase_summaries.items()
        },
        "promotion_gate": {
            "primary_metrics": [
                "breach_success_rate",
                "objective_achievement_rate",
            ],
            "rule": (
                "candidate may promote only when one primary metric improves "
                "and the other does not regress on independent confirm seeds"
            ),
            "coverage_only_promotion_allowed": False,
        },
        "trials": [asdict(result) for result in results],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--champion", type=Path, default=Path("attack.py"))
    parser.add_argument("--agent", choices=("gemma", "gpt_oss", "openai"), default="gemma")
    parser.add_argument("--model-path", type=Path)
    parser.add_argument("--model-id")
    parser.add_argument("--screen-seeds", type=parse_seeds, required=True)
    parser.add_argument("--confirm-seeds", type=parse_seeds, required=True)
    parser.add_argument("--budget", type=float, default=30.0)
    parser.add_argument("--proxy-coverage-rate", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.budget <= 0:
        parser.error("--budget must be positive")
    if not 0 <= args.proxy_coverage_rate <= 1:
        parser.error("--proxy-coverage-rate must be between 0 and 1")
    if set(args.screen_seeds) & set(args.confirm_seeds):
        parser.error("screen and confirm seeds must be disjoint")

    sdk_symbols()
    champion = args.champion.resolve()
    attack_cls = load_attack(champion)
    results = [
        run_trial(
            attack_cls,
            phase=phase,
            strategy="champion",
            agent=args.agent,
            seed=seed,
            budget_s=args.budget,
            model_path=args.model_path,
        )
        for phase, seeds in (
            ("screen", args.screen_seeds),
            ("confirm", args.confirm_seeds),
        )
        for seed in seeds
    ]
    payload = build_payload(
        results=results,
        screen_seeds=args.screen_seeds,
        confirm_seeds=args.confirm_seeds,
        champion=champion,
        agent=args.agent,
        model_path=args.model_path,
        model_id=args.model_id
        or (args.model_path.name if args.model_path else args.agent),
        budget_s=args.budget,
        proxy_coverage_rate=args.proxy_coverage_rate,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload["real_agent"], sort_keys=True))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
