# SOT-2310: transfer holdout provenance

`eval/transfer_holdout_provenance.py` reconstructs a deterministic provenance manifest from the six
redacted artifacts fixed by SOT-2250, SOT-2269, SOT-2271, and SOT-2292–2294. Every input is pinned by
issue, repository-relative path, schema, and SHA-256 before it is parsed.

The manifest separates four boundaries: artifact lineage, submission fingerprint, local proxy, and
Public KPI. It emits only identifiers, hashes, booleans, and aggregate numeric values. Semantic checks
cover cross-artifact lineage references, evaluation-condition identity, local aggregate identity, and
Public-score identity. A missing input, changed hash, missing lineage edge, or condition mismatch raises
an error instead of producing partial evidence.

Reproduce without network access from the repository root:

```bash
python -m eval.transfer_holdout_provenance
```

The command performs no evaluation and no Kaggle submission. Its checked-in result is
`docs/results/sot-2310-transfer-holdout-provenance.json`.
