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
- `OMNI_V10_POSTGRES_PRIVATE_HOSTADDR=<production PostgreSQL private IPv4>`
- `OMNI_V10_POSTGRES_PRIVATE_NETWORK_CIDR=<exact Timeweb private-network CIDR>`
- `OMNI_V10_TRUSTED_EDGE_TLS_TERMINATED=true`
- `PUBLIC_MULTI_USER_ENABLED=false`
- `OMNI_V10_TELEGRAM_LOGIN_ENABLED=false`
- `OMNI_V10_POSTGRES_DSN` present in Timeweb runtime custody.

The DSN keeps the Timeweb PostgreSQL technical hostname, `sslmode=verify-full` and
the canonical relative CA path. The private address is supplied separately. The runtime
uses the private address only as the TCP `hostaddr` while preserving the technical
hostname for SNI/certificate identity. The private host must be IPv4, inside the exact
RFC1918 Timeweb network CIDR selected for the App, and must not use Timeweb-reserved
service addresses. Do not replace the DSN host with a private IP and do not weaken TLS.

In `preactivation` mode, P2 does not accept Telegram credential custody and both public-user activation flags must remain false even if credentials were pre-provisioned outside this gate. A later `live-operable` continuous release preserves an already accepted P5 activation and requires its live-evidence digest; it does not create or rotate Telegram credentials.

## Observe mode

The manual workflow `.github/workflows/v10-timeweb-app-candidate.yml` first proves that
the requested SHA equals protected `main`, verifies the `timeweb-production` GitHub
Environment policy, then checks Timeweb application identity, autodeploy-off state,
runtime configuration, exact active commit, HTTPS `/livez` release identity, and
HTTPS `/healthz` database readiness. Candidate acceptance requires
`status=ok`, the exact release SHA, `database=READY`, and
`synthetic_preview=false`. A process-only `/livez` success is never sufficient proof
that the App Platform container can reach PostgreSQL on its own network path.

The Timeweb technical domain is allowed only as an additional trusted Host for candidate
verification. Browser Origin/CSRF authority remains canonical `https://omnicio.ru`.

## Runtime release modes

The controller has one fail-closed release implementation with two explicit states:

- `preactivation` is the default and requires `PUBLIC_MULTI_USER_ENABLED=false`, `OMNI_V10_TELEGRAM_LOGIN_ENABLED=false`, no P5 live-evidence digest, and no attached canonical `omnicio.ru` domain. This preserves the original P2 candidate gate.
- `live-operable` is allowed only after P5 is already accepted. It requires the two public/Telegram flags to be `true` together, requires `omnicio.ru` to remain attached, and requires the SHA-256 digest of the accepted P5 live evidence. Partial activation is rejected.

The evidence digest binds the release request to previously accepted P5 evidence; it does not create provider, legal, privacy or real-user acceptance. This controller still cannot patch application settings, credentials, DNS or provider registration. Those states must already exist through their owning gates.

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
