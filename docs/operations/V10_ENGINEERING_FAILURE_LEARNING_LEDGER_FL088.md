# V10 Engineering Failure Learning Ledger — FL088

## Scope

Focused CI test-isolation correction for issue #444 while CF-D security PR #443 is paused in DRAFT.

Accepted base at diagnosis: `96e26827a29afff7b7ea443e629e5c76652787c9`.

## Failure observed

PR #443 exact head `dbe0575d0726e55557b7ad25c6592992bb7ce70e` reached a READY verification cycle in which the authoritative Windows lane and the other repository workflows completed successfully, but `V10 Fast PR Checks` run `33838010675` failed at `Run CI and release guard unit tests`.

The failing test was:

`tests.test_v10_regression_shield.V10RegressionShieldGuardTests.test_npm_audit_retries_transient_then_requires_success`

The synthetic test expected status `0` but received host-slot status `75` after:

`npm audit host transport slot timed out; security gate remains failed closed.`

No real npm vulnerability result caused this unit-test failure.

## Root cause

Three pure retry/classification tests in `tests/test_v10_regression_shield.py` replaced the npm subprocess runner with deterministic synthetic results but left `run_audit()` on its default production `lock_factory`.

The default lock is the physical-host loopback serialization contract accepted in FL085. During a parallel READY batch, another legitimate Web dependency audit can hold that host-global slot for the complete real retry/backoff sequence. A synthetic unit test then waits on an unrelated physical resource and becomes timing/concurrency dependent.

The production lock behavior is correct. The defect is failure to isolate pure unit tests from that production coordination primitive.

## Blast radius

The same pattern existed in three tests:

1. `test_npm_audit_retries_transient_then_requires_success`;
2. `test_npm_audit_security_finding_is_not_retried`;
3. `test_npm_audit_transient_exhaustion_stays_red`.

Dedicated lock/serialization coverage remains in `tests/test_v10_npm_audit_serialization.py`; those tests intentionally exercise the host-slot contract and are not converted into lock-free production tests.

No change is required in `scripts/run_v10_npm_audit.py`, the npm audit threshold, production retry budget, host slot, workflow consumers, dependency locks, or toolchain versions.

## Why preflight missed it

Earlier exact-head/DRAFT runs passed because the physical slot happened to be available when these synthetic tests executed. The test suite therefore had a hidden dependency on concurrent runner timing that ordinary single-process deterministic review did not expose.

The READY cycle supplied the missing contention evidence.

## Corrective change

Pure retry/classification tests now inject `contextlib.nullcontext` as `lock_factory` when they already inject a synthetic npm runner. Their retry, backoff and security-classification assertions remain unchanged.

Production and dedicated serialization tests continue to use the real/injected lock behavior appropriate to their scope.

## Permanent regression / prevention rule

- A test that replaces a network/process runner with synthetic results must also replace unrelated physical-host coordination primitives unless the coordination primitive itself is the behavior under test.
- Host-global mutex/slot behavior belongs in dedicated serialization tests, not pure retry/classification unit tests.
- Do not weaken or shorten production fail-closed coordination merely to make a synthetic test deterministic.
- A concurrency-dependent unit test is a test-isolation defect even when the production coordination mechanism is functioning exactly as designed.

## Dependency/tooling knowledge change

None. npm, Node, Python and repository lock versions are unchanged. Current npm documentation still describes `npm audit` as a registry-backed security request; this correction does not change the production audit contract.

## Protected invariants

- V9 `app:app` unchanged.
- `PUBLIC_MULTI_USER_ENABLED=false` unchanged.
- broker write remains OFF.
- `trading_methods=false` unchanged.
- `REAL_TRADING_ENABLED=false` unchanged.
- production npm audit remains mandatory, serialized and fail closed.
- no Cloudflare/Neon mutation or provider secret handling is introduced.
