# SOT-2311: transfer-aware promotion contract

`eval.transfer_promotion_contract` pins the SOT-2310 provenance manifest by identity, schema, and
SHA-256 before it considers a candidate. A candidate is eligible only when the parent fixed its ID,
artifact hash, fingerprint, and evaluation-condition hash. The current parent fixed no variant, so the
checked-in request has zero eligible candidates and no candidate implementation was created.

For an eligible candidate, screen, independent confirm, exec compatibility, and transfer evidence must
all carry the same fixed identity and conditions. Screen and confirm seeds must be non-empty and
disjoint. Local success cannot promote without every other gate, and a failed gate requires both the
candidate code to be reverted and the result to be recorded in the experiment ledger. A candidate with
the champion artifact or fingerprint is excluded.

Reproduce the aggregate/hash/boolean-only decision without network access:

```bash
python -m eval.transfer_promotion_contract \
  --request docs/results/sot-2311-evaluation-request.json \
  --output docs/results/sot-2311-promotion-decision.json
```

This command performs no candidate evaluation and no Kaggle submission.
