# SOT-2323 stratified oracle submission handoff

The checked-in handoff combines terminal SOT-2321 and SOT-2322 artifacts after pinning each by issue,
path, schema, and SHA-256. It is deterministic and fail closed: a nonterminal prerequisite, identity or
SHA mismatch, invalid promotion evidence, champion mismatch, or incomplete fingerprint prevents handoff
generation.

The oracle result is **inconclusive**, not promoted. The aggregate screen passed at `2/3`, but no retained
trial had a manifest-member scenario-family hash; stratified screening could not execute and confirm was
therefore not consumed. Candidate code was reverted, the champion remains SHA-256
`6b1e7d8129bfbcc0ed61484e337cdb537ac743faef650b876446cfd957d0f6f0`, and the current artifact
fingerprint equals the previous submission fingerprint. Consequently `new_artifact=false` and
`submission_eligible=false`.

Only parent SOT-2317 owns any later submission decision. SOT-2323 does not permit wrapper execution and
does not invoke Kaggle CLI/API. The artifacts contain only aggregate values, booleans, hashes, schemas,
paths, and nulls; generation requires no network access.

## Reproduce

```bash
PYTHONPATH=/path/to/repo python -m eval.stratified_oracle_handoff \
  --root /path/to/repo \
  --request /path/to/repo/docs/results/sot-2323-handoff-input.json \
  --output /tmp/sot-2323-submission-handoff.json
cmp /tmp/sot-2323-submission-handoff.json \
  /path/to/repo/docs/results/sot-2323-submission-handoff.json
```
