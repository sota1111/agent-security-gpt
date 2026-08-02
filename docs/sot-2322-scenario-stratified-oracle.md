# SOT-2322 scenario-stratified oracle evaluation

## Decision

Result: **inconclusive (fail closed)**. The pinned aggregate evidence reproduces a screen breach rate of
`2/3`, but none of its redacted trial rows contains a `family_id_sha256` that can be joined to the 30
families in SOT-2321. A seed or the coarse `matched_screen` / `independent_confirm` phase label is not a
scenario-family identity, so the evaluation does not infer or fabricate one.

Consequently, per-stratum numerator/denominator and the worst stratum are unavailable. The legacy
aggregate screen would pass, while the stratified result is unknown; this is recorded as
`unknown_fail_closed`, not as agreement. Confirm seeds are disjoint, but confirm was not consumed because
the stratified screen prerequisite did not pass.

## Fixed inputs

- SOT-2321 terminal manifest: schema `public-contract-scenario-strata-manifest/v1`, SHA-256
  `c6034b582d9567249b7c6416cbe718919c42c4af6482910dac881511e40097ab`.
- Existing redacted evidence: schema `post-submission-transfer-gap/v1`, SHA-256
  `ddd01bba1fa5c1e91fd4548e10b7ca3b17848f22f96dbc87f5a1a5225c1f8be5`.
- Champion: `attack.py`, SHA-256
  `6b1e7d8129bfbcc0ed61484e337cdb537ac743faef650b876446cfd957d0f6f0`.

The machine record contains only aggregate counts, booleans, hashes, paths, schemas, and nulls. The
prototype validator checked all three SHA/schema identities, Public KPI presence, non-empty disjoint
screen/confirm sets, manifest membership, and zero denominators before aggregation. Mutation tests for
the fixed inputs and the current missing-stratum path fail closed. The prototype and its test were
removed after the inconclusive decision, as required for a non-promotion; only documentation and ledger
evidence remain.

## Verification and safety

- Repository preflight / official SDK 3.1.2 contract: PASS.
- Prototype deterministic fail-closed test: PASS; aggregate `2/3`, observed strata `0/30`, confirm not run.
- Full pytest with prototype: 80 passed; after revert: 79 passed.
- Python compileall, arbitrary-CWD offline exec compatibility, restart gate: PASS.
- `attack.py` and candidate/champion code: unchanged; exec-compatible champion SHA confirmed.
- Network access, protected/private payload reads, credential reads, and Kaggle submission: none.

This outcome provides evidence for a later oracle re-anchoring cycle: future retained evaluation rows
must carry a manifest-member `family_id_sha256` at creation time before a stratified screen can run.
