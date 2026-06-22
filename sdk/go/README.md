# sdk/go

Reference server-side SDK (OpenFeature provider). Streams the full ruleset from
the data plane's `/sdk/stream` and evaluates flags locally, in-memory.

This SDK is the **reference implementation of the evaluation + bucketing
contract** — it is built first and validated against [../../conformance/](../../conformance/)
before any second SDK exists. Every other SDK must match its behavior vector-for-vector.

`variation()` always takes a caller default and never blocks or throws into the
host app.

See [../../DESIGN.md](../../DESIGN.md) §4, §5, §7, §10 (Phase 2).
