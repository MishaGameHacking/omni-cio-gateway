# V10 Engineering Failure Learning Ledger — FL126

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `RED_REPAIR_ONLY`
- Failure class: `CF_D_DIRECT_BOOTSTRAP_REPAIR_TRANSCRIPTION_SYNTAX_DEFECT`
- Scope: replacement direct-bootstrap preflight source only

## Evidence

PR #489 exact head `665f8dc46016093ecbd146d74717ab2eb2896037` reached the authoritative Windows merge gate. Repository/bootstrap/toolchain/PG18/policy checks succeeded, then the compile step failed deterministically in `scripts/bootstrap_v10_cloudflare_production_database_direct.py` before static quality or regression execution.

The published replacement source contained two transcription defects in unchanged adjacent bootstrap code: `json.jumps(...)` instead of `json.dumps(...)`, and an unmatched call `connection = _direct_connection_target)` instead of `connection = _direct_connection(target)`. The latter produced the terminal `SyntaxError: unmatched ')'`.

The independently completed exact-head Sonar analysis reported Quality Gate PASS with zero new issues and zero hotspots, but compile failure remains authoritative RED and blocks merge.

## Root cause and blast radius

The defects were introduced while reconstructing the whole source file for the focused root-provenance repair instead of preserving byte-exact unchanged adjacent code. They are not part of the intended provenance behavior and do not indicate a PostgreSQL, Neon, Cloudflare, OIDC, RLS, broker or production-authority failure.

Blast radius is limited to the branch-local direct-bootstrap Python module. The accepted `main` and production deployment were not mutated by this failed PR head.

## Correction

Restore the adjacent request code byte-for-byte to the accepted implementation:

- use `json.dumps(...)` for both existing bootstrap request bodies;
- call `_direct_connection(target)` exactly;
- retain only the intended provenance-preflight behavioral change from FL125.

No CI, type, lint, security, Sonar, secret-scan or provider gate is weakened.

## Permanent regression / guard

The existing authoritative `python -m compileall` gate is the deterministic regression guard and must succeed before static quality/regression/security stages. The replacement exact head must then rerun the entire applicable PR verification cycle; no result from the defective head is final evidence.

## Prevention law

When a focused repair changes only one semantic region of an existing security/control-plane module, preserve all unrelated adjacent code byte-exact rather than manually reconstructing it. Before publication, diff the full file against accepted `main` and require every changed hunk to map to the proven root cause or its deterministic regression coverage.

## Protected invariants

Unchanged: protected V9 `app:app`; `PUBLIC_MULTI_USER_ENABLED=false`; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; broker write, transfer, withdrawal, margin, leverage and uncovered short remain OFF/FORBIDDEN; PostgreSQL 18 + RLS/FORCE RLS remains relational truth; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
