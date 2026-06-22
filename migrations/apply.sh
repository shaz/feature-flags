#!/usr/bin/env bash
# Apply all *.up.sql migrations in order via psql. For local dev when the
# golang-migrate CLI isn't installed. Production/CI should use `migrate` (see
# README.md) for proper version tracking.
set -euo pipefail

DB_URL="${DATABASE_URL:?set DATABASE_URL, e.g. postgres://fubo_flags:localdev@localhost:5432/fubo_flags}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for f in "$HERE"/*.up.sql; do
  echo ">> applying $(basename "$f")"
  psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$f"
done
echo ">> migrations applied"
