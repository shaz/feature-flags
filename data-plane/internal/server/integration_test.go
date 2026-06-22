package server

import (
	"bufio"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/fubotv/fubo-flags/data-plane/internal/store"
	"github.com/jackc/pgx/v5/pgxpool"
)

func dbURL() string {
	u := os.Getenv("DATABASE_URL")
	if u == "" {
		return "postgres://fubo_flags:localdev@localhost:5432/fubo_flags"
	}
	return strings.Replace(u, "postgresql+psycopg://", "postgres://", 1)
}

func sha256hex(s string) string {
	sum := sha256.Sum256([]byte(s))
	return hex.EncodeToString(sum[:])
}

// setup applies migrations, seeds one project/env/flag/credentials, and returns
// a loaded store plus the issued keys. Skips if Postgres is unreachable.
func setup(t *testing.T) (*pgxpool.Pool, *store.Store, string, string, string) {
	t.Helper()
	ctx := context.Background()
	pool, err := pgxpool.New(ctx, dbURL())
	if err != nil {
		t.Skipf("postgres unavailable: %v", err)
	}
	if err := pool.Ping(ctx); err != nil {
		t.Skipf("postgres unreachable: %v", err)
	}

	migDir := filepath.Join("..", "..", "..", "migrations")
	exec := func(file string) {
		b, err := os.ReadFile(filepath.Join(migDir, file))
		if err != nil {
			t.Fatalf("read %s: %v", file, err)
		}
		if _, err := pool.Exec(ctx, string(b)); err != nil {
			t.Fatalf("exec %s: %v", file, err)
		}
	}
	exec("0002_flag_salt.down.sql")
	exec("0001_init.down.sql")
	exec("0001_init.up.sql")
	exec("0002_flag_salt.up.sql")

	var projectID, envID string
	pool.QueryRow(ctx,
		`INSERT INTO projects (key, name) VALUES ('p','P') RETURNING id::text`).Scan(&projectID)
	pool.QueryRow(ctx,
		`INSERT INTO environments (project_id, key, name) VALUES ($1,'production','Prod') RETURNING id::text`,
		projectID).Scan(&envID)

	var flagID string
	pool.QueryRow(ctx, `
		INSERT INTO flags (project_id, key, name, kind, variations, salt, client_side_available)
		VALUES ($1,'smoke-flag','Smoke','boolean',
		        '[{"name":"On","value":true},{"name":"Off","value":false}]','testsalt', true)
		RETURNING id::text`, projectID).Scan(&flagID)
	if _, err := pool.Exec(ctx, `
		INSERT INTO flag_environment_configs (flag_id, environment_id, enabled, fallthrough, off_variation)
		VALUES ($1,$2,true,'{"variation":0}',1)`, flagID, envID); err != nil {
		t.Fatalf("seed config: %v", err)
	}

	serverKey, clientKey := "srv-production-TESTKEY", "cli-production-TESTKEY"
	for _, c := range []struct{ kind, key string }{{"server", serverKey}, {"client", clientKey}} {
		if _, err := pool.Exec(ctx, `
			INSERT INTO sdk_credentials (environment_id, kind, key_hash, key_prefix)
			VALUES ($1,$2,$3,$4)`, envID, c.kind, sha256hex(c.key), c.kind[:3]+"-"); err != nil {
			t.Fatalf("seed credential: %v", err)
		}
	}

	st := store.New(pool)
	if _, err := st.LoadAll(ctx); err != nil {
		t.Fatalf("load: %v", err)
	}
	t.Cleanup(pool.Close)
	return pool, st, envID, serverKey, clientKey
}

func TestStoreAssembly(t *testing.T) {
	_, st, envID, _, _ := setup(t)
	rs, ok := st.Get(envID)
	if !ok {
		t.Fatal("env not loaded")
	}
	if _, ok := rs.Flags["smoke-flag"]; !ok {
		t.Fatalf("smoke-flag not assembled; got %v", rs.Flags)
	}
	if len(rs.ClientFlags) != 1 {
		t.Errorf("client flags = %v, want 1", rs.ClientFlags)
	}
}

func TestEvalEndpoint(t *testing.T) {
	pool, st, _, _, clientKey := setup(t)
	srv := New(pool, st, slog.New(slog.NewTextHandler(io.Discard, nil)))
	ts := httptest.NewServer(srv.Handler())
	defer ts.Close()

	// no key -> 401
	if r := post(t, ts.URL+"/eval", "", `{"kind":"user","key":"u1"}`); r != http.StatusUnauthorized {
		t.Errorf("no-key status = %d, want 401", r)
	}

	// client key -> server-evaluated flag state
	body := doPost(t, ts.URL+"/eval", clientKey, `{"kind":"user","key":"u1"}`)
	var out map[string]struct {
		Value          any    `json:"value"`
		VariationIndex int    `json:"variationIndex"`
		Reason         string `json:"reason"`
	}
	if err := json.Unmarshal(body, &out); err != nil {
		t.Fatalf("decode: %v (%s)", err, body)
	}
	got := out["smoke-flag"]
	if got.Value != true || got.VariationIndex != 0 || got.Reason != "FALLTHROUGH" {
		t.Errorf("eval = %+v, want value=true idx=0 FALLTHROUGH", got)
	}
}

func TestSDKStreamInitialPut(t *testing.T) {
	pool, st, _, serverKey, clientKey := setup(t)
	srv := New(pool, st, slog.New(slog.NewTextHandler(io.Discard, nil)))
	ts := httptest.NewServer(srv.Handler())
	defer ts.Close()

	// client key rejected on the server stream
	if code := streamStatus(t, ts.URL+"/sdk/stream", clientKey); code != http.StatusUnauthorized {
		t.Errorf("client key on /sdk/stream = %d, want 401", code)
	}

	event, data := readFirstSSE(t, ts.URL+"/sdk/stream", serverKey)
	if event != "put" {
		t.Errorf("first event = %q, want put", event)
	}
	if !strings.Contains(data, "smoke-flag") {
		t.Errorf("ruleset missing smoke-flag: %s", data)
	}
}

// ---- helpers ----

func post(t *testing.T, url, key, body string) int {
	t.Helper()
	req, _ := http.NewRequest("POST", url, strings.NewReader(body))
	if key != "" {
		req.Header.Set("Authorization", "Bearer "+key)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("post: %v", err)
	}
	defer resp.Body.Close()
	return resp.StatusCode
}

func doPost(t *testing.T, url, key, body string) []byte {
	t.Helper()
	req, _ := http.NewRequest("POST", url, strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+key)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("post: %v", err)
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	return b
}

func streamStatus(t *testing.T, url, key string) int {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	req, _ := http.NewRequestWithContext(ctx, "GET", url, nil)
	req.Header.Set("Authorization", "Bearer "+key)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("stream: %v", err)
	}
	defer resp.Body.Close()
	return resp.StatusCode
}

func readFirstSSE(t *testing.T, url, key string) (event, data string) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	req, _ := http.NewRequestWithContext(ctx, "GET", url, nil)
	req.Header.Set("Authorization", "Bearer "+key)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("stream: %v", err)
	}
	defer resp.Body.Close()

	sc := bufio.NewScanner(resp.Body)
	for sc.Scan() {
		line := sc.Text()
		switch {
		case strings.HasPrefix(line, "event: "):
			event = strings.TrimPrefix(line, "event: ")
		case strings.HasPrefix(line, "data: "):
			data = strings.TrimPrefix(line, "data: ")
			return event, data // first complete event
		}
	}
	t.Fatal("no SSE event received")
	return "", ""
}
