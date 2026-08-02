# SOT-2329: SDK-native trial family provenance

`eval.trial_family_provenance` pins the SOT-2321 public-contract manifest by issue, schema, and SHA-256,
then derives each trial's family hash from the official `aicomp-sdk 3.1.2` `ToolSideEffect` and
`ToolScope` metadata. Missing, unknown, extra, duplicate, non-member, or tampered inputs fail closed.

The fixed screen seeds (`1103`, `2207`) and disjoint confirm seeds (`3301`, `4409`) each cover all 30
public contract families. The checked-in artifact contains aggregate counts, hashes, and booleans only;
it stores no raw prompts, credentials, or third-party data and performs no network access.

```bash
.venv/bin/python -m eval.trial_family_provenance
.venv/bin/pytest tests/test_trial_family_provenance.py
```

Screen and confirm passed byte-identically, so the provenance generator and artifact are retained.
`attack.py` and the existing execution entrypoint are unchanged, and no Kaggle submission was run.
