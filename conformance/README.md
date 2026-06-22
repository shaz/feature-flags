# conformance

Language-agnostic test vectors that define correct flag evaluation. This is the
**contract** that guarantees a context resolves to the same variation across
every SDK and the server-side evaluator — no variation flipping between the Go
backend and the iOS app.

Each vector is `{ name, flag (definition + env config), context, expected }`.
Every SDK's CI runs the full corpus. Vectors cover: off state, prerequisites,
individual targets, clause operators, segment matches, multi-context targeting,
and sticky percentage rollouts (the SHA1 bucketing in DESIGN.md §5).

See [../DESIGN.md](../DESIGN.md) §4, §5, §7.
