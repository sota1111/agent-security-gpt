# SOT-2312 transfer-aware submission handoff

`docs/results/sot-2312-submission-handoff.json` is the deterministic, fail-closed handoff for cycle 5. It pins the terminal SOT-2310 provenance manifest and SOT-2311 promotion decision by issue, path, schema, and SHA-256.

The checked-in decision is intentionally submission-ineligible: no parent-fixed candidate was eligible, no promotion occurred, and the current champion fingerprint is byte-identical to the previous submitted fingerprint. Therefore there is no new artifact; this outcome must not be counted as a successful submission.

Only parent issue SOT-2309 may execute a later submission wrapper after receiving an eligible handoff. SOT-2312 neither permits wrapper execution nor invokes Kaggle CLI/API.

Regenerate deterministically:

```bash
python -m eval.transfer_submission_handoff \
  --request docs/results/sot-2312-handoff-input.json \
  --output /tmp/sot-2312-submission-handoff.json
cmp /tmp/sot-2312-submission-handoff.json docs/results/sot-2312-submission-handoff.json
```
