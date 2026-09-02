# V10 Engineering Failure Learning Ledger — FL084

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, CF-D exact-main
post-merge acceptance and production-release entry gate.

## Failure observed

After PR #435 was squash-merged, exact accepted main
`e131112491418e26ee5a64267d5f0d2c006519fb` ran its required post-merge push batch.
`Regression Shield` run `33689611114` completed successfully, but
`V10 WP22A Clientless Access Audit` run `33689611175` failed in
`Validate Cloudflare IaC with pinned OpenTofu and provider mirror`.

The preceding Web, Python, PowerShell and dependency checks were successful. The failing
operation was the OpenTofu release download in `scripts/bootstrap_wp22a_terraform.ps1`:
PowerShell reported an unexpected EOF / zero-byte transport stream from
`Invoke-WebRequest`.

Automatic production release run `33690155899` then failed closed at
`Require all exact-main post-merge push workflows`. Provider binding, Neon authority,
staging, production mutation, Custom Domain and live acceptance steps were skipped.

## Root cause class

`WP22A_OPENTOFU_SINGLE_SHOT_DOWNLOAD_TRANSPORT_FRAGILITY`

The OpenTofu bootstrap already pinned the exact version and SHA-256 and cleaned temporary
artifacts, but it attempted the public release download only once. A transient transport
EOF could therefore make a valid exact-main post-merge batch RED before repository or
provider authority checks. The adjacent Cloudflare provider bootstrap already used the
reviewed bounded-retry pattern, so the inconsistency was source-side rather than an
accepted need to weaken the gate.

## Blast radius

The defect is limited to consumers of `scripts/bootstrap_wp22a_terraform.ps1`, currently
the WP22A Cloudflare IaC validation path used by the clientless external-access audit.
The release gate correctly treats that audit as applicable post-merge evidence, so this
single-shot transport failure also blocks CF-D from reaching any provider mutation.

Adjacent download surfaces were reviewed. The directly coupled Cloudflare provider
bootstrap already has bounded transport retries plus an exact archive hash check. Older
or OWNER-run download paths are not changed by this focused correction because they are
not producers of the observed exact-main gate failure.

## Corrective invariant

The OpenTofu bootstrap must:

- keep the exact reviewed OpenTofu version and GitHub release asset unchanged;
- keep the exact SHA-256 verification unchanged and mandatory before extraction;
- retry only transport/download exceptions with a bounded three-attempt loop;
- remove any partial archive before every retry;
- use a finite per-attempt timeout and bounded backoff;
- fail with `WP22A_OPENTOFU_DOWNLOAD_FAILED_AFTER_RETRIES` after the final transport
  failure;
- never treat a checksum mismatch as a retryable transport event;
- never fall back to an unreviewed mirror, latest version, disabled hash check or
  `continue-on-error` path;
- preserve final cleanup of temporary archive/extraction state.

## Permanent learning

- Reproducible pinning and transport resilience are complementary controls: retries may
  improve availability only when the downloaded bytes are still authenticated by the
  reviewed checksum.
- Exact-main CI should not convert a transient EOF into a reason to bypass an applicable
  gate; the bootstrap should absorb a small bounded class of expected transport faults.
- Analogous bootstrap paths should use the same retry/cleanup shape when they fetch
  immutable reviewed release assets.
- A post-merge provider release remains blocked until every applicable exact-main push
  workflow is terminal `success`.

## Security and authority invariants preserved

- Protected V9 `app:app` remains unchanged.
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged.
- broker write remains OFF.
- `trading_methods=false` remains unchanged.
- `REAL_TRADING_ENABLED=false` remains unchanged.
- No provider secret, token, full identifier, connection URI or tenant-private payload is
  introduced or logged.
- No Cloudflare or Neon mutation is authorized by this CI transport correction.
