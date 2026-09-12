# V10 Engineering Failure Learning Ledger — FL134

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `RED_REPAIR_ONLY`
- Failure class: `CF_D_SYNTHETIC_FIXTURE_SECRET_SCANNER_COLLISION`
- Scope: exact-head Self-Hosted Windows CI for PR #496

## Discovery evidence

Exact PR head `feba24058856936eb73053716e81f96f73a19f12` passed compile, Ruff lint, Ruff format, mypy, protected `app:app`, the full Regression Shield (`3103 passed`, branch coverage above the protected threshold), dependency audit and SAST. The tracked-content secret scan then failed on one line in `tests/test_v10_neon_function_invocation_credential.py` because a synthetic object-storage access fixture was stored under a constant whose identifier contained the scanner's secret-keyword trigger.

The reported value was generated test data only. No real Neon, Cloudflare, broker, GitHub or database credential was committed or exposed. The correct response is to remove the scanner collision from the fixture, not to suppress or weaken secret detection.

## Root cause

The FL132 regression added coverage for masking the second sensitive field returned by Neon's credential-creation response. The synthetic fixture used a secret-looking constant identifier even though the test value itself was not production authority. `detect-secrets` correctly treated that identifier pattern as suspicious and the repository fail-closed wrapper blocked the head.

This is a test-fixture naming defect. Production masking, exact response validation and provider credential custody are correct and unchanged.

## Blast radius and adjacent review

The directly coupled test file was reviewed for all newly added synthetic credential fixtures. The provider response key remains the exact external schema field so the test continues to verify masking of the real contract shape. Only the local Python fixture symbol/value is changed to an explicitly synthetic, non-secret-looking access fixture.

No scanner baseline, allowlist, exclusion, inline pragma or CI command is modified.

## Permanent correction

- Rename the local synthetic object-storage fixture to an access-fixture identifier that does not imitate a credential variable.
- Replace the token-shaped synthetic value with a plain bounded ASCII test string that still satisfies the production response validator.
- Preserve assertions that both returned sensitive response values are passed to the masking boundary.
- Preserve the exact external response field name and all fail-closed validation/revocation behavior.

## Regression guard

The unchanged authoritative secret-scan command remains the regression guard. The replacement exact head must pass the same full tracked-content scan after the full test suite, dependency audit and SAST.

## Prevention law

Security regression tests must model sensitive provider fields without embedding secret-like local identifiers or credential-shaped fixture values unless the repository scanner has an already accepted deterministic test pattern. Prefer obviously synthetic access fixtures while keeping the external schema key exact. Never solve a scanner collision by suppressing the scanner, weakening its rules or adding a broad exclusion.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; PostgreSQL 18 + RLS/FORCE RLS; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
