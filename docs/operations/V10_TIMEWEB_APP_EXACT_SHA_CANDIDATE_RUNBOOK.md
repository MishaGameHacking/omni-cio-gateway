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

Initial App creation is an OWNER/provider-panel action. The current documented public
Timeweb CreateApp schema does not expose the immutable private-network selection that the
Docker App requires, while Timeweb documents that the selected private network cannot be
changed in place after creation. Therefore do not replace the panel creation step with an
API create call that cannot bind the accepted network. After the application exists, this
controller may manage only the separately authorized exact-SHA deploy operation.

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

The provider-assigned App technical domain does not exist until the application has been
created. During that one creation-time bootstrap only, `OMNI_V10_CANDIDATE_HOSTNAME`
may be absent so the container can start and Timeweb can perform its localhost
`/livez` health check. This is **not** P2 acceptance. As soon as Timeweb assigns the
technical domain, add it as `OMNI_V10_CANDIDATE_HOSTNAME`, keep autodeploy disabled and
the selected private network unchanged, redeploy the same exact accepted-main SHA, and
only then run P2 `observe`/`deploy`. P2 remains fail-closed while that hostname is
missing or not attached to the application.

The DSN keeps the Timeweb PostgreSQL technical hostname, `sslmode=verify-full` and
the canonical relative CA path. The private address is supplied separately. The runtime
uses the private address only as the TCP `hostaddr` while preserving the technical
hostname for SNI/certificate identity. The private host must be IPv4, inside the exact
RFC1918 Timeweb network CIDR selected for the App, and must not use Timeweb-reserved
service addresses. Do not replace the DSN host with a private IP and do not weaken TLS.

In `preactivation` mode, P2 does not accept Telegram credential custody and both public-user activation flags must remain false even if credentials were pre-provisioned outside this gate. A later `live-operable` continuous release preserves an already accepted P5 activation and requires its live-evidence digest; it does not create or rotate Telegram credentials.

## Cross-gate execution ordering

P2 repository certification and P3 database execution are interleaved deliberately to
avoid a circular dependency:

1. P2 source implementation may be certified and merged before any paid App exists.
2. P3 `observe` may run before App creation because it is a read-only production-target
   prerequisite proof.
3. P3 `prepare` and the required recovery evidence must complete before physical App
   creation/candidate execution, because `/healthz database=READY` depends on the
   canonical schema, runtime ACL and RLS/FORCE-RLS state.
4. Create the Timeweb App once, in the already accepted private network, then complete the
   technical-domain bootstrap and exact-SHA P2 `/livez` plus `/healthz` candidate proof.
5. P3 `accept` runs only after that current physical candidate proof and independently
   repeats it. P3 acceptance is therefore downstream of physical P2 evidence, while P3
   preparation is upstream of physical P2 evidence.

A source-GREEN P2 result is not permission to skip P3 preparation, and a successful P3
prepare is not P3 acceptance.

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

P2 source implementation is `CERTIFIED_GREEN` only after complete exact-head DRAFT
verification. Physical candidate execution additionally requires accepted main, completed
P3 preparation/recovery prerequisites, and the independent Timeweb application/environment
gates. P3 final acceptance remains blocked until the current physical P2 technical-domain
candidate proves both exact-SHA liveness and real database readiness.
