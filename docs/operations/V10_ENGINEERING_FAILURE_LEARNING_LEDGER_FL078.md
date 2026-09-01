# V10 Engineering Failure Learning Ledger — FL078

## Scope

Focused Omni-CIO Sentinel brand-asset custody/integrity work in issue #426 / PR #427.

This entry records the tracked-secret false-positive defect exposed only after the preceding Windows byte-portability and XML-parser security corrections were proven. It does not authorize `WEB-VISUAL-INTEGRATED`, Cloudflare/domain mutation, public-user activation, broker write, or Real execution.

## Exact failure evidence

Exact head `00173bf00b74ee58e822baa902691bf8939d1b49` ran `Self-Hosted Windows CI` workflow run `33564906222`, authoritative job `100045744434`.

Before the final secret stage, the exact head proved:

- repository/CI policy contracts: success;
- compile: success;
- Ruff lint and formatter scope: success;
- mypy: success;
- protected V9 `app:app`: success;
- read-only GPT Actions release contract: success;
- Regression Shield: **2847 passed**, 57 subtests passed, 62.20% coverage: success;
- protected dependency audit: success, no known vulnerabilities;
- Bandit SAST: success, including the corrected Android XML parser.

`Scan tracked content for potential secrets` then failed closed on 43 `Hex High Entropy String` findings. Every reported value was reviewed against its producer/consumer contract and fell into one of these deterministic non-secret classes:

- per-file SHA-256 values in the repository-canonical brand asset manifest;
- custody pins bound to the tracked manifest or tracked brand files;
- the frozen decoded-pixel identity checksum;
- historical/recovery provenance checksums already recorded as non-credential integrity evidence;
- the initial materialization Git commit SHA;
- the three public integrity constants in `scripts/check_v10_brand_assets.py`.

No detector, entropy threshold, path family, or security stage was disabled.

## Root cause

The repository secret policy already distinguishes narrowly approved public checksums and Git SHA evidence from credentials, but the newly materialized brand package introduced a much larger checksum registry after that policy was designed. The brand manifest, custody contract and integrity guard correctly store high-entropy cryptographic digests; the secret post-filter had no semantic knowledge of those new producers, so it treated every digest as an unclassified candidate secret.

A blanket path exclusion would be unsafe because the same brand files can still accidentally receive a real token or credential in the future. The defect is therefore missing semantic checksum classification, not excessive scanner sensitivity.

## Blast radius searched

The directly coupled surfaces are:

- `scripts/check_ci_security_baseline.py`, which is the fail-closed consumer of `detect-secrets` JSON;
- `.github/workflows/self-hosted-windows-smoke.yml` and `.github/workflows/regression-shield.yml`, which use the same scanner/post-filter contract;
- `docs/brand/OMNI_CIO_BRAND_ASSETS_CUSTODY.json`;
- `docs/brand/omni-cio-brand-assets-v1/asset-manifest.json`;
- `scripts/check_v10_brand_assets.py`.

Existing WP6/WP7/WP22A exact-line secret exceptions remain unchanged. No broker, account, tenant, runtime-secret, database, Cloudflare, Telegram, VK, or Real-execution secret path is added to an allowlist.

## Corrective change

1. Preserve `detect-secrets` with all current plugins and thresholds.
2. Do not exclude `docs/brand`, the manifest, custody file, or the integrity guard from scanning.
3. Classify a manifest SHA-256 finding as non-secret only when the manifest record is structurally valid and the checksum exactly matches the bytes and byte count of its tracked asset.
4. Classify custody checksums only when they are cryptographically bound to the current tracked manifest/asset or match the explicitly frozen public provenance checksum contract.
5. Classify integrity-guard checksum literals only when the declaration name and actual tracked asset/custody binding agree.
6. Keep every unknown field, changed digest, wrong finding type, malformed path, missing asset, mismatched byte count and unrelated high-entropy string fail-closed.
7. Add focused positive/negative regression tests for manifest, custody and guard classification.
8. Re-run the complete exact-head DRAFT gate because the security post-filter source changed.

## Why prior preflight missed it

Earlier focused tests exercised the brand integrity verifier itself, including byte tampering, EOL portability and hostile XML. They did not execute the complete repository-wide `detect-secrets scan --all-files | check_ci_security_baseline.py --detect-secrets-report` pipeline against the newly expanded checksum registry. The authoritative lane therefore correctly exposed the missing consumer classification after SAST became GREEN.

## Permanent learning

- Cryptographic digests are high entropy by design; classify them by verifiable producer semantics rather than by directory exclusion or detector suppression.
- A checksum exception is safe only when the checksum is bound to the bytes it claims to identify, or to an explicitly frozen public provenance value.
- Secret-scanner false-positive handling must remain fail-closed for neighboring fields and future edits in the same file.
- New machine-readable integrity registries must include secret-scan compatibility in pre-CI readiness, not only integrity-verifier tests.
- Reaching a later security stage can expose a new defect class even when all preceding exact-head gates are legitimately GREEN; new source still invalidates final acceptance evidence.

## Security and authority invariants preserved

- Protected V9 `app:app` remains unchanged.
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged by this focused branch.
- Broker write remains OFF.
- `trading_methods=false` remains unchanged.
- `REAL_TRADING_ENABLED=false` remains unchanged.
- No real credential, token, password, account identifier, database secret or provider secret is added to GitHub, tests, logs, comments or artifacts.
- No Cloudflare/provider mutation is performed by this correction.
