# V10 Engineering Failure Learning Ledger — FL142

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D` shared CI repair
- Execution unit: `FOCUSED_CHANGE`
- State at discovery: `RED_REPAIR_ONLY`
- Failure class: `WINDOWS_PIP_COMPILE_TRANSPORT_HANG_UNBOUNDED_LOCK_GATE`
- Scope: protected Windows dependency-lock verification used by both PR and post-merge quality gates

## Observed failure

PR #511 exact head `e8333dd6a0023aac4c08d9e09265b0412423f830` reached `Self-Hosted Windows CI` run `34987862022`, authoritative job `104444511567`.

The job successfully completed exact-head repository bootstrap, protected Python 3.12.10 bootstrap, strict Windows dependency projection, hash-locked dependency installation and the PostgreSQL 18 runtime-role rehearsal using synthetic database state.

The next step, `Verify lock files are current`, invoked raw online `python -m piptools compile`. While resolving the package index for `annotated-doc`, pip emitted a retry warning containing a low-level `OSError` with `access violation writing`. The compile process then stopped making progress. Because the child process had no per-attempt deadline, the workflow remained stuck until the authoritative job's 55-minute timeout cancelled the job. Later quality/security steps therefore did not execute.

This failure was not caused by a Cloudflare secret, Neon credential value, Neon organization/project identifier, broker secret or private tenant payload.

## Root cause

The protected Windows workflows treated online lock re-resolution as an unbounded subprocess. The job-level timeout was the only upper bound.

That design is inadequate for a network/package-index fault domain: a low-level transport/runtime failure can leave `piptools compile` alive long enough to consume the entire job budget. The workflow then ends as `cancelled` instead of producing a deterministic, bounded, fail-closed lock-verification result.

The defect is not that lock consistency is checked. Lock re-resolution plus exact Windows projection verification is still required. The defect is the absence of a bounded process deadline and a narrow retry policy around the online resolver.

## Blast radius and analogous-pattern review

Repository-wide search found the same raw online lock re-resolution pattern in both protected verification paths:

- `.github/workflows/self-hosted-windows-smoke.yml` — authoritative exact-head PR gate;
- `.github/workflows/regression-shield.yml` — exact-main/post-merge Regression Shield.

The existing `scripts/check_ci_security_baseline.py` also required the literal raw `python -m piptools compile` marker. Without correcting that guard, replacing the unsafe workflow pattern would either fail the baseline or encourage reintroduction of the unbounded command.

Directly coupled surfaces reviewed:

- `scripts/windows_ci_lock.py` — exact requirement/hash projection verifier;
- `requirements.in` / `requirements-dev.in` and reviewed generated locks;
- protected Windows workflow dependency installation and cleanup steps;
- CI/security baseline contract and its regression tests.

No dependency version, reviewed lock, hash policy, TLS policy, package index, coverage threshold or security gate needs to be weakened or changed for this repair.

## Permanent correction

- Add one stdlib-only `scripts/verify_windows_ci_locks.py` wrapper shared by both protected Windows workflows.
- Preserve the exact existing `piptools compile` inputs/options and the existing `scripts/windows_ci_lock.py verify` semantic comparison.
- Give every compile attempt a hard subprocess deadline so a stalled resolver cannot consume the entire workflow timeout.
- Permit at most three compile attempts.
- Retry only an evidence-based package-index/network/transport failure or a compile-process timeout; dependency/resolver/content errors fail immediately.
- Delete any partial compiled lock output before every attempt so a retry never verifies stale/partial state.
- Keep verification fail-closed: projection mismatch, verifier timeout or verifier launcher failure is never retried as a transient registry event.
- Preserve stdout/stderr diagnostics without logging environment variables or credentials.
- Update the CI/security baseline to require the bounded helper in both protected workflows and reject a return to raw unbounded `python -m piptools compile` execution.

## Why preflight did not catch it

Existing deterministic checks validated lock pinning/hashes, Windows projection semantics, workflow command presence and normal successful execution. They did not model a child resolver that remains alive after a package-index transport/runtime fault, and the workflow guard checked for the raw resolver command rather than checking the fault-containment boundary around it.

The failure class therefore required an injected timeout/transient-transport regression rather than another normal dependency-resolution happy path.

## Permanent regression / guard

Deterministic tests require:

- compile timeout -> bounded retry -> normal compile/verify continuation;
- the exact observed `access violation writing` transport signature -> bounded retry;
- repeated timeouts -> deterministic fail-closed exhaustion;
- non-transient resolver/content error -> no retry;
- Windows projection verification failure -> no retry;
- partial generated lock removal before every compile attempt;
- attempt count cannot exceed the reviewed maximum;
- both protected workflows invoke the bounded helper exactly once;
- protected workflows reject raw unbounded `python -m piptools compile` execution.

After source changes, the replacement exact SHA must receive full applicable certification. A single targeted test proves only the repaired failure surface and does not replace the full gate.

## Dependency/tooling knowledge

No dependency upgrade is required. The repair uses Python standard-library subprocess deadlines and bounded retry control around the already accepted `pip-tools` toolchain. Current official Python subprocess documentation confirms that timeout-enabled subprocess APIs raise `TimeoutExpired` and provide a supported process-boundary mechanism; this is workflow fault containment, not a dependency-policy change.

## Prevention law

Any protected CI step that performs online dependency/package-index resolution must have a bounded child-process deadline independent of the whole-job timeout. Retries must be narrow, finite and classified from evidence; deterministic resolver/content/security failures must not be retried until lucky GREEN. A whole-job timeout is a final containment layer, not the normal timeout mechanism for one external fault domain.

## Protected invariants

Unchanged: protected V9 `app:app`; reviewed hash-locked dependencies; exact Windows lock projection semantics; PostgreSQL 18/RLS/FORCE-RLS boundaries; `PUBLIC_MULTI_USER_ENABLED=false`; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short authority remains OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
