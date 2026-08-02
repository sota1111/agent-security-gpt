# SOT-2331 provenance oracle parent handoff

The handoff pins terminal SOT-2329 and SOT-2330 artifacts by issue, schema, path, and SHA-256. The
SOT-2330 oracle reference is also checked against SOT-2329's recorded terminal result. Any nonterminal
child, SHA/schema mismatch, unsafe artifact, uncertain non-fail-closed result, or unreverted prototype
stops generation.

The result is **inconclusive (fail closed)**. Provenance covered 30/30 fixed families, but the pinned
input supplied outcomes for 0/30 families, so worst-stratum screening could not resolve and confirm was
not consumed. The parent fixed no candidate ID/SHA/evaluation-condition tuple, the prototype was
reverted, champion `attack.py` remains SHA-256
`6b1e7d8129bfbcc0ed61484e337cdb537ac743faef650b876446cfd957d0f6f0`, and the current submission
fingerprint equals the previous submission fingerprint. Accordingly `promotion=false`,
`new_artifact=false`, `fingerprint_changed=false`, and `submission_eligible=false` are recorded as
independent fields.

Only parent SOT-2325 owns any later submission. This child disables wrapper execution and did not run a
Kaggle CLI/API. The artifact contains only aggregate values, hashes, booleans, identifiers, schemas,
paths, and nulls.

## Reproduce

```bash
PYTHONPATH=. .venv/bin/python -m eval.provenance_oracle_handoff \
  --root . \
  --request docs/results/sot-2331-handoff-input.json \
  --output /tmp/sot-2331-submission-handoff.json
cmp /tmp/sot-2331-submission-handoff.json docs/results/sot-2331-submission-handoff.json
```
