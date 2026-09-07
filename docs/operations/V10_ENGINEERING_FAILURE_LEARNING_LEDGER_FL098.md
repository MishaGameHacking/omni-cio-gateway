# V10 Engineering Failure Learning Ledger — FL098

Date: 2026-09-06  
Scope: CF-D exact-main pinned npm bootstrap transport resilience  
Authority: Amendment 8 + Amendment 12 + Amendment 14 + Amendment 15

## Observed failure

Accepted `main` `9a229f00663490b7e5aba871c9690de1f34c02dc` completed the
source correction from PR #452. The downstream `V10 Cloudflare Production Release`
run `34030081511`, job `101477874404`, then passed:

- exact accepted-main bootstrap;
- the exact-main post-merge workflow gate;
- Cloudflare provider authority readiness;
- Workers Builds authority readiness.

The run stopped at `Install exact Cloudflare delivery toolchain` before Container
registry authority, staging rehearsal, production database preparation, production
promotion, Custom Domain mutation or live acceptance could execute.

The installer emitted the existing sanitized terminal code:

`CLOUDFLARE_NPM_DOWNLOAD_FAILED`

The prior CF-D release run `34020979232` on accepted main
`555e5282f9564c729b5bd5f30a159b14f82dad0a` had successfully completed the same
delivery-toolchain step before reaching its later independent staging failure. PR #452
did not modify the delivery-toolchain downloader.

## Root cause class

`CF_D_PINNED_NPM_BOOTSTRAP_SINGLE_ATTEMPT_TRANSPORT_RESILIENCE_GAP`

The repository-controlled bootstrap downloaded the integrity-pinned npm 10.9.2 tarball
from the canonical npm registry with exactly one HTTPS request. Any `OSError`, including
`URLError`, `HTTPError` and timeout subclasses, was collapsed into the single
`CLOUDFLARE_NPM_DOWNLOAD_FAILED` code. The implementation therefore had two coupled
weaknesses:

1. an idempotent read of an immutable, integrity-pinned artifact had no bounded retry
   path for recognized transient registry/network failures;
2. retryable HTTP/transport failures and permanent HTTP/TLS/DNS failures lost their
   safe classification before the release gate could diagnose them.

The exact upstream subtype that caused run `34030081511` is not proven because the old
normalization intentionally discarded it. This entry does not relabel the provider or
network trigger as `ECONNRESET`, timeout, abrupt TLS EOF, HTTP 5xx or any other specific
external event without evidence.

## External behavior checked

Current npm documentation states that npm retries idempotent registry read requests on
network failures or HTTP 5xx responses and exposes bounded fetch retry settings. The
npm-owned `make-fetch-happen` transport additionally documents retry handling for safe
non-POST reads on HTTP 408/429/5xx and recognized transient connection failures.

Current Python 3.14 SSL documentation defines `ssl.SSLEOFError` as an `SSLError` raised
when an SSL connection is terminated abruptly and warns against reusing the affected
underlying transport. The installer retry path starts a fresh `open()` operation for the
next idempotent GET; it does not continue reading from the failed response. Therefore an
abrupt TLS EOF is treated as a bounded transient connection termination while certificate
verification failures and other generic TLS failures remain non-retryable.

The correction adopts only the bounded resilience principle. It does not import npm
cache/mirror behavior, disable TLS verification, follow redirects, widen the registry
origin or weaken the reviewed SHA-512 pin.

## Blast radius and directly coupled surfaces

Repository inspection found the same installer is used by both active Cloudflare delivery
paths:

- `.github/workflows/v10-cloudflare-candidate-deploy.yml` for CF-C staging acceptance;
- `.github/workflows/v10-cloudflare-production-release.yml` for CF-D exact-main release.

The correction therefore covers both candidate and production bootstrap rather than
patching only the failed workflow step.

Adjacent surfaces reviewed:

- exact Node/npm/Wrangler version checks;
- canonical npm tarball URL and redirect rejection;
- exact SHA-512 integrity verification;
- archive size/member/path/type limits and safe extraction;
- root `npm ci --ignore-scripts --no-audit --no-fund` execution;
- secret-safe workflow logs;
- the accepted host-serialized npm-audit retry design from FL085;
- TLS exception subclass ordering so certificate failures cannot be swallowed by a broad
  retry rule.

No dependency version or lockfile changes are required.

## Correction

The pinned npm bootstrap now:

1. keeps the exact canonical HTTPS tarball URL and redirect rejection;
2. keeps the exact reviewed SHA-512 verification unchanged;
3. retries at most five total attempts;
4. uses deterministic bounded linear delays of `15 / 30 / 45 / 60` seconds;
5. retries only recognized transient idempotent-read failures:
   - HTTP `408` and `429`;
   - HTTP `500-599`;
   - timeout/connection failures;
   - temporary DNS resolution (`EAI_AGAIN`);
   - incomplete HTTP reads;
   - abrupt TLS connection termination reported as `ssl.SSLEOFError`;
6. does not retry permanent HTTP statuses such as `401/403/404`;
7. does not retry redirect violations;
8. does not retry TLS certificate verification failures or generic TLS protocol/system
   failures; the narrowly classified abrupt EOF above is the only TLS-specific retry;
9. does not retry unknown URL/DNS/OS failures that are not explicitly classified as
   transient;
10. after exhausting the bounded retry budget, remains terminal RED;
11. logs only allowlisted failure class/status metadata, never exception text, URLs,
    headers, credentials or provider identifiers.

The retry loop is outside integrity and archive validation. A downloaded payload still
must pass the same exact integrity and safe-extraction gates before any npm code executes.

## Verification-batch findings and correction discipline

The first published DRAFT head `da08a945f1e0ac0364a5840ab5b6c5a834919cac`
completed 12 of 13 applicable Actions workflows successfully. The only RED was the
self-hosted authoritative merge gate: Ruff lint passed and `ruff format --check` requested
one deterministic formatting change in the new HTTP response-close branch. No semantic,
security, dependency, PostgreSQL or retry-policy failure was reported.

The exact Ruff formatting correction and final-newline hygiene were applied. The resulting
DRAFT head `db7e2f53baaf5a94a5e49d6f9d29b5186a2c3a2f` completed all 13 applicable Actions
workflows with terminal `success`, including the authoritative static-quality, Regression
Shield, dependency, SAST and tracked-secret stages. SonarQube Cloud also reported a
passing Quality Gate with no new issues or security hotspots.

During the required full-diff/adjacent-failure review after that batch, one remaining
resilience gap was found: `ssl.SSLEOFError` is a subclass of `ssl.SSLError`, so the broad
generic TLS branch would have classified an abrupt TLS connection termination as
permanent. Because the original CF-D failure subtype was lost by the old one-code
normalization, leaving that documented transient connection-termination class uncovered
would make the claimed permanent repair incomplete. The final correction therefore adds a
narrow `SSLEOFError -> TLS_EOF` transient branch before the generic TLS fail-closed branch
and adds both positive EOF-retry and negative generic-TLS regression coverage.

Any commit containing this adjacent correction invalidates the earlier DRAFT GREEN evidence
and requires a fresh exact-head batch before READY.

## Permanent regression guards

Deterministic tests now prove:

- transient connection reset -> bounded retry -> success;
- transient HTTP 503 -> bounded retry -> success;
- abrupt TLS EOF -> bounded retry -> success;
- generic TLS failure remains immediate fail-closed with no retry;
- five transient failures exhaust exactly five attempts with `15/30/45/60` backoff;
- retry policy is limited to HTTP 408/429/5xx and rejects representative permanent
  statuses;
- HTTP 403 is immediate fail-closed with no retry;
- HTTP redirect is immediate fail-closed with no retry;
- TLS certificate failure is immediate fail-closed with no retry;
- incomplete read is retryable;
- unknown URL failure remains non-retryable;
- retry diagnostics do not include raw exception details or the tarball URL;
- existing safe archive extraction and empty-version-output regressions remain passing.

The initial focused scratch preflight completed Python compilation and the then-current
modified delivery-toolchain quality suite successfully. That scratch environment could not
download the repository-pinned `ruff==0.16.1` because its PyPI DNS lookup failed, so no
local Ruff result was fabricated. The later authoritative DRAFT gate provided the real
Ruff/format evidence described above. The final adjacent TLS-EOF correction still requires
fresh exact-head verification and is not accepted by documentation alone.

## Permanent learning

- An immutable integrity-pinned artifact can still require transport retries; transport
  resilience and supply-chain trust are separate properties.
- Retry only the idempotent network operation, never the integrity or authority decision.
- A safe retry contract needs both a hard attempt/time bound and a permanent-vs-transient
  classifier.
- TLS retry classification must be subclass-aware: certificate/authentication failures stay
  permanent, while a specifically documented abrupt connection EOF may be retried only by
  starting a new bounded read attempt.
- Sanitized diagnostics should preserve failure class/status without echoing exception
  text or network targets.
- Existing failure-learning should be propagated to analogous bootstrap consumers;
  FL085 already proved that npm registry transport can be transient on the shared
  self-hosted environment.
- A successful earlier run proves dependency compatibility but not future network
  availability; exact-head release bootstrap must tolerate bounded transient transport
  while still failing closed after exhaustion.

## Security and authority invariants preserved

- protected V9 `app:app` remains unchanged;
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged;
- broker write remains OFF;
- `trading_methods=false` remains unchanged;
- `REAL_TRADING_ENABLED=false` remains unchanged;
- no transfer/withdrawal/margin/leverage/uncovered-short authority is introduced;
- no provider token, database credential, private identifier or tenant payload is logged
  or committed;
- no Cloudflare/Neon/DNS/domain mutation is authorized by this repair;
- no dependency version, npm registry origin, TLS certificate policy or integrity pin is
  widened.

## Acceptance rule

This defect is not accepted merely because source/tests are corrected. Acceptance requires
all applicable exact-head PR checks to conclude `success`, zero unresolved blocking review
threads, squash merge, exact-new-main Regression Shield success and a fresh exact-main
Cloudflare production release that proves the formerly blocked delivery-toolchain step and
the downstream gated release path. Any later provider failure remains RED and must be
classified separately rather than hidden by this transport repair.
