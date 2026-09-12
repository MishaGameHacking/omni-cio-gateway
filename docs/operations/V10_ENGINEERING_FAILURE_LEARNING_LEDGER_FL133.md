# V10 Engineering Failure Learning Ledger — FL133

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `RED_REPAIR_ONLY`
- Failure class: `CF_D_INVOCATION_CREDENTIAL_TEST_AMBIENT_GITHUB_ENV_LEAK`
- Scope: exact-head Self-Hosted Windows CI for PR #496

## Discovery evidence

Exact PR head `67a56e10227027682246c83edb3edb8ce7a6ebb0` passed repository/security guards, Ruff, formatting, mypy, stable `app:app` verification and the read-only release contract. The authoritative Regression Shield then failed one deterministic test while 3102 tests passed and coverage remained above the protected threshold.

The failing invocation-credential fixture expected the manual managed name `omni-cio-cf-d-release-manual`, but the test process inherited GitHub Actions default `GITHUB_RUN_ID` and `GITHUB_RUN_ATTEMPT`. Production code therefore correctly derived a run-scoped managed name and rejected the mismatched synthetic response. GitHub documents both variables as default environment variables supplied to workflow steps.

No production provider state, real credential, account identifier or private payload contributed to this failure.

## Root cause

Tests for the run-derived credential namespace called the production naming function without isolating the two ambient GitHub runner variables. Local execution commonly lacks those variables and therefore selected the manual fallback, while GitHub Actions supplies them automatically. One test failed directly, and adjacent malformed-response tests could pass for the wrong reason because the ambient run-derived name introduced an unintended extra mismatch.

The production exact-name guard is correct and must not be weakened.

## Blast radius and adjacent review

The defect is confined to deterministic tests in `tests/test_v10_neon_function_invocation_credential.py`. Every direct credential-issuance test was reviewed because all of them transitively execute `_credential_name()`.

- Tests that intentionally exercise a real run-derived namespace now pass explicit synthetic run identity.
- All other issue-credential tests explicitly blank `GITHUB_RUN_ID` and `GITHUB_RUN_ATTEMPT` inside one shared helper, preserving the manual fallback deterministically.
- Cleanup, revoke, TLS, provider API, GitHub OIDC, Cloudflare release and protected V9 paths are unchanged.

## Permanent correction

Centralize test invocation through `_issue_credential(run_id="", run_attempt="")`. The helper overlays only `GITHUB_RUN_ID` and `GITHUB_RUN_ATTEMPT` with deterministic values and leaves unrelated environment state intact. The exact run-derived-name test supplies `123` / `1`; every other caller receives empty values and therefore exercises the manual namespace independent of the host runner.

Do not modify production `_credential_name()` behavior and do not weaken returned-name validation.

## Regression guard

The existing stale-managed-credential test now proves the successful cleanup-and-create path under deterministic manual naming even when executed inside GitHub Actions. The scope/branch/name rejection cases also run without accidental ambient-name mismatch, so each assertion continues to test its intended failure mode.

## Prevention law

Any deterministic test that exercises code derived from CI/runtime identity must explicitly own the relevant ambient variables. Default GitHub Actions variables are external test inputs just like provider responses: tests may either set exact synthetic values or blank them in a bounded helper, but they must not depend on whether the host process happens to define them.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; PostgreSQL 18 + RLS/FORCE RLS; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
