# V10 RU-PG-B — Timeweb Synthetic PostgreSQL 18 Create Runbook

Status: **SOURCE READY / PUBLIC IPv4 TRANSPORT SOURCE SELECTED; LIVE MUTATION STILL MANUAL**

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

The accepted transport source now selects `PUBLIC_IPV4_OWNER_APPROVED` after the
OWNER separately approved one public IPv4 up to 200 RUB/month and the repository
added the dedicated firewall/TLS checkpoint.

This does not make the database public during cluster creation. The create POST stays
private-only. Public exposure is a separate manual protected-main mutation that must
first install and verify a DROP firewall with exactly one TCP/5432 verifier /32 rule,
keep IPv6 and the DDoS add-on off, and require provider TLS plus hostname
verification.

The /32 verifier allowlist is RU-PG-B synthetic-proof authority only. It is not
Cloudflare production-network authority and is not inherited by RU-PG-C.

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

The separately accepted network checkpoint authorizes one public IPv4 up to
200 RUB/month for RU-PG-B synthetic verification, but this cluster-create request
does not purchase or attach it. The network workflow owns that later mutation.

This checkpoint does not authorize:

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
- https://github.com/timeweb-cloud/sdk-go/blob/main/docs/PresetsDbs.md
- https://github.com/timeweb-cloud/sdk-go/blob/main/docs/DatabaseClusterDisk.md

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
still starting. The workflow therefore uses state-aware GET verification until
`status=started` or a bounded timeout is reached; exact terminal shape is required
before READY is emitted.

### Provider disk unit contract

Timeweb exposes two different disk units on the provider surfaces used here. The
DB preset field `disk` is reported in MB, while the created
`DatabaseCluster.disk.size` field returned by cluster GET is reported in KB.
Therefore the accepted 20 GB target is `20480 MB` during preset selection and
must be exactly `20971520 KB` during cluster verification.

The verifier accepts only an exact positive integral provider value. It does not
round, truncate or apply tolerance: undersize, oversize, fractional or malformed
cluster disk values fail closed. This prevents a provider-unit mismatch from
either producing a false drift or hiding a real disk drift.

## Live recovery after accepted POST

Live run `35479350478` proved an important recovery case: the provider POST
succeeded far enough for the exact target cluster to exist, while the first
post-create verification stopped with `TIMEWEB_CLUSTER_POST_CREATE_DRIFT`.

A subsequent safe read-only proof confirmed the exact target already exists.
Therefore a retry of this workflow must never issue a second POST merely because
the previous run did not reach the READY marker.

If exactly one target cluster already exists in the selected project, the
provisioner enters `existing-recovery` mode. That mode is GET-only until the
existing resource has passed the same exact terminal verification. A second
cluster-create POST is forbidden.

Accepted automatic Read-Only Proof run `35507498165` on exact main `3a96dfe88e99aac754d8949725122295dd957429` observed the existing approved cluster with `replica_list_count=1`. Synthetic create/recovery therefore no longer assumes that the raw provider list must be empty. Terminal verification requires exactly the accepted provider count of `1`, validates member custody against the target cluster and rejects duplicate members. During provider `starting` convergence only a missing or empty transient list is tolerated; an explicit non-baseline count fails closed immediately. This count-only contract does not authorize Timeweb's separately priced replication option.

The Timeweb API documents that a newly-created resource may be returned while
still starting. Verification is therefore state-aware:

- while `status=starting`, explicit unsafe values (public network/IPv6,
  backups, replicas or disk autoscaling) fail closed immediately, while
  provider fields that have not materialized yet are allowed to converge
  within the existing bounded start window;
- at `status=started`, every required identity/configuration field is
  mandatory and must match exactly;
- terminal drift emits field-specific sanitized stop codes so provider-state
  mismatches can be diagnosed without logging response bodies, provider IDs or
  secrets.

The provider-readiness budget is deliberately multi-minute and remains below the enclosing workflow timeout. A locally chosen wait vector is not a Timeweb SLA: create acceptance, project-list visibility and terminal `started` readiness are separate observations. Ambiguous create reconciliation remains GET-only and never authorizes a second POST.

### Live start-readiness failure learning from workflow ordinal #6

The 2026-09-27 manual create/recovery run reached the exact target cluster and then stopped with:

`TIMEWEB_CLUSTER_START_TIMEOUT`

The step duration matched the old source-defined start waiter closely: the old delay vector totalled only 288 seconds. That result does **not** prove that Timeweb rejected or lost the cluster. The provisioner emits that code only after it has observed provider state but has not proved terminal `started` before its local budget expires. Because create acceptance and provider readiness are separate observations, a safe `starting` resource must not be converted into a second create attempt.

The corrected source therefore:

- keeps the single-create / no-blind-replay authority unchanged;
- extends the GET-only start-readiness budget to 708 seconds;
- bounds every synthetic-create control-plane GET to a 10-second provider read attempt, including credential health, target discovery, ambiguous-create reconciliation, startup readiness and final project-custody verification;
- keeps the create POST itself at one bounded 30-second attempt;
- increases only the enclosing create job timeout to 60 minutes so the complete worst-case provider phase — pre-create reads, one ambiguous POST, GET-only reconciliation, the 708-second readiness delays, nested read retries and final custody read — still retains more than twenty minutes of workflow headroom;
- emits `TIMEWEB_CLUSTER_STARTING_READY_TIMEOUT` when the last valid provider state is still `starting`, while preserving a distinct control-plane-read timeout;
- keeps every unsafe status or explicit configuration drift immediately terminal;
- preserves restart safety: if the exact target already exists, a later run enters `existing-recovery` and remains GET-only.

If the new bounded budget is exhausted while Timeweb still reports `starting`, stop and reconcile provider state rather than widening authority, issuing another POST, deleting the cluster, or inventing a provider SLA.

The workflow ceiling is not calculated from sleep delays alone. Every control-plane GET inherits the client's bounded retry behavior, and an ambiguous create can consume its own GET-only reconciliation window before startup observation begins. The safety proof therefore includes the maximum socket-attempt timeout, the two existing inner retry sleeps, the reconciliation delay vector, the 708-second start delay vector, the single bounded POST and the final custody read. This prevents GitHub Actions from terminating the job before the provisioner can emit its own sanitized reconciliation/readiness result during a prolonged provider/network incident.

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
- provider replica-list baseline count is exactly `1`;
- additional paid replication remains unauthorized;
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

Until that parity checkpoint is accepted, no production database cutover is authorized.
Production `OMNI_V10_POSTGRES_DSN` remains untouched and RU-PG-C remains locked.
