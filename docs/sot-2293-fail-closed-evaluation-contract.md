# SOT-2293: fail-closed oracle-drift evaluation contract

`eval/oracle_drift_contract.py` accepts only candidate artifacts with a stable ID, a lowercase
SHA-256, and the complete evaluation conditions pinned by SOT-2292. The three SOT-2270 axes remain
ineligible because they are `implemented:false` and have no new evidence; no candidate was rebuilt or
evaluated.

Local proxy and Public KPI are separate records. A candidate can be promoted only when both pass,
screen and confirm use the same immutable candidate under identical conditions and disjoint non-empty
seed sets, and exec compatibility passes. A non-promotion is invalid unless candidate code is reverted
and the result is recorded in docs. Thus local success with Public `0.000` fails closed.

The reproducible decision is `docs/results/sot-2293-promotion-decision.json`. It records zero eligible
candidates, no retained candidate code, and required revert/docs actions. No Kaggle submission was run.

Reproduce with:

```bash
.venv/bin/python -m eval.oracle_drift_contract \
  --request docs/results/sot-2293-evaluation-request.json \
  --output /tmp/sot-2293-decision.json
diff -u docs/results/sot-2293-promotion-decision.json /tmp/sot-2293-decision.json
```
