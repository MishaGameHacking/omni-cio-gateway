# V10 RU-PG-B — Timeweb Synthetic PostgreSQL 18 Create Runbook

Status: **SOURCE READY / PAID MUTATION BLOCKED ON PARITY TRANSPORT PROOF**

Owning issue: #559

Accepted source base: `4987d5adced8f449b482ec1ad4165a0130c995d3`.

Accepted prerequisite provider evidence:

- workflow run `35465650177`;
- `TIMEWEB_GITHUB_ENVIRONMENT_GATE=READY`;
- `TIMEWEB_RU_PG_CONTROL_PLANE=READ_ONLY_READY`;
- PostgreSQL 18;
- Timeweb location `ru-3` / availability zone `msk-1`;
- 1 CPU / 2 GB RAM / 20 GB disk;
- recorded base price 790 RUB/month;
- target cluster name `omni-cio-v10-ru-pg-synthetic` available.

## Purpose

This checkpoint adds the narrowly-authorized provider mutation needed to create one
synthetic Timeweb Cloud Managed PostgreSQL 18 cluster for RU-PG-B parity proof.

The source checkpoint itself must not create anything. Provider mutation is permitted
only from the accepted protected `main` through the dedicated manual workflow after
its exact source checkpoint has passed PR GREEN, squash merge and post-merge gates.

### Pre-mutation parity-transport gate

A paid cluster must not be created until the repository has accepted a concrete path
for the mandatory RU-PG-B PostgreSQL parity harness to reach that cluster.

Timeweb documents that a database intended only for its private network does not need
a public IP, but access from outside that private network requires public access.
Timeweb also documents that PostgreSQL TLS/domain setup is performed through public
access. The existing parity harness requires a real PostgreSQL connection with
`sslmode=verify-full` and an external CA root certificate.

Therefore the create workflow now fails closed before provider-secret access unless a
separate accepted transport checkpoint selects and proves exactly one of these modes:

- `TIMEWEB_PRIVATE_VPC_RUNNER` — parity executes from a proved Timeweb private-network
  runner/resource in the same accepted VPC;
- `PUBLIC_IPV6_PROVEN` — free public IPv6 is explicitly proved reachable and compatible
  with the required TLS/hostname-verification path;
- `PUBLIC_IPV4_OWNER_APPROVED` — the separately billed public IPv4 path is explicitly
  approved and security-reviewed. Timeweb currently lists public IPv4 as a separate
  200 RUB/month option, outside the recorded 790 RUB/month base DBaaS approval.

Until one mode is accepted, the machine-readable transport status remains
`BLOCKED_PENDING_PROOF` and the paid create job cannot reach the Timeweb credential.
This is intentionally stricter than merely creating an unreachable recurring-cost
resource and discovering the networking blocker afterwards.

## Cost and add-on boundary

The OWNER-recorded 790 RUB/month approval covers only the selected base DBaaS
configuration:

- PostgreSQL 18;
- Moscow / `ru-3` / `msk-1`;
- 1 CPU;
- 2048 MB RAM;
- 20480 MB disk.

Before POST, the workflow re-reads the provider presets and fails closed if the exact
resource tuple or base price has drifted.

This checkpoint does not authorize:

- public IPv4 purchase;
- public IPv6;
- provider backup add-ons;
- replicas;
- disk autoscaling;
- automatic scale-up;
- a higher recurring price;
- production DSN cutover.

Timeweb documents PostgreSQL 18 support and that public IPv4 is unnecessary when a
database is intended to remain on private networking. The 2 GB tier is also retained
because Timeweb documents that creating additional PostgreSQL users is unavailable
on the 1 CPU / 1 GB / 8 GB minimum tier.

Official references:

- https://timeweb.cloud/docs/dbaas/dbaas-create
- https://timeweb.cloud/docs/dbaas/postgresql
- https://timeweb.cloud/docs/dbaas/postgresql/users-and-privileges
- https://timeweb.cloud/docs/dbaas/postgresql/roles
- https://github.com/timeweb-cloud/sdk-go/blob/main/docs/DatabasesAPI.md
- https://github.com/timeweb-cloud/sdk-go/blob/main/docs/CreateCluster.md

## Manual workflow

Workflow:

`.github/workflows/v10-timeweb-postgres-synthetic-create.yml`

It is `workflow_dispatch` only and requires the exact confirmation value:

`CREATE_TIMEWEB_RU_PG_SYNTHETIC_790_RUB_MONTH`

The workflow is valid only on protected `main`.

Before the Timeweb credential can be consumed it:

1. bootstraps the exact protected-main SHA;
2. validates this create contract and source surface;
3. verifies that RU-PG-B parity transport is separately accepted and machine-readable;
4. verifies the GitHub Environment `timeweb-synthetic` main-only policy;
5. validates the exact confirmation value.

The provider credential remains an environment-scoped secret and is injected only
into the single creation step.

## Provider request

The provider adapter first re-discovers, using GET only:

- project `Общий проект`;
- the unique non-deprecated PostgreSQL 18 provider type;
- the exact `ru-3`, 1 CPU, 2048 MB, 20480 MB, 790 RUB preset;
- absence of the target cluster name in the selected project.

It then permits exactly one non-idempotent provider mutation:

`POST /api/v1/databases`

The request contains only reviewed cluster fields. It explicitly disables public IPv6
and disk autoscaling. It does not request a network/public IPv4, replicas, automatic
backups, backup schedule, inline admin, extra database instance or configuration
override.

The Timeweb API documents that a successful create may return while the resource is
still starting. The workflow therefore verifies the resulting cluster through GET
until `status=started` or a bounded timeout is reached.

## Ambiguous-create recovery

The create POST is never automatically retried.

A transport failure, transient HTTP failure after possible submit, oversized/malformed
201 body, or other lost-success-response condition enters reconciliation.

Reconciliation uses only GET against the already selected project and the exact target
cluster name:

- exactly one matching cluster -> continue with exact cluster verification;
- no matching cluster after bounded reconciliation -> STOP;
- more than one matching cluster -> STOP.

There is no blind second POST and no automatic DELETE cleanup in this checkpoint.
Deletion is a separate provider-authority boundary.

## Post-create verification

Before emitting success, the provider GET evidence must prove:

- exact target cluster identity by name and provider numeric ID;
- PostgreSQL 18 provider type selected during the same run;
- location `ru-3`;
- availability zone `msk-1`;
- 1 CPU / 2048 MB RAM / 20480 MB disk;
- the same exact preset selected during cost revalidation;
- public network disabled;
- public IPv6 disabled;
- automatic backups disabled;
- backup schedule disabled;
- no replicas;
- disk autoscaling disabled;
- cluster status `started`;
- the exact cluster remains attached to the selected project.

Only this sanitized marker is accepted:

`TIMEWEB_RU_PG_SYNTHETIC_CREATE=READY`

No token, provider ID, database host, username, password, DSN or response body is
allowed in logs, PRs, artifacts or chat.

## What this checkpoint does not prove

Creation does not certify RU-PG-B parity.

After successful cluster creation, RU-PG-B still requires a separate bootstrap/runtime
identity and PostgreSQL parity checkpoint using synthetic data only. The existing
proof harness remains:

`python -m scripts.prove_v10_ru_postgres_timeweb_parity`

That later proof must establish PostgreSQL 18, separate non-superuser bootstrap and
least-privilege runtime identities, migrations/idempotence, ALTER DEFAULT PRIVILEGES,
RLS/FORCE RLS, unscoped default deny and cross-tenant negative tests.

Required final parity marker:

`RU_PG_TIMEWEB_SYNTHETIC_PARITY=PASS`

Until that parity checkpoint is accepted, current Neon production authority remains
unchanged, production `OMNI_V10_POSTGRES_DSN` remains untouched and RU-PG-C remains
locked.
