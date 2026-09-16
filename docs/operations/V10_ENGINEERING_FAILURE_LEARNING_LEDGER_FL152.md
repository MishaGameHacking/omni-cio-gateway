# V10 Engineering Failure Learning Ledger — FL152

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `RED_REPAIR_ONLY`
- Failure class: `CF_D_SECRET_SCANNER_DETECTOR_SENSITIVE_FIXTURE`
- Scope: exact-head PR #526 tracked-content secret scan

## Observed failure

Exact repair head `27a4612ebba033fca9f9d5017e9461b7f933a784` passed the focused behavior checks and the broad protected runtime checks in `Self-Hosted Windows CI` run `35087415167`: lock verification, repository/security guards, compile, Ruff, formatting, mypy, protected `app:app`, full regression (`3177 passed`, `361` subtests, branch coverage `62.20%`), dependency audit and Bandit.

The final tracked-content detector then failed on one source location in `tests/test_v10_neon_credential_contract_diagnostics.py` with `Base64 High Entropy String`. The flagged source is a realistic problem-JSON MIME fixture, not a credential. No secret value is recorded here.

## Root cause and blast radius

The new diagnostic regression suite encoded that protocol fixture as one static source literal. `detect-secrets` correctly scans versioned source text rather than runtime intent, so the MIME subtype collided with its Base64 entropy heuristic.

The defect is limited to fixture representation. The diagnostic implementation, production mutation gate, Neon authority contract and runtime behavior are unchanged. Existing fragment-constructed provider-prefix test data already demonstrates the repository pattern for scanner-safe protocol fixtures.

Preflight validated behavior, type/lint and secret output custody but did not execute the exact tracked-content detector against the newly added fixture before the checkpoint was published.

## Permanent correction

- Preserve the exact runtime MIME value exercised by the test.
- Construct the detector-sensitive MIME token from explicit non-secret source fragments.
- Do not add detector suppression, allowlisting or baseline exceptions.
- Do not weaken or disable `detect-secrets`.
- Keep the Neon diagnostic and production provisioner implementation unchanged.
- Re-run the exact tracked-content scan and full exact-head certification on the replacement SHA.

## Prevention law

Security and protocol tests that intentionally contain realistic token-like strings must run the same tracked-content secret detector during focused preflight. When a harmless fixture collides with a detector heuristic, represent it from semantically obvious source fragments instead of suppressing the detector.

## Protected invariants

Unchanged: protected V9 `app:app`; PostgreSQL 18 + RLS/FORCE RLS; `PUBLIC_MULTI_USER_ENABLED=false`; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; no provider secret/private payload disclosure; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
