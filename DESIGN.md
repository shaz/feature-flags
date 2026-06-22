# fubo-flags — Design

A self-hosted feature-flag and targeting platform to replace our LaunchDarkly
instance. Admin console (Python) for managing flags; a high-performance Go data
plane for distributing rules and evaluating client contexts; Postgres as the
source of truth; Redis as the change/notification bus.

Status: **design — pending approval before implementation.**

---

## 1. Goals & non-goals

**Goals (v1)**
- Projects → environments → flags, with per-environment targeting.
- Boolean and multivariate flags with variations.
- Targeting rules (attribute clauses), reusable segments, percentage rollouts,
  prerequisites, individual targets.
- Deterministic, cross-language **sticky bucketing** for rollouts.
- Server-side SDKs that evaluate **locally** (in-memory ruleset).
- Client SDKs (web + mobile) that get **server-evaluated** flag state, streamed.
- Full audit log of every change.
- Emit exposure events to a stream for later analysis.

**Non-goals (deferred)**
- Experiments / A-B statistical analysis (we emit events now; analysis is a
  later project).
- Approvals/workflows, scheduled changes, flag triggers.
- Multi-region active-active. (v1 is single-region; design doesn't preclude it.)

---

## 2. Architecture

```
   ┌──────────────────────── CONTROL PLANE (Python) ────────────────────────┐
   │  Admin UI (the prototype)  →  Admin API  →  Postgres (source of truth)   │
   │                                              + audit_logs                │
   └───────────────────────────────────┬────────────────────────────────────┘
                                        │ on write: bump config.version,
                                        │ NOTIFY / Redis pub-sub "env <id> changed"
   ┌────────────────────────────────────▼───────────────────────────────────┐
   │            DATA PLANE (Go) — holds per-env ruleset in process memory      │
   │  GET /sdk/stream    (server SDK key)  → full ruleset      → backends eval │
   │  GET /eval/stream   (client/mobile key) → server-evaluated → web + mobile │
   │  POST /events       (any key)         → exposure events    → stream       │
   └───────────────────────┬──────────────────────────────────────────────────┘
        exposure events ────▼──► Kafka / PubSub ──► [experiments analytics, later]
```

- **Postgres** is the only source of truth. Every targeting change increments a
  per-(flag, environment) `version` and writes an `audit_log` row in the same
  transaction.
- **Change propagation**: control plane fires `NOTIFY flags_changed, '<env_id>'`
  (Postgres `LISTEN/NOTIFY` is enough for v1) and/or publishes to a Redis
  channel. Data-plane nodes hold the assembled ruleset in process memory and
  reload the affected environment on signal. **Reads never hit Postgres or Redis
  on the eval path** — they hit local memory.
- **Redis** role: change bus + shared cache for warm starts / many replicas. Not
  a per-read hop. v1 can run on `LISTEN/NOTIFY` alone; Redis earns its place when
  we scale the data plane horizontally.

### Why the eval split (verified against LaunchDarkly docs)

| | Server-side SDKs (Go, Python, Node) | Client SDKs (web JS, iOS, Android) |
|---|---|---|
| Ruleset | Full per-env ruleset streamed down | **Never** — security/PII |
| Where eval runs | In-process, in-memory (µs) | On the data plane, per context |
| Update mechanism | Stream ruleset diffs | Stream evaluated flag-state diffs |
| Credential | `server` SDK key (secret) | `client` ID / `mobile` key (public) |

Client SDKs send an evaluation context; the data plane evaluates every
client-available flag for that context, returns the flag-state map, and streams
updates as config or context changes. This keeps targeting logic and segment
membership off untrusted devices.

---

## 3. Data model (Postgres)

Flag **definition** is shared across environments. Flag **targeting / on-off** is
per-environment. That split is the backbone of the schema.

```sql
-- Identifiers are UUIDs; keys are the stable human/SDK-facing handles.

create table projects (
  id          uuid primary key default gen_random_uuid(),
  key         text not null unique,            -- e.g. "streaming"
  name        text not null,
  description text,
  created_at  timestamptz not null default now()
);

create table environments (
  id          uuid primary key default gen_random_uuid(),
  project_id  uuid not null references projects(id) on delete cascade,
  key         text not null,                   -- "production", "staging"
  name        text not null,
  sort_order  int  not null default 0,
  created_at  timestamptz not null default now(),
  unique (project_id, key)
);

create table sdk_credentials (
  id             uuid primary key default gen_random_uuid(),
  environment_id uuid not null references environments(id) on delete cascade,
  kind           text not null check (kind in ('server','client','mobile')),
  key_hash       text not null,                -- store hash; show plaintext once
  key_prefix     text not null,                -- e.g. "sdk-prod-" for UI display
  created_at     timestamptz not null default now(),
  revoked_at     timestamptz
);

-- Flag definition (shared across all environments in the project).
create table flags (
  id           uuid primary key default gen_random_uuid(),
  project_id   uuid not null references projects(id) on delete cascade,
  key          text not null,                  -- "paywall-v3"
  name         text not null,
  description  text,
  kind         text not null check (kind in ('boolean','multivariate')),
  -- ordered array; rules/fallthrough reference variations by INDEX (LD-style).
  -- [{"name":"On","value":true}, {"name":"Off","value":false}]
  variations   jsonb not null,
  temporary    boolean not null default true,  -- "remove when done" hint
  tags         text[] not null default '{}',
  owner        text,
  client_side_available boolean not null default false,  -- exposable to web/mobile
  created_at   timestamptz not null default now(),
  archived_at  timestamptz,
  unique (project_id, key)
);

-- Per-environment configuration. One row per (flag, environment).
create table flag_environment_configs (
  flag_id        uuid not null references flags(id) on delete cascade,
  environment_id uuid not null references environments(id) on delete cascade,
  enabled        boolean not null default false,   -- "targeting is on/off"
  -- per-kind explicit targets: [{"contextKind":"user","variation":0,"keys":["u-123"]}]
  targets        jsonb not null default '[]',
  -- ordered rules; first match wins. Shape in §4.
  rules          jsonb not null default '[]',
  -- default rule when enabled and nothing else matched. variation or rollout.
  fallthrough    jsonb not null default '{"variation":0}',
  -- variation served when enabled = false.
  off_variation  int not null default 0,
  -- prerequisite flags: [{"flagKey":"x","variation":1}]
  prerequisites  jsonb not null default '[]',
  version        bigint not null default 1,        -- bumps on every change
  updated_at     timestamptz not null default now(),
  updated_by     text,
  primary key (flag_id, environment_id)
);

-- Segment definition is project-level; membership/rules are per-environment.
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
  context_kind   text not null default 'user',     -- kind whose keys are listed
  included       text[] not null default '{}',     -- explicit context keys
  excluded       text[] not null default '{}',
  rules          jsonb not null default '[]',      -- same clause shape as flags
  version        bigint not null default 1,
  updated_at     timestamptz not null default now(),
  primary key (segment_id, environment_id)
);

create table audit_logs (
  id             bigserial primary key,
  project_id     uuid not null references projects(id) on delete cascade,
  environment_id uuid references environments(id) on delete set null,
  actor          text not null,                    -- admin user / API token
  action         text not null,                    -- "flag.targeting.updated"
  resource_type  text not null,                    -- "flag" | "segment" | ...
  resource_key   text not null,
  summary        text not null,                    -- human-readable line
  diff           jsonb,                            -- before/after
  created_at     timestamptz not null default now()
);
create index on audit_logs (project_id, created_at desc);
```

**Variation referencing.** Rules/fallthrough/targets point at variations by
**index** (matching LD and our conformance vectors). Variations are
append-or-retire only — never reordered — so indices stay stable. The admin API
enforces this.

**Exposure events are not in Postgres.** They go to a stream (§6).

---

## 4. Targeting & evaluation semantics

### Context model (multi-context, LD-current)

A context is one or more **kinds** (`user`, `device`, `org`, …), each with its own
`key` and attributes. Single-kind is the degenerate case.

```jsonc
// multi-kind
{ "kind": "multi",
  "user":   { "key": "u-123", "country": "US", "segment": "power-viewers" },
  "device": { "key": "ios-9", "osVersion": "17" } }

// single-kind shorthand
{ "kind": "user", "key": "u-123", "country": "US" }
```

Every clause, target, and rollout names the `contextKind` it applies to. If a
flag references a kind absent from the context, that clause does not match and a
rollout that buckets on the missing kind uses an empty bucket-by value (still
deterministic — all such contexts land together). This is specified exactly by
the conformance vectors (§7).

### Evaluation order

Evaluation of one flag for one context, in order (first hit wins):

1. **Off** — if `enabled = false`, serve `off_variation`. Stop.
2. **Prerequisites** — for each, the prereq flag must be `enabled` *and* evaluate
   to the required variation. Any failure → serve `off_variation`. Stop.
3. **Targets** — if the context's key (for the target's `contextKind`) is listed,
   serve that variation. Stop.
4. **Rules** — first rule whose clauses all match → its `variation` or `rollout`.
5. **Fallthrough** — the default rule's `variation` or `rollout`.

**Clause** (the unit inside a rule) — names the context kind it reads from:
```jsonc
{ "contextKind": "user", "attribute": "country",
  "op": "in", "values": ["US","CA"], "negate": false }
```
v1 operators: `in`, `endsWith`, `startsWith`, `matches` (regex), `contains`,
`lessThan`, `greaterThan`, `before`, `after`, `semVerEqual/Less/Greater`,
`segmentMatch` (value is a segment key). Negate flips the result.

**Rule / fallthrough payload** is either a fixed variation or a rollout. A
rollout names the `contextKind` it buckets on:
```jsonc
// fixed
{ "clauses": [ ... ], "variation": 1 }

// percentage rollout
{ "clauses": [ ... ],
  "rollout": {
    "contextKind": "user",
    "bucketBy": "key",
    "variations": [ { "variation": 0, "weight": 60000 },
                    { "variation": 1, "weight": 40000 } ] } }   // Σ weight = 100000
```

---

## 5. Bucketing spec (the cross-language contract)

This MUST be byte-for-byte identical in every SDK and in the server-side
evaluator, or a user flips variations between platforms. **Verified against
LaunchDarkly's published algorithm** so existing rollouts migrate cleanly.

```
bucket_value(flagKey, salt, contextKind, bucketBy, context):
    value     = attribute(context, contextKind, bucketBy)   # "" if kind/attr absent
    hashInput = flagKey + "." + salt + "." + str(value)
    hexHash   = sha1_hex(hashInput)            # 40 hex chars
    take first 15 hex chars                     # 60 bits
    intVal    = int(those_15_chars, base=16)
    return intVal / 0xFFFFFFFFFFFFFFF            # float in [0, 1)
```

- `salt` is per-flag (stable; rotating it re-buckets everyone — admin-gated).
- The rollout's `contextKind` + `bucketBy` select which context kind's attribute
  to bucket on (`bucketBy` defaults to `key`). If that kind is absent, `value` is
  empty — still deterministic, all such contexts bucket together.
- Map the float onto 100,000 partitions; assign by **cumulative weight** in
  variation order. 60,000 / 40,000 → partitions 1–60,000 get variation 0.

> Note: the 60-bit truncation has a known mild distribution quirk (see
> launchdarkly/node-server-sdk#157). We keep it for LD parity and pin exact
> behavior with conformance vectors (§7) rather than "improving" it silently.

---

## 6. Distribution protocol (data plane)

All streams are **SSE** (`text/event-stream`); fall back to polling with ETag.

- **`GET /sdk/stream`** — auth: `server` key. Sends `put` (full env ruleset:
  flags + segments) on connect, then `patch`/`delete` events as configs change.
  The SDK evaluates locally. Payload is the assembled ruleset keyed by flag key,
  each carrying its `version`.
- **`GET /eval/stream`** — auth: `client`/`mobile` key + an evaluation context.
  The data plane evaluates all `client_side_available` flags for that context and
  sends `put` (flag-state map: `{key: {value, variation, reason}}`), then
  `patch` as config or context-relevant data changes. No rules leave the server.
- **`POST /events`** — batched exposure + custom events from any SDK (§ below).

**Reload path**: on `NOTIFY`/Redis signal for an env, the node re-assembles that
env's ruleset from Postgres into memory and pushes diffs to connected streams.
Assembly resolves segments and validates prerequisite references.

**Versioning**: monotonic per-(flag, env) `version`. SDKs ignore out-of-order
updates. A full `put` carries every flag's version for reconciliation.

---

## 7. SDK strategy

- Build SDKs as **OpenFeature providers** (verified as the vendor-agnostic
  standard) so the consumer API is a community spec, not ours to bikeshed.
  - Server-side: Go (reference), Python, Node — local evaluator + `/sdk/stream`.
  - Client-side: Web JS, iOS, Android — `/eval/stream`, local cache, offline
    fallback, default-value safety.
- **Conformance test vectors** are the contract that guarantees parity. A
  language-agnostic JSON corpus lives in the repo:
  ```jsonc
  { "name": "rollout 60/40 sticky by key",
    "flag": { ...definition+config... },
    "context": { "key": "user-123", "country": "US" },
    "expected": { "value": true, "variation": 0, "reason": "FALLTHROUGH" } }
  ```
  Every SDK's CI runs the full corpus. The evaluator and vectors are written
  before the second SDK exists, so Go validates the contract first.
- **Fail-safe**: every `variation()` call takes a caller-supplied default; if the
  SDK is uninitialized or disconnected, it returns the default and logs — it
  never blocks or throws into the host app.

---

## 8. Exposure events

On each evaluation, server-side SDKs emit (batched, async) an exposure event:
`{flagKey, variation, value, contextKey, reason, timestamp, version}`. Client
SDKs do the same via `POST /events`. The data plane forwards to **GCP Managed
Kafka** (a dedicated `fubo-flags.exposures` topic). v1 stops there; the
experiments analytics pipeline consumes the topic later.

---

## 9. Tech stack

| Layer | Choice | Rationale |
|---|---|---|
| Source of truth | Postgres | Relational, transactional audit, `LISTEN/NOTIFY` |
| Change bus / cache | Redis (or NOTIFY for v1) | Fan-out reload signal; warm cache at scale |
| Admin API + UI | Python (FastAPI) | Team-maintained back office; matches conventions |
| Data plane | Go | Hot path, in-memory eval, many concurrent streams |
| Reference SDK | Go | Perf path + writes the conformance contract |
| Event stream | GCP Managed Kafka | Decouple exposure events; reuse existing infra |
| Deploy | Docker + K8s, Terraform, GH Actions | Per project conventions |

Each component containerized; `config.yaml` per service (no hardcoded values);
Makefile with `build`/`run` per repo; tests alongside code.

---

## 10. Phasing

1. **Control plane** — schema + FastAPI admin API + wire up the prototype UI.
   CRUD on projects/envs/flags/segments/targeting + audit log. Internally usable
   before any SDK exists.
2. **Data plane + reference SDK** — Go distribution service, in-memory ruleset,
   `/sdk/stream`, change bus, Go server-side SDK, **conformance vector suite**.
3. **Client serving** — `/eval/stream` + Web JS SDK, then iOS/Android.
4. **Exposure events** — emit to stream. (Experiments analytics: separate project.)

---

## 11. Decisions & open questions

**Decided**
- **Context model**: multi-context (LD-current) from day one. Reflected in §4–§5.
- **Event stream**: GCP Managed Kafka, `fubo-flags.exposures` topic.
- **LD migration**: deferred — revisit once the phase-1 console is usable. Schema
  stays LD-compatible (variation indices, SHA1 bucketing) so a later importer is
  viable.

**Still open**
- **Admin authn/z**: Okta SSO + role model (reader / writer / admin per project)?
- **Segment scope**: project-level definition with env-scoped membership (current
  design) vs fully env-scoped — confirm.
