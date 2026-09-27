# V10 RU-PG-B — Timeweb Control-Plane Read-Only Proof

Status: **SOURCE READY / MACHINE ENVIRONMENT GATE PENDING LIVE EVIDENCE**

Owning issue: #559  
Accepted base: `3a1bd050d596b2e05f73a72f93199f4e2944f94b`

## Purpose

This checkpoint adds the protected-main workflow that will collect the first real
Timeweb RU-PG-B provider evidence. The workflow remains read-only: it may discover
provider metadata through the approved Public API adapter, but it may not create,
update or delete any Timeweb resource.

The existing PostgreSQL 18 migrations, tenant model, RLS/FORCE RLS, runtime-role
convergence and recovery semantics remain the application/database authority.
Timeweb is the only selected provider-specific control-plane boundary. Neon external authority is unavailable after the OWNER-reported decommission; no Neon rollback or new provider mutation path is allowed.

## Machine-verified environment gate

GitHub environment `timeweb-synthetic` contains the environment secret named
`TIMEWEB_CLOUD_API_TOKEN`. The secret value must never appear in source, chat,
screenshots, PR comments, logs or artifacts.

Before the provider credential can be consumed, the workflow now performs a
machine-verifiable GitHub REST proof that the environment uses selected deployment
refs instead of an unrestricted or protected-branches-only mode. The verifier
requires:

- `deployment_branch_policy.protected_branches=false`;
- `deployment_branch_policy.custom_branch_policies=true`;
- exactly one custom deployment policy;
- exact policy name `main`;
- if GitHub exposes a policy `type` field, it must be `branch`;
- no wildcard or second policy is accepted.

GitHub's documented list-response example does not include a policy `type` field.
When that field is absent, branch-vs-tag semantics are still enforced by GitHub
itself: the provider job references `timeweb-synthetic` from
`GITHUB_REF=refs/heads/main`, and GitHub documents that branch and tag patterns are
configured separately and matched against `GITHUB_REF`. A tag-only `main` rule
therefore cannot admit the branch-backed provider job.

The pre-secret job does **not** reference the Timeweb provider secret. It uses only
the workflow `GITHUB_TOKEN` with `actions: read`, because GitHub documents that
the environment and deployment-branch-policy read endpoints require Actions read
permission for private repositories. The same policy is re-checked immediately
before the provider step.

Accepted sanitized environment marker:

`TIMEWEB_GITHUB_ENVIRONMENT_GATE=READY`

The verifier reads only:

- `GET /repos/{owner}/{repo}/environments/timeweb-synthetic`;
- `GET /repos/{owner}/{repo}/environments/timeweb-synthetic/deployment-branch-policies?per_page=100&page=1`.

It uses bounded GET retries, disallows redirects and never emits policy IDs,
environment IDs, response bodies or token values.

If the machine gate fails because the environment is not configured for selected
branches/tags, the OWNER-only correction remains:

1. Repository **Settings** -> **Environments** -> `timeweb-synthetic`;
2. Deployment branches and tags -> **Selected branches and tags**;
3. add exactly one **Branch** rule named `main`;
4. remove any broader branch/tag rule;
5. save the protection rule and rerun the read-only proof.

Do not paste the provider token into chat, issues, pull requests or logs.

GitHub documents that environment protection rules must pass before a job can use
environment secrets, and that custom deployment branch policies are exposed through
the deployment environment REST API.

Official GitHub references:

- https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments
- https://docs.github.com/en/rest/deployments/environments
- https://docs.github.com/en/rest/deployments/branch-policies

## Read-only workflow

Canonical workflow:

`.github/workflows/v10-timeweb-postgres-readonly-proof.yml`

Properties:

- automatic read-only execution is triggered only after a successful
  `Regression Shield` `workflow_run` for branch `main`;
- the upstream Regression Shield run itself must be the normal `push` path on
  protected `main`, not a manually dispatched verification;
- manual `workflow_dispatch` on `main` remains an explicit fallback;
- the exact target SHA is taken from `github.event.workflow_run.head_sha` for the
  automatic path and is re-checked against the current `refs/heads/main` before
  any provider secret can be consumed;
- if a newer `main` supersedes the accepted upstream SHA while this proof is
  queued, the proof fails closed instead of observing stale provider state;
- repository permissions are limited to `contents: read` and `actions: read`;
- a first job proves the exact GitHub environment policy without referencing the
  Timeweb provider credential;
- the provider job has `needs: environment-policy-proof`;
- environment must be `timeweb-synthetic`;
- the environment policy is re-verified immediately before provider access;
- the provider credential is injected only into the single Timeweb GET probe step;
- source contract verification runs before any provider-secret consumption;
- both self-hosted workspaces are cleaned in `always()` steps;
- no provider identifiers or response bodies are accepted output.

### Automatic post-merge sequencing

The automatic trigger exists to remove a proven human/workflow sequencing hazard:
after PR #570 accepted the count-only replica diagnostic, Synthetic Create #4 was
manually dispatched before the new Read-Only Proof had collected the required
topology evidence. That run correctly failed closed on the still-existing raw
replica guard, but it could not exercise the diagnostic introduced by #570.

The read-only proof therefore follows the GitHub-native post-merge Regression
Shield directly. It inherits **no** provider mutation or paid-transition authority.
GitHub documents that `workflow_run` can access secrets, so this workflow treats
that event as privileged: it accepts only a successful trusted `push` run for
protected `main`, bootstraps only the upstream exact SHA, verifies that SHA is
still current `main`, retains read-only `GITHUB_TOKEN` permissions, re-verifies
the protected environment immediately before access, and executes only the GET-only
Timeweb adapter. It never depends on a retired Cloudflare/Neon release workflow and
never consumes artifacts or code from an untrusted PR.

Official GitHub references:

- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- https://docs.github.com/en/actions/reference/security/secure-use

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

## Credential-health classification

Timeweb credential lifecycle is an external provider-authority boundary. A GitHub
environment secret being present does not prove that the provider still accepts it.

Every write-capable Timeweb path must first complete a GET-only credential/read
preflight against the exact RU-PG-B project. The shared adapter classifies the two
authorization outcomes without reading or logging the provider response body:

- HTTP `401` -> `TIMEWEB_API_AUTHENTICATION_REJECTED`;
- HTTP `403` -> `TIMEWEB_API_AUTHORIZATION_REJECTED`.

Neither status is retried. Bounded retries remain limited to the separately accepted
transient network/rate/service-unavailable statuses. Token values and provider response
bodies must never appear in logs, issues, PRs, artifacts or chat.

Timeweb documents that API tokens have an explicit lifetime, may have restricted
permissions, and that reissuing a token invalidates the previous value. Provider-token
repair or GitHub environment-secret rotation is therefore an external OWNER action and
does not itself grant database/network mutation authority.

## Live discovery contract

`scripts/probe_v10_timeweb_postgres_control_plane.py` queries only:

- `GET /api/v1/projects`;
- `GET /api/v1/database-types`;
- `GET /api/v2/presets/dbs`;
- `GET /api/v1/projects/{project_id}/resources/databases`;
- when the exact target already exists, `GET /api/v1/databases/{cluster_id}`.

The probe must verify, without emitting provider identifiers:

- exactly one project named `Общий проект`;
- a non-deprecated PostgreSQL 18 provider type from live metadata;
- location `ru-3` / MSK-1;
- 1 CPU;
- 2048 MB RAM;
- 20480 MB / 20 GB disk;
- exact approved base price 790 RUB/month;
- the target cluster name is either absent or resolves to exactly one provider
  object;
- target absence is a valid pre-create read-only state: the control-plane marker remains
  `READ_ONLY_READY`, while the account-level IPv4 observer must return a successful
  observation with recovery explicitly `BLOCKED` as
  `TIMEWEB_IPV4_TARGET_ABSENT`; target absence must never fabricate custody or mutation
  authority;
- if that exact target already exists, its cluster detail is read with GET only
  and only the sanitized `replica_list_count` is emitted.

### Existing-target replica topology diagnostic

Live Synthetic Create run #3 on accepted main reached
`TIMEWEB_CLUSTER_REPLICAS_PRESENT` after the disk-unit defect had already been
repaired. The read-only control-plane proof therefore owns a count-only diagnostic
for the exact existing target.

Accepted sanitized observation marker:

`TIMEWEB_RU_PG_REPLICA_TOPOLOGY=OBSERVED`

The marker may contain only `replica_list_count`, the source-controlled
`contract_replica_list_count=1`, a numeric relation, and
`semantics=COUNT_ONLY_BASELINE`. It must never emit cluster IDs, replica IDs, private IPs,
response bodies or provider credentials.

This observation is deliberately not an authorization decision. Timeweb's current
documentation uses different replica wording across surfaces: the DBaaS creation
flow describes optional PostgreSQL/MySQL replication with additional replica
choices and recurring cost, while the DBaaS Operator documents
`replica_count` values including `1`. Until live provider shape is correlated
with those documented semantics, a matching numeric count must not be interpreted
as proof that paid replication is authorized or absent. The existing synthetic
create and public IPv4/TLS guards therefore remain fail-closed.

Accepted automatic Read-Only Proof run `35507498165` on exact main `3a96dfe88e99aac754d8949725122295dd957429` observed `replica_list_count=1` with `relation=matches_contract_count`. This count is the canonical RU-PG-B provider baseline. The runtime verifier requires exactly one provider-list member for terminal state, validates cluster custody and unique member IDs, and rejects count drift. This count-only baseline does not grant Timeweb's separately priced replication option; additional paid replication remains unauthorized.

Official replica references:

- https://timeweb.cloud/docs/dbaas/dbaas-create
- https://timeweb.cloud/docs/k8s/addons/dbaas-operator
- https://github.com/timeweb-cloud/sdk-go/blob/main/docs/DatabaseCluster.md
- https://github.com/timeweb-cloud/sdk-go/blob/main/docs/DatabaseClusterReplicaListInner.md

Timeweb documents PostgreSQL 18 support. It also documents that the minimum
1 CPU / 1 GB / 8 GB tier cannot create additional PostgreSQL users, so that tier
cannot satisfy Omni-CIO's required bootstrap/runtime identity separation.

Price or preset drift fails closed and requires fresh OWNER cost review instead of
silently selecting a different resource.

Accepted sanitized success marker:

`TIMEWEB_RU_PG_CONTROL_PLANE=READ_ONLY_READY`

When the exact target exists, the same successful read-only run must also emit
`TIMEWEB_RU_PG_REPLICA_TOPOLOGY=OBSERVED`; provider terminology remains count-only and additional paid replication remains unauthorized.

No token, project ID, preset ID, account ID, response body, database hostname, DSN,
password or private payload may appear in accepted evidence.

## Mutation boundary

This checkpoint does not create or modify:

- a Timeweb database cluster;
- public IPv4;
- VPC/network objects;
- backup add-ons;
- retired provider runtime secrets;
- production `OMNI_V10_POSTGRES_DSN`;
- retired Cloudflare/Neon resources.

Only after the machine environment gate returns
`TIMEWEB_GITHUB_ENVIRONMENT_GATE=READY` and the same protected-main run returns
`TIMEWEB_RU_PG_CONTROL_PLANE=READ_ONLY_READY` may RU-PG-B proceed to a separate
paid synthetic-cluster creation checkpoint. RU-PG-C remains locked until the
complete RU-PG-B parity gate is `CERTIFIED_GREEN`.
