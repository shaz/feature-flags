// Package server exposes the data-plane HTTP surface (DESIGN.md §6):
//
//	GET  /sdk/stream  server key  -> full ruleset over SSE (backends eval locally)
//	POST /eval        client key  -> server-evaluated flag state for a context
//	POST /events      any key     -> exposure events (forwarded to Kafka; stubbed)
//	GET  /healthz
package server

import (
	"encoding/json"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/fubotv/fubo-flags/data-plane/internal/auth"
	"github.com/fubotv/fubo-flags/data-plane/internal/store"
	"github.com/fubotv/fubo-flags/sdk/go/flageval"
	"github.com/jackc/pgx/v5/pgxpool"
)

type Server struct {
	pool  *pgxpool.Pool
	store *store.Store
	log   *slog.Logger
}

func New(pool *pgxpool.Pool, st *store.Store, log *slog.Logger) *Server {
	return &Server{pool: pool, store: st, log: log}
}

func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})
	mux.HandleFunc("GET /sdk/stream", s.handleSDKStream)
	mux.HandleFunc("POST /eval", s.handleEval)
	mux.HandleFunc("POST /events", s.handleEvents)
	return mux
}

// bearer extracts the SDK key from "Authorization: Bearer <key>".
func bearer(r *http.Request) string {
	h := r.Header.Get("Authorization")
	if after, ok := strings.CutPrefix(h, "Bearer "); ok {
		return after
	}
	return ""
}

func (s *Server) authenticate(r *http.Request, want string) (auth.Credential, error) {
	cred, err := auth.Authenticate(r.Context(), s.pool, bearer(r))
	if err != nil {
		return auth.Credential{}, err
	}
	switch want {
	case "server":
		if cred.Kind != "server" { // server stream needs a server key
			return auth.Credential{}, auth.ErrInvalidKey
		}
	case "client":
		if cred.Kind == "server" { // /eval is for client + mobile keys
			return auth.Credential{}, auth.ErrInvalidKey
		}
	}
	return cred, nil
}

// handleSDKStream sends the full ruleset to a trusted server-side SDK and pushes
// a fresh copy whenever the environment's version changes.
func (s *Server) handleSDKStream(w http.ResponseWriter, r *http.Request) {
	cred, err := s.authenticate(r, "server")
	if err != nil {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "streaming unsupported", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")

	var lastVersion int64 = -1
	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()

	send := func() bool {
		rs, ok := s.store.Get(cred.EnvID)
		if !ok || rs.Version == lastVersion {
			return false
		}
		lastVersion = rs.Version
		writeSSE(w, "put", rs)
		flusher.Flush()
		return true
	}

	send() // initial snapshot
	for {
		select {
		case <-r.Context().Done():
			return
		case <-ticker.C:
			send()
		}
	}
}

type evalResult struct {
	Value          any    `json:"value"`
	VariationIndex int    `json:"variationIndex"`
	Reason         string `json:"reason"`
}

// handleEval evaluates every client-available flag for a posted context and
// returns the flag-state map. Targeting rules never leave the server.
func (s *Server) handleEval(w http.ResponseWriter, r *http.Request) {
	cred, err := s.authenticate(r, "client")
	if err != nil {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	var rawCtx map[string]any
	if err := json.NewDecoder(r.Body).Decode(&rawCtx); err != nil {
		http.Error(w, "invalid context", http.StatusBadRequest)
		return
	}
	rs, ok := s.store.Get(cred.EnvID)
	if !ok {
		http.Error(w, "environment not loaded", http.StatusServiceUnavailable)
		return
	}

	ctx := flageval.ParseContext(rawCtx)
	fstore := rs.AsStore()
	out := make(map[string]evalResult, len(rs.ClientFlags))
	for _, key := range rs.ClientFlags {
		res := flageval.Evaluate(rs.Flags[key], fstore, ctx)
		out[key] = evalResult{res.Value, res.VariationIndex, res.Reason}
	}
	writeJSON(w, http.StatusOK, out)
}

func (s *Server) handleEvents(w http.ResponseWriter, r *http.Request) {
	if _, err := s.authenticate(r, "any"); err != nil {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	var events []json.RawMessage
	if err := json.NewDecoder(r.Body).Decode(&events); err != nil {
		http.Error(w, "invalid events", http.StatusBadRequest)
		return
	}
	// TODO(phase-4): forward to GCP Managed Kafka (fubo-flags.exposures).
	s.log.Info("exposure events received", "count", len(events))
	w.WriteHeader(http.StatusAccepted)
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func writeSSE(w http.ResponseWriter, event string, v any) {
	b, _ := json.Marshal(v)
	_, _ = w.Write([]byte("event: " + event + "\ndata: "))
	_, _ = w.Write(b)
	_, _ = w.Write([]byte("\n\n"))
}
