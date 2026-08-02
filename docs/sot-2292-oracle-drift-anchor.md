# SOT-2292: fixed-artifact oracle-drift anchor

This diagnostic replays no attack and evaluates no candidate. It reads only three already-redacted,
repository-local artifacts. `eval/oracle_drift_anchor.py` pins each input by issue ID, schema, path,
and SHA-256 before parsing it, then fails closed if identity, lineage, or the recorded evaluation
conditions disagree.

The reproduced result is `docs/results/sot-2292-oracle-drift-anchor.json`: the identical retained
artifact succeeded at the local breach boundary in 4 of 6 preserved trials (0.6667 aggregate rate),
while its recorded Public score is 0.000. This is evidence of an oracle/transfer mismatch; it does not
claim equivalence with the hidden grader or reveal hidden behavior.

The output contains only IDs, paths, schemas, hashes, public evaluation configuration, aggregate
counts/rates, and booleans. It stores no trial payload, fixture value, credential, attack procedure,
or candidate code. Generation requires no network access. The champion is unchanged, no candidate is
promoted, screen→confirm is N/A, and no Kaggle submission is executed.

Reproduce from the repository root:

```bash
python -m eval.oracle_drift_anchor
```
