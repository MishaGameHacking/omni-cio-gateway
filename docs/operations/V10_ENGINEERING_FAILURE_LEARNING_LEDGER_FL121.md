# V10 Engineering Failure Learning Ledger — FL121

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_FUNCTION_PROVENANCE_CHECKOUT_EOL_DRIFT`
- Scope: exact-source provenance for the production database bootstrap Function

## Observed failure

After PR #483 was accepted, exact-main post-merge verification succeeded and the production release reached the staging candidate. The canonical Neon Function had already been converged to the accepted two-file provenance bundle, but the release still classified the Function source as stale and attempted the provider deployment write, which correctly failed closed with the existing insufficient-write-authority classification.

No secret value, provider identifier, Function URL, OIDC token or database credential is recorded here.

## Root cause

The source digest is intentionally byte-exact, but its two `.mjs` inputs were not pinned to a repository EOL policy. The authoritative release runs from a Windows checkout. A checkout-level LF-to-CRLF transformation therefore changes the digest even though the Git blob and deployed Function source are semantically identical. The false drift then selects the write-required recovery path.

This is a provenance portability defect, not a reason to weaken digest equality, broaden provider write authority, ignore the 403, or normalize arbitrary provider responses.

## Permanent correction

`.gitattributes` now pins `infrastructure/cloudflare/cf_d_neon_bootstrap/*.mjs` to `text eol=lf`. The deployed Function, Linux checkouts and authoritative Windows release checkout therefore derive the same source bytes and the same deterministic provenance digest.

A deterministic regression test requires both the repository attribute contract and LF-only checkout bytes for the canonical handler and provenance wrapper. Any future removal of the EOL pin or CRLF checkout drift fails before production release acceptance.

## Reuse rule

Any source identity derived from raw repository bytes must define platform-invariant checkout semantics for every hashed text input. Prefer an explicit repository EOL contract over weakening byte identity or adding platform-specific digest normalization after the fact.
