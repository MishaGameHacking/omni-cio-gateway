# V10 RU-PG-B — Timeweb Control-Plane Read-Only Preflight

Status: **SOURCE CHECKPOINT / ENVIRONMENT HARDENING PENDING**

Owning issue: #559  
Accepted base: `8fa5ad33a17851aff6ff82be08281fed0c8c33ae`

## Purpose

This checkpoint prepares the provider control plane needed for the real RU-PG-B
Timeweb PostgreSQL 18 proof. It is deliberately read-only.

The existing PostgreSQL 18 migrations, tenant model, RLS/FORCE RLS, runtime-role
convergence and recovery semantics remain the application/database authority.
Timeweb replaces only the provider-specific control-plane boundary. Neon
production authority is preserved until the later accepted cutover.

## OWNER secret custody

The OWNER created GitHub environment `timeweb-synthetic` and environment
secret `TIMEWEB_CLOUD_API_TOKEN`. The secret value must never appear in source,
chat, screenshots, PR comments, logs or artifacts.

Before any workflow is allowed to consume the environment secret, GitHub
environment deployment branches/tags must be changed from **No restriction** to
**Selected branches and tags** with exactly the Branch rule `main`.

Official GitHub reference:

- https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments

This source checkpoint intentionally contains no workflow reference to
`TIMEWEB_CLOUD_API_TOKEN` and no `environment: timeweb-synthetic`. That remains
blocked until the OWNER returns evidence that the environment is restricted to
`main`.

## Why Public API, not Timeweb Terraform mutation yet

Timeweb supports both Terraform and Public API automation. The current OWNER
token deliberately keeps Telegram deletion confirmation enabled.

Timeweb documents that Terraform deletion requires disabling that confirmation.
Doing so would widen destructive authority. A stateful Terraform mutation path
would also introduce state custody/recovery work that is not needed merely to
prove PostgreSQL-provider parity.

Therefore RU-PG-B uses a stateless direct Public API adapter for provider
discovery/convergence. This read-only checkpoint permits only HTTP GET.

Official references:

- https://timeweb.cloud/docs/account-management/token
- https://timeweb.cloud/docs/terraform/nachalo-raboty-s-terraform
- https://timeweb.cloud/docs/dbaas/dbaas-create
- https://timeweb.cloud/docs/k8s/addons/dbaas-operator

## Read-only provider discovery

`scripts/probe_v10_timeweb_postgres_control_plane.py` will eventually run with
the environment secret and query only:

- `GET /api/v1/projects`;
- `GET /api/v1/database-types`;
- `GET /api/v2/presets/dbs`;
- `GET /api/v1/projects/{project_id}/resources/databases`.

The probe verifies without emitting provider identifiers:

- exactly one project named `Общий проект`;
- a non-deprecated PostgreSQL 18 provider type discovered from live metadata;
- the OWNER-approved target preset in `ru-3`;
- 1 CPU;
- 2048 MB RAM;
- 20480 MB / 20 GB disk;
- exact base price 790 RUB/month;
- no existing cluster named `omni-cio-v10-ru-pg-synthetic`.

Price or preset drift fails closed and requires fresh OWNER cost review instead
of silently creating a different resource.

Success is sanitized to:

`TIMEWEB_RU_PG_CONTROL_PLANE=READ_ONLY_READY`

No token, project ID, preset ID, account ID, response body, database hostname,
DSN or private payload may appear in accepted evidence.

## Mutation boundary

This checkpoint does not create or modify:

- a Timeweb database cluster;
- public IPv4;
- VPC/network objects;
- backup add-ons;
- production or staging Cloudflare DB secrets;
- production `OMNI_V10_POSTGRES_DSN`;
- Neon resources.

After the environment is hardened and this source checkpoint becomes
`CERTIFIED_GREEN`, the next RU-PG-B provider-action checkpoint may consume the
secret from protected `main` for live read-only discovery. A separate,
explicitly gated mutation step is required before creating the paid synthetic
cluster.
