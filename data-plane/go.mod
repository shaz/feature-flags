module github.com/fubotv/fubo-flags/data-plane

go 1.25

require (
	github.com/fubotv/fubo-flags/sdk/go v0.0.0
	github.com/jackc/pgx/v5 v5.6.0
	gopkg.in/yaml.v3 v3.0.1
)

require (
	github.com/jackc/pgpassfile v1.0.0 // indirect
	github.com/jackc/pgservicefile v0.0.0-20221227161230-091c0ba34f0a // indirect
	github.com/jackc/puddle/v2 v2.2.1 // indirect
	github.com/kr/text v0.2.0 // indirect
	github.com/rogpeppe/go-internal v1.15.0 // indirect
	golang.org/x/crypto v0.17.0 // indirect
	golang.org/x/sync v0.1.0 // indirect
	golang.org/x/text v0.14.0 // indirect
)

// sdk/go lives in this repo; resolve it locally (works in CI without a go.work).
replace github.com/fubotv/fubo-flags/sdk/go => ../sdk/go
