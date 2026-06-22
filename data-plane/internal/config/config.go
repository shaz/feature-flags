// Package config loads data-plane configuration from config.yaml with env overrides.
package config

import (
	"os"
	"path/filepath"
	"strconv"
	"time"

	"gopkg.in/yaml.v3"
)

type Config struct {
	Port           int
	DatabaseURL    string
	ReloadInterval time.Duration
}

type raw struct {
	Port          int `yaml:"port"`
	ReloadSeconds int `yaml:"reload_seconds"`
}

func Load(path string) (Config, error) {
	if path == "" {
		path = filepath.Join("config", "config.yaml")
	}
	b, err := os.ReadFile(path)
	if err != nil {
		return Config{}, err
	}
	var r raw
	if err := yaml.Unmarshal(b, &r); err != nil {
		return Config{}, err
	}

	cfg := Config{
		Port:           envInt("FUBO_FLAGS_DP_PORT", r.Port),
		DatabaseURL:    dbURL(),
		ReloadInterval: time.Duration(envInt("FUBO_FLAGS_DP_RELOAD", r.ReloadSeconds)) * time.Second,
	}
	return cfg, nil
}

func dbURL() string {
	if u := os.Getenv("DATABASE_URL"); u != "" {
		// pgx wants postgres:// not postgresql+psycopg://
		return normalize(u)
	}
	return "postgres://fubo_flags:localdev@localhost:5432/fubo_flags"
}

func normalize(u string) string {
	const driverPrefix = "postgresql+psycopg://"
	if len(u) >= len(driverPrefix) && u[:len(driverPrefix)] == driverPrefix {
		return "postgres://" + u[len(driverPrefix):]
	}
	return u
}

func envInt(key string, def int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return def
}
