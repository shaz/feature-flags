-- Per-flag bucketing salt (DESIGN.md §5). Stable; rotating it re-buckets every
-- context in every percentage rollout, so the admin API gates changes to it.
alter table flags
  add column salt text not null default encode(gen_random_bytes(8), 'hex');
