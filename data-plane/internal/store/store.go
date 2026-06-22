// Package store assembles per-environment rulesets from Postgres and holds them
// in process memory for the evaluation/serving path (DESIGN.md §2, §6).
package store

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"

	"github.com/fubotv/fubo-flags/sdk/go/flageval"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Ruleset is one environment's assembled flags + segments, ready to evaluate.
type Ruleset struct {
	EnvID       string                      `json:"-"`
	Version     int64                       `json:"-"` // aggregate; changes when any config changes
	Flags       map[string]flageval.Flag    `json:"flags"`
	Segments    map[string]flageval.Segment `json:"segments"`
	ClientFlags []string                    `json:"-"` // client_side_available flag keys
}

func (r *Ruleset) AsStore() flageval.Store {
	return flageval.Store{Flags: r.Flags, Segments: r.Segments}
}

// Store holds every environment's ruleset, refreshed from Postgres.
type Store struct {
	pool *pgxpool.Pool
	mu   sync.RWMutex
	envs map[string]*Ruleset
}

func New(pool *pgxpool.Pool) *Store {
	return &Store{pool: pool, envs: map[string]*Ruleset{}}
}

func (s *Store) Get(envID string) (*Ruleset, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	r, ok := s.envs[envID]
	return r, ok
}

// LoadAll reassembles every environment. Returns the env IDs whose aggregate
// version changed since the last load.
func (s *Store) LoadAll(ctx context.Context) ([]string, error) {
	rows, err := s.pool.Query(ctx, `SELECT id::text, project_id::text FROM environments`)
	if err != nil {
		return nil, fmt.Errorf("list environments: %w", err)
	}
	defer rows.Close()

	type envRef struct{ id, projectID string }
	var refs []envRef
	for rows.Next() {
		var e envRef
		if err := rows.Scan(&e.id, &e.projectID); err != nil {
			return nil, err
		}
		refs = append(refs, e)
	}

	var changed []string
	for _, ref := range refs {
		rs, err := s.assemble(ctx, ref.id, ref.projectID)
		if err != nil {
			return nil, fmt.Errorf("assemble env %s: %w", ref.id, err)
		}
		s.mu.Lock()
		prev, ok := s.envs[ref.id]
		if !ok || prev.Version != rs.Version {
			s.envs[ref.id] = rs
			changed = append(changed, ref.id)
		}
		s.mu.Unlock()
	}
	return changed, nil
}

func (s *Store) assemble(ctx context.Context, envID, projectID string) (*Ruleset, error) {
	rs := &Ruleset{
		EnvID:    envID,
		Flags:    map[string]flageval.Flag{},
		Segments: map[string]flageval.Segment{},
	}

	flagRows, err := s.pool.Query(ctx, `
		SELECT f.key, f.salt, f.kind, f.variations, f.client_side_available,
		       c.enabled, c.targets, c.rules, c.fallthrough, c.off_variation,
		       c.prerequisites, c.version
		FROM flags f
		JOIN flag_environment_configs c
		  ON c.flag_id = f.id AND c.environment_id = $1
		WHERE f.project_id = $2 AND f.archived_at IS NULL`, envID, projectID)
	if err != nil {
		return nil, err
	}
	defer flagRows.Close()

	for flagRows.Next() {
		var (
			f                                                flageval.Flag
			variations, targets, rules, fallthrough_, prereq []byte
			clientSide                                       bool
			version                                          int64
		)
		if err := flagRows.Scan(
			&f.Key, &f.Salt, &f.Kind, &variations, &clientSide,
			&f.Config.Enabled, &targets, &rules, &fallthrough_, &f.Config.OffVariation,
			&prereq, &version,
		); err != nil {
			return nil, err
		}
		for _, u := range []struct {
			dst  any
			data []byte
		}{
			{&f.Variations, variations},
			{&f.Config.Targets, targets},
			{&f.Config.Rules, rules},
			{&f.Config.Fallthrough, fallthrough_},
			{&f.Config.Prerequisites, prereq},
		} {
			if len(u.data) == 0 {
				continue
			}
			if err := json.Unmarshal(u.data, u.dst); err != nil {
				return nil, fmt.Errorf("flag %s: %w", f.Key, err)
			}
		}
		rs.Flags[f.Key] = f
		rs.Version += version
		if clientSide {
			rs.ClientFlags = append(rs.ClientFlags, f.Key)
		}
	}

	segRows, err := s.pool.Query(ctx, `
		SELECT s.key, sec.context_kind, sec.included, sec.excluded, sec.rules, sec.version
		FROM segments s
		JOIN segment_environment_configs sec
		  ON sec.segment_id = s.id AND sec.environment_id = $1
		WHERE s.project_id = $2`, envID, projectID)
	if err != nil {
		return nil, err
	}
	defer segRows.Close()

	for segRows.Next() {
		var (
			seg     flageval.Segment
			rulesJS []byte
			version int64
		)
		if err := segRows.Scan(
			&seg.Key, &seg.ContextKind, &seg.Included, &seg.Excluded, &rulesJS, &version,
		); err != nil {
			return nil, err
		}
		if err := json.Unmarshal(rulesJS, &seg.Rules); err != nil {
			return nil, fmt.Errorf("segment %s rules: %w", seg.Key, err)
		}
		rs.Segments[seg.Key] = seg
		rs.Version += version
	}

	return rs, nil
}
