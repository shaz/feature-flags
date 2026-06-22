# data-plane

Go service that holds each environment's assembled ruleset in process memory and
serves it over SSE. Two surfaces:

- `GET /sdk/stream` — full ruleset to trusted server-side SDKs (local eval).
- `GET /eval/stream` — server-evaluated flag state for web/mobile contexts.
- `POST /events` — exposure events, forwarded to Managed Kafka.

Reloads an environment on change signals from the control plane. Reads never hit
Postgres on the eval path.

See [../DESIGN.md](../DESIGN.md) §2, §6, §10 (Phase 2).
