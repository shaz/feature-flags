# migrations

Postgres schema, applied as ordered migrations. The schema is the source of truth
for projects, environments, flags, per-environment configs, segments, SDK
credentials, and the audit log.

DDL is specified in [../DESIGN.md](../DESIGN.md) §3. Phase 1 turns it into real
migration files.
