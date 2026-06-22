// Command dataplane serves assembled rulesets to SDKs and evaluates client
// contexts (DESIGN.md §2, §6).
package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/fubotv/fubo-flags/data-plane/internal/config"
	"github.com/fubotv/fubo-flags/data-plane/internal/server"
	"github.com/fubotv/fubo-flags/data-plane/internal/store"
	"github.com/jackc/pgx/v5/pgxpool"
)

func main() {
	log := slog.New(slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelDebug}))

	cfg, err := config.Load(os.Getenv("FUBO_FLAGS_DP_CONFIG"))
	if err != nil {
		log.Error("load config", "err", err)
		os.Exit(1)
	}

	ctx := context.Background()
	pool, err := pgxpool.New(ctx, cfg.DatabaseURL)
	if err != nil {
		log.Error("connect postgres", "err", err)
		os.Exit(1)
	}
	defer pool.Close()

	st := store.New(pool)
	if _, err := st.LoadAll(ctx); err != nil {
		log.Error("initial ruleset load", "err", err)
		os.Exit(1)
	}
	log.Info("initial rulesets loaded")

	go reloadLoop(ctx, st, cfg.ReloadInterval, log)
	go listenForChanges(ctx, pool, st, log)

	srv := server.New(pool, st, log)
	addr := ":" + strconv.Itoa(cfg.Port)
	log.Info("data plane listening", "addr", addr)
	httpSrv := &http.Server{Addr: addr, Handler: srv.Handler(), ReadHeaderTimeout: 5 * time.Second}
	if err := httpSrv.ListenAndServe(); err != nil {
		log.Error("http server", "err", err)
		os.Exit(1)
	}
}

// reloadLoop is the backstop: periodically reassemble and log what changed.
func reloadLoop(ctx context.Context, st *store.Store, interval time.Duration, log *slog.Logger) {
	if interval <= 0 {
		interval = 5 * time.Second
	}
	t := time.NewTicker(interval)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
			if changed, err := st.LoadAll(ctx); err != nil {
				log.Error("reload", "err", err)
			} else if len(changed) > 0 {
				log.Info("rulesets reloaded", "environments", len(changed))
			}
		}
	}
}

// listenForChanges reacts to control-plane NOTIFY flags_changed for immediate
// reloads (DESIGN.md §6). The reload poll above covers any missed notification.
func listenForChanges(ctx context.Context, pool *pgxpool.Pool, st *store.Store, log *slog.Logger) {
	conn, err := pool.Acquire(ctx)
	if err != nil {
		log.Warn("listen acquire failed; relying on poll", "err", err)
		return
	}
	defer conn.Release()
	if _, err := conn.Exec(ctx, "LISTEN flags_changed"); err != nil {
		log.Warn("LISTEN failed; relying on poll", "err", err)
		return
	}
	log.Info("listening for flags_changed notifications")
	for {
		n, err := conn.Conn().WaitForNotification(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return
			}
			log.Warn("wait notification", "err", err)
			return
		}
		if changed, err := st.LoadAll(ctx); err != nil {
			log.Error("reload on notify", "err", err)
		} else {
			log.Info("reloaded on notify", "payload", n.Payload, "changed", len(changed))
		}
	}
}
