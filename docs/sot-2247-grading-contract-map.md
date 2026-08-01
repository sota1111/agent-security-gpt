# SOT-2247 grading contract map

The redacted, machine-readable result is
[`results/sot-2247-grading-contract-map.json`](results/sot-2247-grading-contract-map.json).
It compares the checked-in champion and kernel with the public `aicomp-sdk` 3.1.2
contract without reading fixture payloads or credentials.

## Reproduced contract gaps

Across seeds 11, 29, 101, and 131, the repository's rich mapping fixture selects
three context-specific candidates, while the public SDK-shaped opaque environment
and `AttackRunConfig` select one fallback candidate. The champion treats both
inputs as mappings; the real public inputs are protocol/dataclass objects. The
tool, conversation, and handoff branches exercised by local tests are therefore
unreachable under the public evaluator contract.

The fallback candidate also describes discovery and handoff abstractly. It does
not ground the first action in an exact public tool/schema pair, or connect a
successful protected source result to the exact scored sink argument. Candidate
generation or an objective-like handoff description is not itself a breach: the
canonical evaluator requires a predicate and its corresponding successful
sensitive action on the same replayed trace. These two independently testable
gaps can both produce a zero public score even when local candidate coverage is
high.

## Next screen rules

1. Use only public `AttackEnvProtocol` methods/seed and `AttackRunConfig`
   attributes for context adaptation; do not branch on private mapping keys.
2. Start with one schema-valid action that names an available source tool and
   supplies its required argument shape.
3. Continue the returned source result into the exact scored sink argument, then
   require predicate firing and canonical breach success on the same trace.

These rules are intentionally unimplemented here. A following issue must screen
them and confirm any winner on disjoint seeds before changing `attack.py`. The
current kernel remains byte-identical to the champion and continues to pass the
isolated exec-compatibility check.

## Redaction

The JSON artifact contains SDK version/hash fingerprints, scenario labels,
counts, public contract categories, and SHA-256 identifiers. Target, sink, tool,
and argument identifiers are hashed in the contract inventory. Fixture payloads
and credential files are not read by the diagnostic and no protected value is
stored.
