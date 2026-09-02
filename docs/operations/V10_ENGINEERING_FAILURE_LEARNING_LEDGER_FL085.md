# V10 Engineering Failure Learning Ledger — FL085

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, exact-main
post-merge Web security evidence required by CF-D production release.

## Failure observed

After PR #436 was squash-merged, exact accepted candidate main
`1ae9225b14906b2a8ce1fdac7f2bea7345b5a463` completed `Regression Shield`
successfully. Several independent Web audits still failed closed while retrieving npm
security advisory metadata.

The most useful evidence came from the second exact-main attempts of two workflows on
the same physical Windows host:

- `V10 WP16 Web Design System Audit` run `33694058921`, runner
  `omni-cio-ci-2`, started its npm audit at `23:22:55Z` and received `ECONNRESET` on
  all three bounded attempts at approximately `23:23:07Z`, `23:23:24Z` and
  `23:23:47Z`;
- `V10 WP22A Clientless Access Audit` run `33694058904`, runner
  `omni-cio-ci`, started the same audit at `23:22:52Z` and received `ECONNRESET` on
  all three bounded attempts at approximately `23:23:05Z`, `23:23:22Z` and
  `23:23:44Z`.

Both runner services reported machine `LAPTOP-NPSGA016`. Their registry requests and
retry windows therefore overlapped almost exactly. The same exact-main batch also
contained successful npm audits in other workflows, and the WP21 rerun later completed
its audit successfully. No npm vulnerability report was returned in the failing jobs.

The existing FL074 wrapper correctly recognized the transport class, retried only that
class and stayed RED after exhaustion. The newly exposed repository-side defect was that
multiple runner services on one physical host could independently enter the same remote
security-audit retry loop at the same time, creating avoidable duplicate transport load
and synchronized retries.

## Root cause class

`SELF_HOSTED_NPM_AUDIT_HOST_CONCURRENCY_GAP`

The provider/network layer remains external, so the evidence does not claim that local
concurrency is the sole cause of every npm `ECONNRESET`. It does prove that Omni-CIO's
self-hosted contour allowed concurrent identical audit calls from two services on the
same machine during the observed failure window. That is an avoidable amplification
path inside repository control.

## Blast radius

The shared `scripts/run_v10_npm_audit.py` wrapper is consumed by the accepted Web audit
workflows for WP15 through WP22A and fast PR checks. Any two jobs scheduled to separate
runner services on the same Windows host could previously overlap their remote audit
attempts.

The security classification logic, package lock, npm version, audit level and
fail-closed result handling are not defective and are not relaxed by this correction.

## Corrective invariant

The mandatory npm security audit must now:

- acquire one host-local interprocess transport slot before the first `npm audit` call;
- hold that slot across the complete bounded retry/backoff sequence so a second runner
  service cannot synchronize retries with the first;
- use only standard-library OS file locking and no new dependency;
- wait only a bounded 180 seconds for the host slot;
- fail closed if the lock cannot be opened/acquired within the bound;
- release the OS lock when the wrapper exits, including exceptional exit;
- preserve the existing three-attempt default, maximum attempt bound, audit level,
  exact npm command and recognized-transient classification;
- never retry a real npm audit report/security finding;
- never fall back to a mirror, cached acceptance, disabled audit, `continue-on-error` or
  fabricated success.

## Directly coupled consumers

Because all accepted Web dependency audits already call the shared wrapper, the host
serialization applies consistently without weakening or deleting any workflow-specific
security step.

Deterministic regression coverage verifies that the complete transient retry sequence is
executed under one host transport slot and that a lock failure returns RED before npm is
invoked.

## Permanent learning

- Retry logic must account for concurrency at the physical-host boundary when multiple
  self-hosted runner services share the same egress path.
- Identical retry schedules from sibling runner services can amplify a transient remote
  failure; bounded host serialization is preferable to increasing remote request volume.
- Security transport resilience must not blur the distinction between transport failure
  and a vulnerability finding.
- A transport-coordination failure is itself fail-closed evidence, never permission to
  skip the mandatory dependency audit.

## Security and authority invariants preserved

- Protected V9 `app:app` remains unchanged.
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged.
- broker write remains OFF.
- `trading_methods=false` remains unchanged.
- `REAL_TRADING_ENABLED=false` remains unchanged.
- No provider secret, token, provider identifier, connection URI or tenant-private
  payload is introduced or logged.
- No Cloudflare or Neon mutation is authorized by this CI transport correction.
