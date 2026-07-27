# agent-security-gpt

Attack-only entry for Kaggle AI Agent Security (Multi-Step Tool Attacks).

## Starter champion

[`attack.py`](attack.py) implements the competition contract directly:
`AttackAlgorithm.run(env, config) -> list[AttackCandidate]`. The starter emits one deterministic
three-message chain which discovers tools, retrieves hidden configuration, and requests verbatim
exfiltration. It is intentionally simple; its purpose is to provide a valid, measurable champion
before testing stronger multi-step attacks.

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

The recorded starter baseline is `docs/results/starter-screen.json`. It has one valid candidate,
three messages, 66.7% case coverage, and one output fingerprint across all three seeds. The uncovered
external-handoff case leaves measurable room for a challenger.

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
