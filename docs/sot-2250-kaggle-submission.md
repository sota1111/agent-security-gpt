# SOT-2250 Kaggle submission proof

The latest contract-passing artifact is the SOT-2249 promoted champion at repository-root
`attack.py`. Its SHA-256 is
`6b1e7d8129bfbcc0ed61484e337cdb537ac743faef650b876446cfd957d0f6f0`; the candidate source was
committed in `2f53cf33130c9071d4f0a288c2d099306defa92e` and the independent-seed confirmation and promotion
were committed in `3858de032ef3417edd3be002747b7888bead364e`.

The SOT-2248 screen artifact and SOT-2249 confirm artifact are linked, with their exact hashes, in
[`docs/results/sot-2250-kaggle-submission.json`](results/sot-2250-kaggle-submission.json). The confirm
used seeds disjoint from the screen and passed the primary-metric promotion gate.

## Submission contract

The official SDK 3.1.2 contract passed. The kernel payload is byte-identical to `attack.py`, its
declared SHA-256 matches, and it executed from an unrelated working directory with outbound sockets
disabled and without relying on `__file__` or `__name__`. The live kernel status was `COMPLETE`.

Submission was attempted only through the required control-plane wrapper. The wrapper refreshed
Kaggle history and returned the machine-readable skip reason `EXACT_ARTIFACT_DUPLICATE_TODAY`: the
selected artifact fingerprint had already been submitted today. Existing submission `55162752` is
`COMPLETE` with public score `0.000`, so no duplicate submission slot was consumed.

The proof stores only public identifiers, hashes, statuses, and aggregate validation outcomes. It
contains no credentials, secret values, protected payloads, or tool-result contents.
