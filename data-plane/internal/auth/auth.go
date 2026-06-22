// Package auth resolves an SDK key to its environment by hash lookup.
package auth

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

var ErrInvalidKey = errors.New("invalid or revoked SDK key")

// Credential identifies the environment and kind an SDK key grants access to.
type Credential struct {
	EnvID string
	Kind  string // server | client | mobile
}

// Authenticate hashes the presented key and looks it up. We only ever store the
// hash, so this is the only way a key maps back to an environment.
func Authenticate(ctx context.Context, pool *pgxpool.Pool, presentedKey string) (Credential, error) {
	sum := sha256.Sum256([]byte(presentedKey))
	hash := hex.EncodeToString(sum[:])

	var c Credential
	err := pool.QueryRow(ctx, `
		SELECT environment_id::text, kind
		FROM sdk_credentials
		WHERE key_hash = $1 AND revoked_at IS NULL`, hash).Scan(&c.EnvID, &c.Kind)
	if errors.Is(err, pgx.ErrNoRows) {
		return Credential{}, ErrInvalidKey
	}
	return c, err
}
