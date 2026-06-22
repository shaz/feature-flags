-- fubo-flags initial schema. See DESIGN.md §3.
-- Canonical, language-neutral DDL: both the Python control plane and the Go
-- data plane read this schema. Variations are referenced by INDEX; the admin
-- API enforces append-or-retire (never reorder) so indices stay stable.

create extension if not exists pgcrypto;   -- gen_random_uuid()

-- ── Catalog ────────────────────────────────────────────────────────────────

create table projects (
  id          uuid primary key default gen_random_uuid(),
  key         text not null unique,
  name        text not null,
  description text,
  created_at  timestamptz not null default now()
);

create table environments (
  id          uuid primary key default gen_random_uuid(),
  project_id  uuid not null references projects(id) on delete cascade,
  key         text not null,
  name        text not null,
  sort_order  int  not null default 0,
  created_at  timestamptz not null default now(),
  unique (project_id, key)
);

create table sdk_credentials (
  id             uuid primary key default gen_random_uuid(),
  environment_id uuid not null references environments(id) on delete cascade,
  kind           text not null check (kind in ('server','client','mobile')),
  key_hash       text not null,
  key_prefix     text not null,
  created_at     timestamptz not null default now(),
  revoked_at     timestamptz
);
create index sdk_credentials_env_idx on sdk_credentials (environment_id);

-- ── Flags ──────────────────────────────────────────────────────────────────

create table flags (
  id                    uuid primary key default gen_random_uuid(),
  project_id            uuid not null references projects(id) on delete cascade,
  key                   text not null,
  name                  text not null,
  description           text,
  kind                  text not null check (kind in ('boolean','multivariate')),
  -- ordered: [{"name":"On","value":true}, {"name":"Off","value":false}]
  variations            jsonb not null,
  temporary             boolean not null default true,
  tags                  text[] not null default '{}',
  owner                 text,
  client_side_available boolean not null default false,
  created_at            timestamptz not null default now(),
  archived_at           timestamptz,
  unique (project_id, key)
);

-- One row per (flag, environment). Holds the per-env targeting.
create table flag_environment_configs (
  flag_id        uuid not null references flags(id) on delete cascade,
  environment_id uuid not null references environments(id) on delete cascade,
  enabled        boolean not null default false,
  -- per-kind targets: [{"contextKind":"user","variation":0,"keys":["u-123"]}]
  targets        jsonb  not null default '[]',
  -- ordered rules; first match wins. clause/rollout shapes in DESIGN.md §4.
  rules          jsonb  not null default '[]',
  -- default rule when enabled and nothing matched: {"variation":N} | {"rollout":{...}}
  fallthrough    jsonb  not null default '{"variation":0}',
  -- variation served when enabled = false
  off_variation  int    not null default 0,
  -- [{"flagKey":"x","variation":1}]
  prerequisites  jsonb  not null default '[]',
  version        bigint not null default 1,
  updated_at     timestamptz not null default now(),
  updated_by     text,
  primary key (flag_id, environment_id)
);

-- ── Segments ───────────────────────────────────────────────────────────────

create table segments (
  id          uuid primary key default gen_random_uuid(),
  project_id  uuid not null references projects(id) on delete cascade,
  key         text not null,
  name        text not null,
  description text,
  created_at  timestamptz not null default now(),
  unique (project_id, key)
);

create table segment_environment_configs (
  segment_id     uuid not null references segments(id) on delete cascade,
  environment_id uuid not null references environments(id) on delete cascade,
  context_kind   text   not null default 'user',
  included       text[] not null default '{}',
  excluded       text[] not null default '{}',
  rules          jsonb  not null default '[]',
  version        bigint not null default 1,
  updated_at     timestamptz not null default now(),
  primary key (segment_id, environment_id)
);

-- ── Audit ──────────────────────────────────────────────────────────────────

create table audit_logs (
  id             bigserial primary key,
  project_id     uuid not null references projects(id) on delete cascade,
  environment_id uuid references environments(id) on delete set null,
  actor          text not null,
  action         text not null,
  resource_type  text not null,
  resource_key   text not null,
  summary        text not null,
  diff           jsonb,
  created_at     timestamptz not null default now()
);
create index audit_logs_project_time_idx on audit_logs (project_id, created_at desc);
