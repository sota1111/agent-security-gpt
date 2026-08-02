# SOT-2321: public-contract scenario strata manifest

`eval/public_contract_strata.py` generates a deterministic inventory from the public `aicomp-sdk
3.1.2` contract. It treats every public `ToolSideEffect` × `ToolScope` pair as one scenario family and
stores only hashes of those definitions. The manifest therefore supplies stable strata identifiers
without reading fixture payloads, protected values, or credentials.

Before producing output, generation verifies each parent-approved repository input by issue, path,
schema, and SHA-256. It also verifies the installed SDK version, the SHA-256 of the four relevant public
contract source files, and the expected enum shape. Any missing file, changed hash, schema mismatch,
version mismatch, or enum change fails closed.

Reproduce from the repository root with outbound networking disabled:

```bash
.venv/bin/python -m eval.public_contract_strata
```

The checked-in result is `docs/results/sot-2321-public-contract-strata.json`. This step creates only the
input manifest for the downstream screen→confirm evaluation. It does not evaluate or change a
candidate/champion and does not submit to Kaggle.
