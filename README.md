# fubo-flags

A self-hosted feature-flag and targeting platform — our replacement for
LaunchDarkly. Postgres as the source of truth, a Python admin console for
managing flags, and a Go data plane for distributing rules and evaluating
client contexts. Exposure events stream to GCP Managed Kafka for later analysis.

See [DESIGN.md](DESIGN.md) for the full architecture, data model, evaluation
semantics, and the cross-language bucketing contract.

## Layout

| Path | What |
|------|------|
| [control-plane/](control-plane/) | Python (FastAPI) admin API + console UI |
| [data-plane/](data-plane/) | Go distribution + evaluation service |
| [sdk/go/](sdk/go/) | Reference server-side SDK (writes the contract) |
| [conformance/](conformance/) | Language-agnostic eval test vectors |
| [migrations/](migrations/) | Postgres schema |
| [terraform/](terraform/) | Cloud SQL, Kafka topic, GKE deployment |
| [docker/](docker/) | Container definitions |

## Status

Design approved; Phase 1 (control plane) starting. See DESIGN.md §10 for phasing.

> Repo currently lives under a personal account during an Okta lockout; moving to
> `github.com/fubotv/fubo-flags` (with branch protection) once access is restored.
