# V10 Timeweb App Platform Exact-SHA Candidate Runbook

Scope: branch-local `P2_TIMEWEB_EXACT_SHA_CANDIDATE` under Amendment 21.

This runbook does not authorize App Platform creation, paid-capacity changes, immutable
network selection, production PostgreSQL cutover, `omnicio.ru` DNS/TLS mutation,
Telegram credential activation, public-user activation, broker write, or Real Trading.

## Preconditions

The existing Timeweb application must be a Docker backend named `omni-cio-v10`, sourced
from `MishaGameHacking/omni-cio-gateway` branch `main`, with autodeploy disabled.
The controller accepts only one explicit 40-character protected-main SHA. It does not
create, resize, delete, stop, or patch the application.

Required runtime configuration for P2:

- `OMNI_V10_HOSTED_RUNTIME=1`
- `OMNI_V10_PUBLIC_HOSTNAME=omnicio.ru`
- `OMNI_V10_CANDIDATE_HOSTNAME=<Timeweb technical domain>`
- `OMNI_V10_RELEASE_SHA=<exact protected-main SHA>`
- `OMNI_V10_POSTGRES_RUNTIME_ROLE=omni_cio_hosted_api`
- `OMNI_V10_TRUSTED_EDGE_TLS_TERMINATED=true`
- `PUBLIC_MULTI_USER_ENABLED=false`
- `OMNI_V10_TELEGRAM_LOGIN_ENABLED=false`
- `OMNI_V10_POSTGRES_DSN` present in Timeweb runtime custody.

P2 does not accept Telegram credential custody. Public-user and Telegram activation flags
must remain false even if credentials were pre-provisioned outside this gate.

## Observe mode

The manual workflow `.github/workflows/v10-timeweb-app-candidate.yml` first proves that
the requested SHA equals protected `main`, verifies the `timeweb-production` GitHub
Environment policy, then checks Timeweb application identity, autodeploy-off state,
runtime configuration, exact active commit, and HTTPS `/livez` release identity.

The Timeweb technical domain is allowed only as an additional trusted Host for candidate
verification. Browser Origin/CSRF authority remains canonical `https://omnicio.ru`.

## Deploy mode

Deploy requires the exact confirmation string:

`DEPLOY_EXACT_TIMEWEB_APP_COMMIT`

The only provider mutation authorized by this P2 controller is:

`POST /api/v1/apps/{app_id}/deploy`

with only `commit_sha=<exact protected-main SHA>`.

The POST is never retried blindly. If its outcome is ambiguous, reconciliation is GET-only
against deployment history and succeeds only when exactly one new deploy for the expected
SHA exists. Provider free-form deploy logs are not read.

## Acceptance and rollback boundary

The controller records the most recent distinct successful provider deployment SHA as
`last_known_good_sha`, but P2 does not perform automatic rollback. Rollback remains a
later explicit acceptance transition to an exact previously successful SHA.

P2 is `CERTIFIED_GREEN` only after its repository implementation passes the complete
exact-head DRAFT verification. Physical candidate execution occurs only after accepted
main plus the independent Timeweb application/environment gates. P3 PostgreSQL production
cutover remains blocked until then.
