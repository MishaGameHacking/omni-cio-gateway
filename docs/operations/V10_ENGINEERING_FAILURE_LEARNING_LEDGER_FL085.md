# V10 Engineering Failure Learning Ledger — FL085

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, exact-main
post-merge Web security evidence required by CF-D production release.

## Failure observed

After PR #436 was squash-merged, exact merged candidate main
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

PR #440 exact-head evidence then proved that serialization is required but the original
retry horizon was also too short:

- WP22 run `33695387038` acquired the host slot and exhausted three serialized
  `ECONNRESET` attempts;
- WP19 run `33695387063` explicitly waited for that slot, then exhausted its own three
  serialized attempts;
- WP22A run `33695387116` also emitted the host-slot wait marker and then exhausted
  three attempts;
- Fast PR run `33695386947` exhausted the same serialized retry path;
- WP16 run `33695387151` subsequently completed `npm audit` successfully on the same
  machine only seconds after another workflow had exhausted its third attempt.

No failing job returned an npm vulnerability report. Web type-check, lint, unit tests,
build and the surrounding repository/security contracts completed successfully before
the transport-only failure paths.

Current npm documentation confirms that `npm audit` submits dependency data using a POST
to the Bulk Advisory endpoint. The audit POST therefore needs an explicit repository
transport-recovery budget rather than assuming generic registry-read retries are a
complete recovery contract.

Independent review then exposed defects in the first filesystem-lock implementation:

- a process/service temporary directory is not necessarily a physical-host namespace;
- an undersized waiter bound can turn correct serialization into avoidable starvation;
- Windows lock contention must be distinguished from real descriptor/argument errors.

Those findings were corrected, but the filesystem coordination design still failed the
external security quality gate. SonarCloud check `100468737447` on exact head
`db575a241c99079bef4a0b40ea737c5ffa624b4a` and check `100546704553` after the
formatter-only head `573ec20c04a21fc1431ced5d4dbc9b33ed0a7c49` both reported
`D Security Rating on New Code` with two annotations. Because the second commit changed
only Ruff layout, the security result is attributable to the filesystem-lock design, not
the formatter correction. The available GitHub integration does not expose the private
Sonar annotation rule IDs, so this ledger does not invent them or suppress the findings.
Instead, the shared-file coordination surface is removed completely.

The DRAFT authoritative Windows gate also caught one deterministic Ruff formatting
mismatch on `db575a241c99079bef4a0b40ea737c5ffa624b4a`. Exact head
`573ec20c04a21fc1431ced5d4dbc9b33ed0a7c49` applied only the formatter-required layout.
This exposed a preflight gap: focused corrections must reproduce the authoritative Ruff
format scope before publication.

The later loopback-slot head
`444259eb4ae17f5351ed7b42ae29dc9337a21f14` then completed the full DRAFT repository
batch successfully, including a real Windows contention marker from WP21 followed by
`found 0 vulnerabilities`, authoritative Ruff/static/coverage/security checks, WP22A
npm audit and pinned OpenTofu validation, Sonar Quality Gate success and Semgrep success.
That evidence is diagnostic only after the next correction commit.

A fresh current-head manual Gitar review then found one additional recovery edge: a
single fixed loopback port could be occupied indefinitely by an unrelated local process,
leaving every audit correctly fail-closed but requiring a source edit to recover. The
correction therefore keeps a safe default port while adding a strictly validated,
operator-controlled host-wide override. Automatic free-port scanning is intentionally
forbidden because different sibling runners could otherwise select different ports and
silently defeat serialization.

A final manual pre-merge review then exposed an error-precedence edge in the context
manager exit path. If `npm audit` had already returned a real non-transient/security
failure and the host-slot release subsequently failed, the release exception could replace
the already-authoritative npm exit status with transport-lock status `75`. Both outcomes
were RED, but the second classification blurred the exact distinction this wrapper is
required to preserve. The correction now stages the npm result before leaving the slot:
a prior nonzero npm result remains the primary exit status while the release failure is
also logged; a clean npm result followed by release failure still fails closed as `75`.

## Root cause class

`SELF_HOSTED_NPM_AUDIT_RETRY_WINDOW_CONCURRENCY_AND_COORDINATION_GAP`

Seven repository-controlled weaknesses are addressed:

1. sibling runner services could previously amplify the same transient failure with
   overlapping audit/retry streams;
2. after serialization removed that overlap, the accepted three-attempt / 5-second-base
   retry horizon still ended while the same endpoint later became reachable within the
   surrounding exact-head batch;
3. the first serialization namespace was not guaranteed to be physical-host global;
4. the first Windows lock path did not initially distinguish ordinary contention from
   real lock-integrity errors;
5. predictable shared-filesystem coordination introduced an avoidable security-analysis
   surface and failed the required Sonar new-code security gate;
6. a fixed-only loopback port provided no bounded operator recovery if an unrelated local
   process permanently occupied the reserved default;
7. a secondary slot-release failure could previously override a primary nonzero npm audit
   result and misclassify an already-observed security/non-transient failure as transport.

The upstream/provider/network trigger for each `ECONNRESET` remains external and is not
claimed to be uniquely identified. npm public status can remain operational while an
individual self-hosted path experiences a transient reset, so status alone is not
accepted as proof that the audit POST succeeded.

## Blast radius

The shared `scripts/run_v10_npm_audit.py` wrapper is consumed by the accepted Web audit
workflows for WP15 through WP22A and fast PR checks. A short transient advisory-endpoint
window can therefore block multiple otherwise-valid exact-head or exact-main gates.

Any coordination primitive used by this wrapper is also shared by sibling runner
services on one physical host. A weak namespace, an over-broad contention classifier, an
insecure shared-file primitive, inconsistent per-service coordination configuration, or
incorrect primary/cleanup error precedence therefore affects every consumer at once.

The package lock, npm version, audit level, security-result classification and
fail-closed behavior are not defective and are not relaxed by this correction.

## Corrective invariant

The mandatory npm security audit must now:

- acquire one physical-host-local transport slot before the first `npm audit` call;
- implement that slot with an IPv4 TCP socket bound only to loopback `127.0.0.1`, without
  listening or accepting connections;
- use default port `43867`, which is outside the repository Web preview range
  `18000-31999` and below the default Windows dynamic client range beginning at `49152`;
- allow only an explicit `OMNI_CIO_NPM_AUDIT_SLOT_PORT` recovery override in the bounded
  range `32000-49151`;
- require the override to contain ASCII decimal digits only; malformed, Unicode-digit,
  below-range or above-range values fail closed before socket acquisition;
- require any override to be configured identically for every sibling runner service on
  the same physical host; the variable is recovery configuration, not a per-job routing
  input;
- never auto-scan or auto-fallback to another port after `EADDRINUSE`, because different
  contenders could otherwise acquire different slots and overlap remote audit traffic;
- on Windows require `SO_EXCLUSIVEADDRUSE` before bind so address reuse cannot silently
  defeat mutual exclusion;
- classify only `EADDRINUSE` as ordinary slot contention;
- fail closed immediately on configuration, socket creation, socket-option, bind, or
  release errors that are not ordinary contention;
- hold the bound loopback socket across the complete retry/backoff sequence so sibling
  runner services cannot synchronize remote retries;
- wait at most 600 seconds for the host slot, then fail closed;
- use five attempts by default, which is the already-reviewed hard maximum;
- use a 15-second default linear backoff with each delay capped at 60 seconds, producing
  `15 / 30 / 45 / 60` seconds before attempts 2 through 5;
- release the bound socket when the wrapper exits, including exceptional exit;
- preserve the exact npm command and `high` audit threshold;
- retry only recognized transport/temporary registry failures;
- never retry or suppress a real npm audit vulnerability report;
- preserve a prior nonzero npm audit/launcher result if slot release also fails, while
  logging the secondary release failure instead of reclassifying the primary result;
- treat a clean npm audit followed by slot-release failure as RED `75` because the
  coordination integrity itself was not cleanly closed;
- never fall back to a mirror, cached acceptance, disabled audit, `continue-on-error` or
  fabricated success.

The loopback slot is coordination only. It does not open a listening service, select a
remote target, proxy npm traffic, or create any new application/network authority.

## Directly coupled consumers

All accepted Web dependency-audit workflows already call the shared wrapper, so host
serialization and the enlarged bounded retry horizon apply consistently without deleting
or softening any workflow-specific security step.

Deterministic regression coverage verifies that:

- the default host-slot port stays inside the reserved `32000-49151` corridor, outside
  the source-controlled Web preview range and below the default Windows dynamic range;
- the recovery override defaults correctly, accepts a validated in-range ASCII-decimal
  port, rejects malformed/out-of-range/Unicode-digit values, and is propagated to bind;
- only `EADDRINUSE` is classified as normal contention;
- a real loopback bind prevents a concurrent second slot without filesystem state;
- the complete retry sequence stays under one host transport slot;
- the default budget reaches a fifth attempt and uses exactly `15 / 30 / 45 / 60`
  seconds of bounded backoff;
- a custom large backoff remains capped at 60 seconds;
- host-slot acquisition failure returns RED before npm is invoked;
- slot-release failure cannot replace a prior real npm security/non-transient failure
  status;
- slot-release failure after a clean npm result remains RED `75`.

Focused scratch preflight for the override correction completed nine deterministic tests
and Python compilation successfully. The scratch environment had no Ruff binary and its
PyPI DNS lookup failed, so it could not honestly reproduce `ruff==0.16.1` locally. The
fresh exact-head trusted Windows Ruff check/format remains mandatory evidence and must not
be inferred from earlier heads.

The cleanup-precedence correction adds two deterministic regression cases but does not
claim a new local Ruff result. Fresh exact-head trusted Windows Ruff/test/security evidence
remains mandatory after publication of the correction head.

## Permanent learning

- Retry logic must account for concurrency at the physical-host boundary when multiple
  self-hosted runner services share one egress path.
- Removing concurrency amplification does not prove the external transport is healthy;
  exact-head evidence must still test whether the bounded retry horizon covers observed
  transient windows.
- Shared coordination should avoid predictable files in broadly shared temporary
  locations when a narrower host-local OS/network namespace can provide mutual exclusion
  without creating filesystem race/path surface.
- A host-local coordination default needs an explicit, strictly validated recovery path
  for unrelated local resource collisions, but that recovery path must preserve a single
  shared slot across all sibling runners.
- Automatic free-resource fallback is unsafe for a mutex primitive when independent
  contenders can choose different resources.
- Contention and coordination-integrity errors are distinct failure classes and must not
  be collapsed into the same timeout path.
- Security transport resilience must not blur the distinction between transport failure
  and a vulnerability finding.
- Cleanup/coordination failures must never erase an already-observed primary security
  finding; both conditions may be reported, but failure-class authority stays explicit.
- Increasing a bounded retry horizon is acceptable only when the hard attempt/delay caps
  and fail-closed terminal result remain explicit.
- A transport-coordination or retry-exhaustion failure is never permission to skip the
  mandatory dependency audit.
- Focused preflight must include the exact authoritative formatter scope whenever that
  tool is actually available; an unavailable tool is recorded, not fabricated.

## Security and authority invariants preserved

- Protected V9 `app:app` remains unchanged.
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged.
- broker write remains OFF.
- `trading_methods=false` remains unchanged.
- `REAL_TRADING_ENABLED=false` remains unchanged.
- No provider secret, token, provider identifier, connection URI or tenant-private
  payload is introduced or logged.
- No Cloudflare or Neon mutation is authorized by this CI transport correction.
