# V10 Engineering Failure Learning Ledger — FL073

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, CF-D exact-head
verification on PR #413 after the provider-type and Ruff correction batch.

This entry records a late deterministic security-scan failure and the adjacent preflight
lesson. It does not authorize production cutover, public multi-user activation, broker
write, or Real execution.

## Exact failure evidence

Exact head `18d1bc5e2f4284074b48148c5f8de3e4b824567d` completed the substantive
protected-runtime path successfully through dependency locks, PostgreSQL 18 rehearsal,
repository/governance guards, compilation, Ruff lint/format, mypy, gateway contract,
Regression Shield with coverage, dependency audit and Bandit SAST.

The only authoritative Windows failure was the final tracked-content secret scan:

- file: `scripts/manage_v10_cloudflare_production.py`;
- finding type: `Secret Keyword`;
- finding line: the module-level assignment that bound the public configuration name
  `OMNI_V10_POSTGRES_DSN` to an internal identifier named `_RUNTIME_SECRET`.

The source contained no database DSN value. The real runtime DSN remains read only from
a runner-temporary file, is masked before provider use, and is uploaded to Cloudflare
as `secret_text` without being printed.

## Root cause

`detect-secrets` KeywordDetector intentionally looks for secret-sounding variable names
that are assigned hard-coded values. The internal identifier `_RUNTIME_SECRET` therefore
made a non-secret configuration-name constant look like a hard-coded secret assignment
to the scanner.

This is a source-naming defect, not a reason to disable the detector, add a broad
exclude, or allowlist the line. Suppressing the scanner would reduce recall for real
hard-coded credentials and is forbidden for this correction.

## Blast radius searched

The exact authoritative report contained one tracked-content finding. The current
Cloudflare correction surface was also reviewed for analogous hard-coded quoted
assignments to identifiers containing `SECRET`. No second current report finding was
present.

Directly coupled surfaces reviewed:

- production Cloudflare secret lookup/upload in
  `scripts/manage_v10_cloudflare_production.py`;
- Cloudflare release-acceptance guard/tests;
- exact `OMNI_V10_POSTGRES_DSN` Wrangler/runtime binding contract;
- authoritative detect-secrets report validator;
- prior Ruff-only verification failure on the parent correction cycle.

The binding string itself must remain unchanged because it is part of the accepted
runtime contract. Only the internal Python identifier should change.

## Why preflight missed it

The branch-local CF-D focused preflight covered syntax, unit contracts, release guards
and Ruff commands, but the tracked-content `detect-secrets` scan was not reproduced
before the expensive authoritative cycle. The independent stdlib Engineering Governance
lane also did not contain a source-level regression for this KeywordDetector naming
class, so it passed while the later full security scan correctly failed closed.

The immediately preceding correction cycle exposed the adjacent process weakness for
Ruff: exact final changed-file formatting must be checked after the last edit, not on an
earlier intermediate source state.

## Corrective change

1. Rename the internal binding constant from `_RUNTIME_SECRET` to
   `_RUNTIME_DSN_BINDING` and the related missing-state constant to
   `_RUNTIME_DSN_BINDING_MISSING`.
2. Preserve the literal provider/runtime binding name `OMNI_V10_POSTGRES_DSN`, the
   Cloudflare `/secrets` API, `secret_text` type, runner-temporary DSN custody and all
   existing fail-closed error codes.
3. Do not add `pragma: allowlist secret`, do not disable KeywordDetector, and do not
   broaden secret-scan exclusions.
4. Add a stdlib regression to the Cloudflare release-acceptance test family that rejects
   quoted hard-coded assignments to `*SECRET*` identifiers in the production manager
   and requires the canonical `_RUNTIME_DSN_BINDING` declaration. That test already
   executes in the fast Engineering Governance workflow, shifting this defect class
   earlier than the authoritative full scan.
5. Re-run the full exact-head verification chain because any source correction
   invalidates all prior final evidence.

## Permanent learning

- A secret binding **name** is metadata, but naming its Python constant `*SECRET*` while
  assigning a quoted literal can intentionally resemble a hard-coded secret to
  KeywordDetector. Use semantic identifiers such as `*_BINDING` or `*_ENV` for public
  configuration names.
- Never fix a secret-scan false positive by weakening the scanner when a source-level
  semantic rename removes the ambiguity.
- Exact final-source Ruff formatting and tracked-content secret scanning belong in the
  preflight definition for release/cutover corrections. If those exact tools cannot be
  executed locally, do not claim final preflight parity; the authoritative gate remains
  the truth source.
- Independent governance tests should encode deterministic scanner-adjacent source
  invariants that can run without external packages, while the full detector remains
  mandatory as the security authority.

## Security and authority invariants preserved

- Protected V9 `app:app` remains unchanged.
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged.
- Telegram/VK activation remains outside this correction.
- Broker write remains OFF.
- `trading_methods=false` and `REAL_TRADING_ENABLED=false` remain unchanged.
- No provider/broker/database secret value or full private identifier is added to source,
  logs, PR discussion, or artifacts.
- No CF-D production mutation occurs in this correction.
