# V10 Engineering Failure Learning Ledger — FL129

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `RED_REPAIR_ONLY`
- Failure class: `CF_D_INVOKE_CREDENTIAL_CHECKPOINT_MISSED_STATIC_REVIEW_FINDINGS`
- Scope: the focused Neon Function invocation-credential repair in PR #496

## Observed failure

Published PR #496 head `5b842e3c40295633607514c9738e52d43f058369` reached exact-head verification with the functional repair already present. The provider/runtime logic was not yet merge evidence because two independent static-quality gates found repository-content defects:

- `Self-Hosted Windows CI` reached `python -m ruff check .` successfully, then `python -m ruff format --check .` rejected one unformatted authenticated provenance condition in `scripts/deploy_v10_cloudflare_neon_bootstrap_function.py`;
- `V10 Engineering Governance` consumed exact-head Sonar findings and failed because new-code issues were not zero. Sonar identified the failure-path unit test as an exception assertion containing multiple potentially throwing invocations and identified the invocation-credential context manager's rethrow-only `except` path as unnecessary exception handling.

The remaining independent PR audits on that head were successful, and Sonar reported zero new Security Hotspots. Those successes did not make the head GREEN because the two applicable failures remained blocking.

No provider secret, Function URL, account identifier, database credential, OIDC token or private payload is recorded here.

## Root cause

The invoke-credential repair was published before the full changed Python surface had been rechecked against both canonical formatter output and the repository's Sonar exception-handling/test conventions.

The cleanup implementation was semantically fail-closed, but it expressed the success/failure cleanup path with a nested `except` plus bare rethrow even though Python `try/finally` already provides the required guarantee. The regression test directly nested the context manager inside `assertRaisesRegex`, leaving several calls inside the exception assertion rather than isolating the single operation under test. Separately, an adjacent provenance condition remained syntactically valid and Ruff-lint clean but not Ruff-format clean.

This was therefore a preflight completeness defect, not evidence that the security boundary should be weakened or that CI/Sonar should be suppressed.

## Blast radius and adjacent review

The repair review covered:

- `scripts/neon_function_invocation_credential.py` and all create/revoke/cleanup paths;
- `tests/test_v10_neon_function_invocation_credential.py` and its exception assertions;
- `scripts/deploy_v10_cloudflare_neon_bootstrap_function.py` around authenticated provenance and source convergence;
- the directly coupled production database bootstrap, production-release workflow and CF-D acceptance contract already changed by PR #496;
- analogous cleanup/error-preservation patterns in the existing gated Cloudflare candidate/production runners.

No analogous repository-wide requirement was found to suppress formatter or Sonar rules. Existing accepted code instead favors explicit bounded cleanup state or ordinary `finally` cleanup, so the repair follows that convention.

## Permanent correction

- Express ephemeral invocation-credential revocation with `try/finally`, preserving mandatory revoke on normal completion and on any exception without a rethrow-only `except` clause.
- Keep cleanup fail-closed: a revoke failure remains an exception and therefore blocks acceptance; a regression test verifies this behavior.
- Isolate the deliberate failing operation behind one helper so each exception assertion contains one invocation that may raise.
- Apply the canonical Ruff formatting to the authenticated provenance condition without changing its behavior.
- Do not suppress Sonar findings, exclude the files from formatting, reduce test coverage or reinterpret a failed applicable gate as GREEN.

## Permanent regression / guard

The focused regression surface now requires:

- ephemeral credential revocation after successful use;
- ephemeral credential revocation after primary-body failure;
- revoke failure to remain fail-closed while the original body failure remains attached as exception context;
- broader/mismatched credential scopes to fail closed;
- project-authority and generated invocation-token masking to remain tested;
- canonical Ruff format and Sonar new-code issue count to pass on the replacement exact head.

## Prevention law

Before publishing a security/provider checkpoint, run the canonical formatter check on every changed Python surface in addition to lint/compile checks, and review newly introduced cleanup/context-manager and exception-test patterns against the repository's accepted static-analysis conventions. A semantically correct exception path is not preflight-ready while deterministic formatter or maintainability findings remain discoverable locally.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; PostgreSQL 18 + RLS/FORCE RLS; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
