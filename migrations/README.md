# migrations

Postgres schema, applied as ordered migrations. This is the **source of truth**
for the data model — both the Python control plane and the Go data plane map to
it. DDL is specified in [../DESIGN.md](../DESIGN.md) §3.

## Format

Files follow [golang-migrate](https://github.com/golang-migrate/migrate) naming
(`NNNN_name.up.sql` / `.down.sql`) so the Go side can share the same tooling.
Variations are referenced by **index**; the admin API enforces append-or-retire
so indices never shift.

## Applying

Production / CI uses `migrate`:

```sh
migrate -path . -database "$DATABASE_URL" up
```

For local dev without the CLI, the control-plane Makefile applies the `*.up.sql`
files in order via `psql` (`make migrate`).
