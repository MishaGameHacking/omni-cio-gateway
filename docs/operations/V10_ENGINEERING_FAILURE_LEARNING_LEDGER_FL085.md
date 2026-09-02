# V10 Engineering Failure Learning Ledger — FL085

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, exact-main
post-merge Web security evidence required by CF-D production release.

## Failure observed

After PR #436 was squash-merged, exact accepted candidate main
`1ae9225b14906b2a8ce1fdac7f2bea7345b5a463` completed `Regression Shield`
successfully. Several independent Web audits still failed closed while retrieving npm
security advisory metadata.

The first evidence showed concurrent retry streams from two runner services on physical
host `LAPTOP-NPSGA016`:

- `V10 WP16 Web Design System Audit` run `33694058921`, runner
  `omni-cio-ci-2`, received `ECONNRESET` on all three bounded attempts;
- `V10 WP22A Clientless Access Audit` run `33694058904`, runner
  `omni-cio-ci`, received the same transport failure on an almost identical retry
  schedule.

PR #440 exact-head evidence then proved that host serialization works but is not by
itself sufficient:

- WP22 run `33695387038` acquired the host slot and exhausted three serialized
  `ECONNRESET` attempts;
- WP19 run `33695387063` explicitly waited for that slot, then exhausted its own three
  serialized attempts;
- WP22A run `33695387116` also emitted the host-slot wait marker and then exhausted
  three serialized attempts;
- Fast PR run `33695386947` exhausted the same serialized retry path;
- WP16 run `33695387151` subsequently completed `npm audit` successfully on the same
  machine only seconds after another workflow had exhausted its third attempt.

No failing job returned an npm vulnerability report. Web type-check, lint, unit tests,
build and the surrounding repository/security contracts completed successfully before
the transport-only failure paths.

Current npm documentation confirms that `npm audit` submits dependency data using a POST
to the Bulk Advisory endpoint. npm's generic fetch retry configuration documents retry
behavior for idempotent registry reads, so this audit POST cannot rely on that setting as
its complete transport-recovery budget.

Independent PR review also exposed a portability defect in the first serialization
implementation: `tempfile.gettempdir()` may resolve to a per-service-account directory on
Windows, or to a service-private temporary namespace on POSIX. Although current exact-head
logs proved the installed Windows runner services were sharing the lock in this machine
configuration, a per-user temporary path is not an acceptable host-global invariant.

## Root cause class

`SELF_HOSTED_NPM_AUDIT_RETRY_WINDOW_AND_CONCURRENCY_GAP`

Three repository-controlled weaknesses are addressed:

1. sibling runner services could previously amplify the same transient failure with
   overlapping audit/retry streams;
2. after serialization removed that overlap, the accepted three-attempt / 5-second-base
   retry horizon still ended while the same endpoint later became reachable within the
   surrounding exact-head batch;
3. the first lock-file location depended on a process/service temporary directory instead
   of an explicit host-shared location.

The upstream/provider/network trigger for each `ECONNRESET` remains external and is not
claimed to be uniquely identified. npm's public status can remain operational while an
individual self-hosted path experiences a transient reset, so status alone is not
accepted as proof that the audit POST succeeded.

## Blast radius

The shared `scripts/run_v10_npm_audit.py` wrapper is consumed by the accepted Web audit
workflows for WP15 through WP22A and fast PR checks. A short transient advisory-endpoint
window can therefore block multiple otherwise-valid exact-head or exact-main gates.

The lock-location defect could affect any future deployment where sibling runner services
use distinct service accounts or isolated temporary namespaces, even though current
Windows exact-head evidence showed actual serialization on the OWNER host.

The package lock, npm version, audit level, security-result classification and
fail-closed behavior are not defective and are not relaxed by this correction.

## Corrective invariant

The mandatory npm security audit must now:

- acquire one host-local interprocess transport slot before the first `npm audit` call;
- hold that slot across the complete bounded retry/backoff sequence so sibling services
  cannot synchronize remote retries;
- use only standard-library OS file locking and no new dependency;
- on Windows, place the default lock under the host-global `SystemRoot\Temp`, never a
  per-user `TEMP`/`TMP` directory;
- support an explicit `OMNI_CIO_NPM_AUDIT_LOCK_ROOT` override for environments that need
  a separately provisioned host-shared lock root;
- fail closed if the Windows host-global root cannot be resolved or the lock file cannot
  be opened;
- use `/var/tmp` as the portable POSIX default; POSIX service deployments with isolated
  temporary namespaces must set the explicit host-shared lock-root override;
- wait at most 600 seconds for the host slot, then fail closed;
- use five attempts by default, which is the already-reviewed hard maximum;
- use a 15-second default linear backoff with each delay capped at 60 seconds, producing
  `15 / 30 / 45 / 60` seconds before attempts 2 through 5;
- release the OS lock when the wrapper exits, including exceptional exit;
- preserve the exact npm command and `high` audit threshold;
- retry only recognized transport/temporary registry failures;
- never retry or suppress a real npm audit vulnerability report;
- never fall back to a mirror, cached acceptance, disabled audit, `continue-on-error` or
  fabricated success.

## Directly coupled consumers

All accepted Web dependency-audit workflows already call the shared wrapper, so the
serialization and enlarged bounded retry horizon apply consistently without deleting or
softening any workflow-specific security step.

Deterministic regression coverage verifies that:

- Windows resolves the default lock to a host-global system temporary directory;
- an explicit host-shared lock root overrides the platform default;
- missing Windows system-root evidence fails closed;
- the complete retry sequence stays under one host transport slot;
- the default budget reaches a fifth attempt and uses exactly `15 / 30 / 45 / 60`
  seconds of bounded backoff;
- a custom large backoff remains capped at 60 seconds;
- lock acquisition failure returns RED before npm is invoked.

## Permanent learning

- Retry logic must account for concurrency at the physical-host boundary when multiple
  self-hosted runner services share one egress path.
- A cross-process lock is only as global as its namespace/path; per-user temporary
  directories are not an acceptable substitute for a host-global coordination surface.
- Removing concurrency amplification does not prove the external transport is healthy;
  exact-head evidence must still test whether the bounded retry horizon covers observed
  transient windows.
- Security transport resilience must not blur the distinction between transport failure
  and a vulnerability finding.
- Increasing a bounded retry horizon is acceptable only when the hard attempt/delay caps
  and fail-closed terminal result remain explicit.
- A transport-coordination or retry-exhaustion failure is never permission to skip the
  mandatory dependency audit.

## Security and authority invariants preserved

- Protected V9 `app:app` remains unchanged.
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged.
- broker write remains OFF.
- `trading_methods=false` remains unchanged.
- `REAL_TRADING_ENABLED=false` remains unchanged.
- No provider secret, token, provider identifier, connection URI or tenant-private
  payload is introduced or logged.
- No Cloudflare or Neon mutation is authorized by this CI transport correction.
