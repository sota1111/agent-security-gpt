# SOT-2271 submission handoff

SOT-2270 found no eligible fixed candidate: all three follow-up axes in the
SOT-2269 artifact are `implemented:false` and have no candidate SHA. No screen
or independent-seed confirm was therefore permitted, no code was promoted, and
the SOT-2249 champion remains the unique submission target.

## Artifact and validation lineage

The selected artifact is repository-root `attack.py`, SHA-256
`6b1e7d8129bfbcc0ed61484e337cdb537ac743faef650b876446cfd957d0f6f0`.
It is the candidate screened by SOT-2248 and promoted on disjoint confirm seeds
by SOT-2249. The exact result paths and hashes, including the later SOT-2269
diagnostic and SOT-2270 non-promotion decision, are recorded in
[`docs/results/sot-2271-submission-handoff.json`](results/sot-2271-submission-handoff.json).

The embedded payload in `kaggle/kernel/submit.py` is byte-identical to
`attack.py`, and its declared champion hash matches. The repository restart
gate passed with `aicomp-sdk 3.1.2`: constructor/SDK loading, arbitrary-CWD
execution, execution without `__file__` or `__name__`, and execution with
outbound socket connections disabled all passed. The algorithm returned one
valid candidate.

## Parent submission contract

Only parent SOT-2266 may execute the submission. From
`/workspaces/ai-dev-control-plane`, after confirming this committed proof still
matches the checked-out champion, run exactly:

```bash
bash scripts/ai/kaggle_targets_submit.sh --competition agent-security --repo agent-security-gpt --execute
```

Required wrapper inputs are registry target `agent-security-gpt`, kernel
`sota1111/agent-security-gpt-champion`, immutable version `2`, and output
`submission.csv`. Their canonical identity
`kaggle-notebook:sota1111/agent-security-gpt-champion@2:submission.csv` hashes
to fingerprint
`sha256:ca069ff7236374f378359d906b932e843b88b92155d670a4817b3cd3d80693f7`.
That fingerprint matches the existing SOT-2250 submission proof. The wrapper
must refresh live history and may safely skip an exact duplicate; this child
does not claim a new submission ref, status, or score.

No Kaggle CLI/API, submission helper, or submit wrapper was invoked by this
issue. Candidate screen/confirm is **N/A** because there was no implemented
candidate and the champion was unchanged.
