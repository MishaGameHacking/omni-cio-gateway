# V10 Engineering Failure Learning Ledger — FL079

Status: **FOCUSED CF-D CORRECTION / EXTERNAL AUTHORITY STILL FAIL-CLOSED**

Date: 2026-09-02

Owning issue: `#428`

## Failure

After the brand-focused PR #427 was squash-merged, exact accepted `main`
`92034ae66259bed6be77a5cd2c50212ea5b1a7b8` triggered `V10 Cloudflare Production
Release` run `33605832877`.

The release correctly passed the exact-main post-merge gate, Cloudflare credential
presence checks, Workers Builds authority, the pinned delivery toolchain, Containers
registry read authority and the pinned provider control-plane dependency install. The
staging rehearsal then stopped before candidate deployment with the sanitized provider
result:

`CLOUDFLARE_NEON_RUNTIME=STOPPED code=NEON_API_KEY_INSUFFICIENT`

No production Worker promotion, Custom Domain attachment or public cutover followed.

## Root cause

The immediate blocker is external Neon credential authority drift, not the brand change
and not a database-schema regression. The configured Neon credential values are present,
but the current API credential cannot read the exact project bound by `NEON_PROJECT_ID`.
The same Cloudflare/Neon source path had already passed real isolated staging Neon,
Worker and Container acceptance on the prior accepted Cloudflare source. PR #427 did not
modify the Cloudflare/Neon delivery implementation.

A directly coupled source review found a second, reusable defect class: the dedicated
`V10 Cloudflare Provider Readiness` workflow already calls the read-only exact-project
`probe_provider_access_from_env()` before provider mutation, while both the CF-C
candidate workflow and the CF-D exact-main production workflow previously relied only on
presence/shape readiness before proceeding to later work. The provisioner itself still
validated the exact project before database mutation, so authority remained fail-closed,
but unusable provider authority was discovered too late in the release path.

## Blast radius and analogous surfaces

Reviewed together:

- `.github/workflows/v10-cloudflare-provider-readiness.yml` — accepted read-only pattern;
- `.github/workflows/v10-cloudflare-candidate-deploy.yml` — analogous candidate path;
- `.github/workflows/v10-cloudflare-production-release.yml` — failing exact-main path;
- `scripts/provision_v10_cloudflare_neon_runtime.py` — exact-project authority producer;
- candidate/release contract guards and deterministic tests;
- production-domain and rollback steps downstream of the failed preflight.

The failure does not change tenant identity, PostgreSQL RLS semantics, Web presentation,
VK provider registration, broker authority or protected V9 recovery.

## Correction

Both mutation-capable Cloudflare workflows now reuse the already accepted read-only Neon
project probe immediately after the existing Cloudflare Workers Builds authority probe.

For CF-C, exact Neon project authority is verified before stale staging-trigger
quarantine, delivery-toolchain installation, Neon runtime-role provisioning, Worker
bootstrap or Workers Build configuration.

For CF-D, exact Neon project authority is verified before delivery-toolchain installation,
exact-main staging rehearsal, production database bootstrap, production deployment or
Custom Domain work.

The actual Neon provisioning validation is retained. The new preflight is an additional
early authority gate, not a replacement or bypass.

`tests/test_v10_cloudflare_neon_authority_preflight.py` permanently guards probe presence,
ordering and runtime-only GitHub Secret custody in both workflows.

## Permanent learning

- Credential presence is not credential authority. A release path must probe the exact
  resource permission it relies on before mutation or expensive preparation.
- A read-only provider-readiness probe must be reused by every later mutation-capable
  workflow that cannot consume the original readiness result as same-SHA evidence.
- Provider scope drift is a normal external failure mode. Re-running a previously proven
  source does not prove that a long-lived API credential still has the required project
  authority.
- Exact-project credentials are preferable to broad organization credentials when they
  satisfy the required operations; lack of broad organization access is not itself a
  failure when the exact project remains authorized.
- A source correction cannot fabricate provider authority. If the protected Neon
  credential remains insufficient, the release remains RED until the credential is
  corrected out of band and the real exact-project probe succeeds.

## Security and authority invariants preserved

- No Neon API key, Cloudflare token, database DSN or provider identifier value is stored
  in source, comments, logs or artifacts by this correction.
- Protected V9 `app:app` remains unchanged.
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged.
- VK/Telegram live activation is not performed by this correction.
- Broker write remains OFF.
- `trading_methods=false` remains unchanged.
- `REAL_TRADING_ENABLED=false` remains unchanged.
- No transfer, withdrawal, margin, leverage or uncovered-short authority is introduced.
