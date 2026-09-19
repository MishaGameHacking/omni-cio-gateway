# V10 RU-PG-B — Timeweb Control-Plane Read-Only Proof

Status: **SOURCE READY / LIVE DISPATCH BLOCKED ON ENVIRONMENT EVIDENCE**

Owning issue: #559  
Accepted base: `b3d2e1dba80b2b6ebc004f70f27bcc2b8c8e7ff8`

## Purpose

This checkpoint adds the protected-main workflow that will collect the first real
Timeweb RU-PG-B provider evidence. The workflow remains read-only: it may discover
provider metadata through the approved Public API adapter, but it may not create,
update or delete any Timeweb resource.

The existing PostgreSQL 18 migrations, tenant model, RLS/FORCE RLS, runtime-role
convergence and recovery semantics remain the application/database authority.
Timeweb replaces only the provider-specific control-plane boundary. Neon production authority is preserved until a later accepted cutover.

## OWNER environment gate

GitHub environment `timeweb-synthetic` contains the environment secret named
`TIMEWEB_CLOUD_API_TOKEN`. The secret value must never appear in source, chat,
screenshots, PR comments, logs or artifacts.

Before the new workflow may be dispatched, the environment must be configured as:

- Deployment branches and tags: **Selected branches and tags**;
- exactly one Branch rule: `main`;
- no wildcard branch or tag rule that broadens access.

The repository does not claim that external setting is accepted until direct OWNER
or API evidence proves it. Until then, do not dispatch the workflow.

GitHub documents that a job referencing an environment must satisfy its protection
rules before it can access environment secrets. The workflow also fails closed at
source level unless `github.ref == 'refs/heads/main'`.

Official GitHub reference:

- https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments

## Read-only workflow

Canonical workflow:

`.github/workflows/v10-timeweb-postgres-readonly-proof.yml`

Properties:

- manual `workflow_dispatch` only;
- exact ref must be `refs/heads/main`;
- environment must be `timeweb-synthetic`;
- `contents: read` is the only repository permission;
- the provider credential is injected only into the single probe step;
- source contract verification runs before the secret-consuming step;
- the self-hosted workspace is cleaned in an `always()` step;
- no provider identifiers or response bodies are accepted output.

## Why Public API, not Timeweb Terraform mutation yet

Timeweb supports both Terraform and Public API automation. The current OWNER token
keeps Telegram deletion confirmation enabled. Disabling that confirmation merely to
use Terraform would widen destructive authority, and Terraform state would add a new
custody/recovery boundary that is unnecessary for provider parity.

Therefore this RU-PG-B checkpoint uses the stateless Public API adapter and permits
only HTTP GET.

Official references:

- https://timeweb.cloud/docs/account-management/token
- https://timeweb.cloud/docs/terraform/nachalo-raboty-s-terraform
- https://timeweb.cloud/docs/dbaas/dbaas-create
- https://timeweb.cloud/docs/dbaas/postgresql/users-and-privileges

## Live discovery contract

`scripts/probe_v10_timeweb_postgres_control_plane.py` queries only:

- `GET /api/v1/projects`;
- `GET /api/v1/database-types`;
- `GET /api/v2/presets/dbs`;
- `GET /api/v1/projects/{project_id}/resources/databases`.

The probe must verify, without emitting provider identifiers:

- exactly one project named `Общий проект`;
- a non-deprecated PostgreSQL 18 provider type from live metadata;
- location `ru-3` / MSK-1;
- 1 CPU;
- 2048 MB RAM;
- 20480 MB / 20 GB disk;
- exact approved base price 790 RUB/month;
- no existing cluster named `omni-cio-v10-ru-pg-synthetic`.

Timeweb documents PostgreSQL 18 support. It also documents that the minimum
1 CPU / 1 GB / 8 GB tier cannot create additional PostgreSQL users, so that tier
cannot satisfy Omni-CIO's required bootstrap/runtime identity separation.

Price or preset drift fails closed and requires fresh OWNER cost review instead of
silently selecting a different resource.

Accepted sanitized success marker:

`TIMEWEB_RU_PG_CONTROL_PLANE=READ_ONLY_READY`

No token, project ID, preset ID, account ID, response body, database hostname, DSN,
password or private payload may appear in accepted evidence.

## Mutation boundary

This checkpoint does not create or modify:

- a Timeweb database cluster;
- public IPv4;
- VPC/network objects;
- backup add-ons;
- production or staging Cloudflare database secrets;
- production `OMNI_V10_POSTGRES_DSN`;
- Neon resources.

Only after the environment restriction is proven and the live read-only run returns
the sanitized marker may RU-PG-B proceed to a separate paid synthetic-cluster
creation checkpoint. RU-PG-C remains locked until the complete RU-PG-B parity gate
is `CERTIFIED_GREEN`.
