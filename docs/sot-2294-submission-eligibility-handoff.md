# SOT-2294 cycle-four submission eligibility handoff

The checked-in handoff combines the terminal, redacted results from SOT-2292 and SOT-2293 without
running a candidate or a Kaggle submission. `eval.submission_eligibility_handoff` pins each child
artifact by issue, schema, path, and SHA-256, then verifies the retained champion against `attack.py`.

## Decision

- Candidate SHA: none (`eligible_candidate_count=0` in SOT-2293).
- Champion SHA: `6b1e7d8129bfbcc0ed61484e337cdb537ac743faef650b876446cfd957d0f6f0`.
- Current and previous submission fingerprint:
  `sha256:ca069ff7236374f378359d906b932e843b88b92155d670a4817b3cd3d80693f7`.
- Promotion: false.
- Submission eligible: false.
- Reasons: no fixed eligible candidate, no promotion, and no new artifact fingerprint.

Screen-to-confirm and exec compatibility are explicitly not applicable because no candidate was
eligible or promoted. The inherited non-promotion contract remains `revert_candidate_code` plus
`record_result_in_docs`; the champion is unchanged. Only parent SOT-2291 may use the control-plane
fingerprint gate, and this child did not submit anything.

## Reproduce

```bash
python3 -m eval.submission_eligibility_handoff \
  --request docs/results/sot-2294-handoff-input.json \
  --output /tmp/sot-2294-submission-handoff.json
diff -u docs/results/sot-2294-submission-handoff.json /tmp/sot-2294-submission-handoff.json
pytest -q tests/test_submission_eligibility_handoff.py
```

The machine-readable result is
[`docs/results/sot-2294-submission-handoff.json`](results/sot-2294-submission-handoff.json).
