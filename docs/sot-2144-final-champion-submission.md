# SOT-2144 final-champion exec-compat & Kaggle submission

The machine-readable record is
[`docs/results/sot-2144-kaggle-proof.json`](results/sot-2144-kaggle-proof.json).

## Champion identity (hash / commit / logic)

`attack.py` is byte-identical to the champion promoted at SOT-2079 and submitted at
SOT-2080. No candidate was promoted by the SOT-2142 real-agent transfer screen or the
SOT-2143 confirm, so the final champion is unchanged.

| Artifact | sha256 |
| --- | --- |
| `attack.py` | `6d480375c3b75bc2b650be6a77a3ca9b97308bfb424f2cdd68c2b9c624bdb039` |
| kernel embedded payload (`kaggle/kernel/submit.py`) | `6d480375…` (byte-identical, verified) |
| kernel `CHAMPION_SHA256` | `6d480375…` (matches) |
| promotion commit (SOT-2079) | `925fb85b19d7d6ea5d150131ac349da031a08aaa` |

The payload-identity check (base64-decode the kernel payload, compare bytes and sha256 to
`attack.py`) was re-verified in the control-plane devcontainer this cycle and passes.

## exec-compatibility

`scripts/test_exec_compat.py` and the real-agent tests import `aicomp-sdk`, which is
installed only by the Kaggle competition runtime and cannot be installed in this offline,
PEP-668-managed devcontainer. The authoritative full exec-compatibility PASS (exec, no
`__file__`/`__name__`, changed cwd, internet disabled) was recorded at SOT-2080
([`docs/results/sot-2080-kaggle-proof.json`](results/sot-2080-kaggle-proof.json)) and
remains valid because the champion bytes are unchanged. Only the SDK-independent
payload-identity portion was re-verified locally.

## Kaggle submission

The champion's existing submission is kernel `sota1111/agent-security-gpt-champion`
version 2, ref **`55051758`**, status **pending**, public score **0.000**
(`docs/kaggle-ranking-history.md`, 2026-07-28 snapshot).

No new submission was performed this cycle:

1. The champion is byte-identical to that submission, so a new kernel version would be an
   exact duplicate.
2. The Kaggle CLI is unauthenticated in this control-plane devcontainer, so a fresh kernel
   push and score query cannot be performed here.

## Score-0 divergence → next-cycle material

The local real-agent SDK evaluation (agent `gemma`, model `Qwen/Qwen2.5-0.5B-Instruct`,
30 s budget, screen seed 11 / confirm seeds 101,131) reports **breach success rate 0.0**
and **objective achievement rate 0.0** (SOT-2141 baseline, SOT-2142 champion). This
**agrees** with the Kaggle public score 0.000, so there is no local-vs-Kaggle divergence to
explain.

The standing gap is **proxy-vs-real**: the fixed-fixture keyword-proxy coverage is 1.0
while the real-agent breach rate is 0.0 (`transfer_gap.proxy_coverage_minus_breach_rate =
1.0` in SOT-2141). Cycle 5 should therefore target genuinely transferable real-agent
breaches rather than deterministic messages optimised for the keyword proxy.
