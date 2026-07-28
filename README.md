# agent-security-gpt

Attack-only entry for Kaggle AI Agent Security (Multi-Step Tool Attacks).

## Champion

[`attack.py`](attack.py) implements the competition contract directly:
`AttackAlgorithm.run(env, config) -> list[AttackCandidate]`. SOT-2027 promoted the
`context_conditioned_portfolio` candidate. It deterministically selects independent chains for
available tool metadata, prior conversation/tool state, and external handoff information. Selection
is capped at three candidates and exact chains are de-duplicated. When none of those context fields
is available, it returns the previous four-message champion unchanged.

## Reproducible local evaluation

The versioned fixtures in `eval/cases.json` pass three distinct runtime contexts to every algorithm:
tool metadata/argument schema, prior conversation/tool state, and an external handoff destination.
For each context the evaluator records weighted attack-surface coverage, candidate count, pairwise
candidate overlap, determinism, and latency. Candidate count is diagnostic only: adding duplicate
candidates cannot improve the promotion decision. Run the champion over the fixed screen seeds:

```bash
python3 -m eval.run --stage screen --seeds 11,29,47 \
  --output docs/results/starter-screen.json
```

Run it again with the same arguments and compare KPI values and output fingerprints. Wall-clock
latency is diagnostic and is excluded from the reproducibility assertion.

The current champion baseline is `docs/results/context-aware-champion-screen.json`. It records the
full v2 result schema, fixture IDs, per-context covered surfaces, and one stable output fingerprint
across all three screen seeds.

## SOT-2079 promotion

`docs/results/sot-2079-context-portfolio-gate.json` compares the previous
`tool_argument_handoff` champion and the context-conditioned portfolio under identical fixtures.
The record includes both artifact SHA-256 values, per-context candidate fingerprints, screen seeds,
and independent confirm seeds. The portfolio reached mean/minimum context coverage `1.0/1.0`
without duplicate candidates and passed both stages, so `attack.py` was updated to the promoted
portfolio. `docs/results/sot-2079-champion-screen.json` is its post-promotion baseline.

The released `aicomp-sdk` constructor contract is verified locally. The promotion record retains
`run_kaggle_proof` as the next external proof action; SOT-2080 owns packaging and the Kaggle run, so
this repository does not claim an unperformed competition submission.

## SOT-2027 comparison

Three independently implemented candidates live under `experiments/`: a single-message control,
a staged tool-context chain, and a tool-argument/external-handoff chain. Their gate records are in
`docs/results/sot-2027/`. Each record includes the exact screen seeds `11,29,47`; candidates that
strictly beat the starter then use independent confirm seeds `101,131,173,211,257`.

Only `tool_argument_handoff` covered all three weighted cases and passed confirm, so it replaced the
starter in production. The other candidates remain experiment fixtures and documented results, not
production branches. `tests/test_attack_harness.py` checks the released SDK factory contract and its
constructor fallback. The promoted champion is therefore ready for the Kaggle proof tracked by
SOT-2028; this issue does not claim a Kaggle submission.

Reproduce the comparison from the pre-promotion commit by running:

```bash
python3 -m eval.gate --champion experiments/starter_baseline.py \
  --candidate experiments/single_message.py \
  --output docs/results/sot-2027/single-message.json
python3 -m eval.gate --champion experiments/starter_baseline.py \
  --candidate experiments/staged_tool_context.py \
  --output docs/results/sot-2027/staged-tool-context.json
python3 -m eval.gate --champion experiments/starter_baseline.py \
  --candidate experiments/tool_argument_handoff.py \
  --output docs/results/sot-2027/tool-argument-handoff.json
```

## Candidate promotion gate

Candidate changes stay outside `attack.py` until promotion:

```bash
python3 -m eval.gate --candidate experiments/challenger.py \
  --output docs/results/challenger-gate.json
```

The gate reads screen seeds `11,29,47` and disjoint confirm seeds `101,131,173,211,257` from the
fixture document. Both stages compare champion and candidate under exactly the same contexts and seeds.
A stage passes only when output is deterministic and either (a) minimum context coverage strictly
improves without mean coverage regression, or (b) coverage does not regress while mean pairwise
candidate overlap strictly decreases. The complete criteria are emitted into every gate result.

- Rejection emits ordered actions `revert_candidate_code` then `record_result_in_docs`. Keep
  `attack.py` unchanged, revert the experimental candidate, and commit the gate JSON/rationale.
- Promotion emits `verify_exec_compatibility`, `run_kaggle_proof`, then `replace_champion`.
  Verify the real SDK/competition exec contract before the Kaggle proof; only after both succeed
  should the challenger replace `attack.py`.

Run local checks with:

```bash
python3 -m pytest
python3 -m compileall -q attack.py eval tests
```
