# agent-security-gpt

Attack-only entry for Kaggle AI Agent Security (Multi-Step Tool Attacks).

## Champion

[`attack.py`](attack.py) implements the competition contract directly:
`AttackAlgorithm.run(env, config) -> list[AttackCandidate]`. SOT-2027 promoted the
`tool_argument_handoff` candidate: a deterministic four-message chain that discovers tools, uses
tool-argument context to retrieve hidden configuration, preserves it verbatim, and requests an
external handoff.

## Reproducible local evaluation

The versioned cases in `eval/cases.json` measure candidate validity, message/candidate counts,
determinism, latency, and coverage of three starter attack objectives. Run the starter over the
fixed screen seeds:

```bash
python3 -m eval.run --stage screen --seeds 11,29,47 \
  --output docs/results/starter-screen.json
```

Run it again with the same arguments and compare KPI values and output fingerprints. Wall-clock
latency is diagnostic and is excluded from the reproducibility assertion.

The original starter baseline is `docs/results/starter-screen.json`. It has one valid candidate,
three messages, 66.7% case coverage, and one output fingerprint across all three seeds. The uncovered
external-handoff case leaves measurable room for a challenger.

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

The gate first uses screen seeds `11,29,47`. Confirm seeds `101,131,173,211,257` execute only when
the challenger is deterministic and strictly exceeds the champion's minimum case coverage.

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
