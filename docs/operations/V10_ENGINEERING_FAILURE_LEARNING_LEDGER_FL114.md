# V10 Engineering Failure Learning Ledger — FL114

## Failure class

`DETECT_SECRETS_TEST_MARKER_KEYWORD_COLLISION`

## Evidence

Exact PR head `c8bb15e0a1cdf5179c4e5b27ef7b6cd59b3ac506` completed the protected Windows compile, repository policy, PostgreSQL 18 rehearsal, Ruff, formatting, mypy, full regression suite, coverage, dependency audit and SAST stages successfully. The authoritative merge gate then stopped at the tracked-content secret scan with one deterministic finding in `tests/test_v10_cloudflare_staging_secret_reuse_preflight.py`.

The flagged value was not a credential. It was a source-code marker containing the command used to probe the staging runtime binding. The marker variable name itself used credential-shaped terminology, which caused the scanner's Secret Keyword detector to treat an ordinary test marker assignment as a potential secret.

## Root cause

A non-secret string constant used only to locate workflow source text was named as though it might store sensitive material. That naming choice crossed the repository's intentional fail-closed secret-scanning heuristic even though the value was a deterministic command marker.

## Blast radius and analogous-pattern review

The directly related staging authority tests and workflow-marker constants were reviewed. The defect class is limited to non-secret test/source markers whose identifier names imply secret-bearing storage while their values are ordinary deterministic source text. No real credential value, provider identifier, database DSN, token or private payload was present in the finding.

The scanner itself is correct to fail closed. Suppressing the finding, adding a scan allowlist, weakening `detect-secrets`, or reducing tracked-content coverage would hide the naming ambiguity instead of fixing it.

## Correction

Rename the source marker to describe what it actually represents: a runtime-binding probe command. Update only the local test references; workflow behavior, provider authority, secret custody and production semantics are unchanged.

The mandatory tracked-content scan remains unmodified and is the permanent regression guard for this defect class.

## Prevention law

Non-secret test constants that store command/source markers must use semantic names describing the marker or operation, not credential-shaped names such as `secret`, `token`, `password`, `key` or equivalent terms unless the value is intentionally handled as sensitive material. A scanner hit caused only by ambiguous naming is fixed at the naming/source boundary, never by suppressing or weakening the scanner.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; broker write OFF; transfer, withdrawal, margin, leverage and uncovered-short authority remain forbidden; no Web Visual, Telegram/VK, AI/Cortex, D1 or speculative Hyperdrive scope is introduced.
