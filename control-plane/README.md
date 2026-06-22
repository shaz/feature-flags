# control-plane

Python (FastAPI) admin API and console UI. Owns writes to Postgres, the audit
log, and SDK credential management. Fires change notifications (Postgres
`NOTIFY` / Redis) that the data plane listens for.

The UI is the `fubo-flags` prototype, wired to this API.

See [../DESIGN.md](../DESIGN.md) §2–§4, §10 (Phase 1).
