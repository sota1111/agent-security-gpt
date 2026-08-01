# SOT-2219 adaptive-recovery Kaggle submission proof

The machine-readable record is
[`docs/results/sot-2219-kaggle-proof.json`](results/sot-2219-kaggle-proof.json).

## Submission artifact and promotion provenance

SOT-2217 screened three adaptive-recovery candidates against the champion on seeds `11,29,47`.
All candidates tied the champion at breach success `0/3` and objective achievement `0/3`, so none
passed screen. SOT-2218 therefore ran no confirm and retained the existing champion. The unique latest
submission artifact is repository-root `attack.py`:

| Artifact | SHA-256 |
| --- | --- |
| `attack.py` | `6d480375c3b75bc2b650be6a77a3ca9b97308bfb424f2cdd68c2b9c624bdb039` |
| decoded payload in `kaggle/kernel/submit.py` | `6d480375c3b75bc2b650be6a77a3ca9b97308bfb424f2cdd68c2b9c624bdb039` |
| SOT-2217 screen artifact | `18253028c396487be6248e95a1703635ad7998b01e6fec763b3ac4865e89dc6d` |

The candidate hashes, rejected status, unconsumed independent confirm seeds, and retained champion
are recorded in `docs/results/sot-2218-adaptive-recovery-confirm.json`.

## Payload and exec contract

`python scripts/test_exec_compat.py` passed with `aicomp-sdk==3.1.2`. It verified that the embedded
payload equals `attack.py` byte-for-byte, the declared payload hash matches, and the champion executes
without `__file__` or `__name__` from an unrelated working directory while outbound socket connections
are disabled. The resulting algorithm returned three valid candidates.

The live Kaggle kernel `sota1111/agent-security-gpt-champion` was pulled through the authenticated
Kaggle CLI. Its Python source SHA-256 is
`c1b4bdfc060a052e7b85886c492612738591b52b44377b6062ab2ebe28a95af1`, byte-identical to the checked-in
`kaggle/kernel/submit.py`. The live kernel status was `COMPLETE`; metadata confirms private execution,
internet disabled, and the target competition source.

## Submission and ranking observation

At `2026-08-01 00:30 UTC`, the authenticated Kaggle CLI reported:

- latest GPT-lineage submission ref: `55132776`
- description: `auto-improve submit: agent-security-gpt champion [slot:2026-07-31-jst-18]`
- status: `COMPLETE`
- public score: `0.000`
- official team rank: `2,614 / 2,635`

No new kernel version or competition submission was created. The live kernel source and retained
champion are already byte-identical to the checked-in submission payload, and ref `55132776` is the
completed submission for that current GPT champion. Pushing and submitting it again would consume a
submission slot for an exact duplicate without changing the evaluated artifact. This is the explicit
duplicate-submission skip allowed by SOT-2219; the authenticated status, ref, score, and downloadable
leaderboard snapshot make the decision reproducible.
