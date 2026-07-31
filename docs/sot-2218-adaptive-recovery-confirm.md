# SOT-2218 adaptive-recovery independent-confirm decision

## Outcome

No SOT-2217 candidate qualified for independent confirm. The screen compared
the champion and all three candidates under the same official SDK, model,
30-second budget, and seeds `11,29,47`. Every strategy recorded breach success
`0/3` and objective achievement `0/3`; consequently
`passing_candidates` is empty.

Running the candidates again on confirm seeds would violate the inherited
screen-before-confirm gate. The confirm target is therefore explicitly `null`,
the candidate modules remain reverted, and the champion is not promoted or
modified.

## Seed contract

| Stage | Seeds | Status |
| --- | --- | --- |
| screen | `11,29,47` | completed by SOT-2217 |
| confirm | `101,131,173,211,257` | not run; no screen-passing target |

The two configured sets are disjoint. No confirm seed was consumed by the
screen result, and no screen seed is designated for confirm.

## Primary KPI decision

| Strategy | Breach success | Objective achievement | Decision |
| --- | ---: | ---: | --- |
| champion | 0/3 | 0/3 | retained |
| adaptive-search-open | 0/3 | 0/3 | rejected at screen |
| adaptive-local-read | 0/3 | 0/3 | rejected at screen |
| adaptive-search-local-fallback | 0/3 | 0/3 | rejected at screen |

Promotion requires either breach success or objective achievement to improve,
with the other metric not regressing. None improved a primary KPI. Auxiliary
coverage and candidate shape were not used to override the decision.

## Provenance and submission artifact

- Screen evidence:
  [`results/sot-2217-adaptive-tool-recovery-screen.json`](results/sot-2217-adaptive-tool-recovery-screen.json),
  SHA-256 `18253028c396487be6248e95a1703635ad7998b01e6fec763b3ac4865e89dc6d`.
- Machine-readable decision:
  [`results/sot-2218-adaptive-recovery-confirm.json`](results/sot-2218-adaptive-recovery-confirm.json).
- Retained champion and unique latest submission payload: repository-root
  `attack.py`, SHA-256
  `6d480375c3b75bc2b650be6a77a3ca9b97308bfb424f2cdd68c2b9c624bdb039`.
- Candidate source hashes and their reverted status are copied by reference
  into the machine decision from the immutable SOT-2217 screen artifact.

Because the champion bytes did not change, a new exec-compatibility claim is
not a promotion prerequisite for this no-promotion outcome. The existing
champion is nevertheless rechecked by the repository exec-compatibility test
as part of this Issue's verification. SOT-2219 owns final submission-contract
validation and Kaggle submission.
