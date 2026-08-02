# SOT-2330: provenance-backed stratified oracle decision

## Decision

Result: **inconclusive (fail closed)**. The fixed SOT-2329 artifact establishes deterministic family
identity for all 30 public-contract strata and separate screen/confirm fixtures. It contains metadata
and provenance aggregates, but no pinned per-family oracle outcomes. Family provenance coverage is
therefore `30/30`, while outcome coverage is `0/30`; the worst-stratum value remains unknown rather
than being inferred from the legacy aggregate result (`2/3`).

Because complete outcome coverage and a passing worst-stratum threshold are screen prerequisites,
confirm was not consumed. No candidate variant was present in the parent input, so none was implemented
or evaluated. The evaluation does not claim hidden-grader equivalence.

## Fixed inputs and thresholds

- SOT-2329 terminal artifact: schema `sdk-native-trial-family-provenance/v1`, SHA-256
  `bec47051b4f806c36790a5b4a23cdeb73851411d70545b1bc85c0a4289b9ef5c`, terminal result `promoted`.
- Legacy aggregate evidence: SOT-2269 schema `post-submission-transfer-gap/v1`, SHA-256
  `ddd01bba1fa5c1e91fd4548e10b7ca3b17848f22f96dbc87f5a1a5225c1f8be5`.
- Screen requires exact input identity/schema/SHA/terminal result, `30/30` provenance coverage,
  `30/30` outcome coverage, a defined passing worst stratum, and the pinned aggregate comparison.
- Confirm requires every screen condition and the SOT-2329 disjoint confirm fixture. Since screen did
  not pass, confirm execution is `false`.

The prototype validator exercised input mutation, missing/unknown families, insufficient outcome
coverage, confirm gating, seed disjointness, and deterministic serialization. It was removed after the
non-promotion result, together with its prototype-only tests. The retained machine artifact contains
only identifiers, schemas, paths, hashes, aggregate numbers, booleans, nulls, and an enum reason.

## Verification and safety

- Fixed artifact identities and SHA-256 values: PASS.
- Family coverage and aggregate/worst-stratum separation: PASS (`30/30`, worst stratum `null`).
- Confirm gating: PASS (not executed on incomplete screen evidence).
- Fail-closed mutation/prototype checks: PASS; prototype reverted after the inconclusive result.
- Existing exec compatibility and repository quality gates: PASS.
- Candidate/champion code: unchanged.
- Network, credentials, raw prompts, third-party data, and Kaggle submission: not used.
