# V10 Engineering Failure Learning Ledger — FL091

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, CF-D exact-main
production database bootstrap after accepted main
`2491ad5fb95321970d63e41ae36d3c30d04dbb3c`.

Owning recovery thread: `#430`.

This correction does not authorize public multi-user activation, Telegram/VK provider
activation, broker write, Real execution or any new Work Package.

## Failure evidence

Exact-main production release run `33956589149` reached the production database
bootstrap boundary twice while preserving fail-closed release sequencing.

The fresh second attempt completed all of the following before the failure:

- exact-main post-merge workflow gate;
- Cloudflare provider and Workers Builds authority checks;
- exact pinned delivery/control-plane toolchain installation;
- Containers registry authority;
- exact-main isolated staging Worker + Container deployment;
- staging `/api/v10/release` and `/healthz` acceptance;
- canonical public-domain configuration validation;
- production Worker anchor reuse.

Production still had no accepted runtime database binding, so the one-time OIDC
bootstrap path was required. The runner stopped at
`CLOUDFLARE_CF_D_STAGING_BOOTSTRAP_FAILED`; all production promotion, Custom Domain and
live-acceptance steps remained skipped, and cleanup/quarantine succeeded.

The source-controlled Neon Function was independently compared with the active provider
deployment. Provider drift was found: the active deployment predated the accepted OIDC
source. The exact accepted function source was redeployed through the connected Neon
control plane without handling or exposing a provider secret. A new release attempt
still failed at the same staging bootstrap boundary.

Neon function telemetry for the second failure window contained no invocation at the
bootstrap timestamp. That rules out an OIDC-claim/database-convergence rejection inside
the corrected Function as the immediate failure and localizes the remaining defect to
the staging Container -> Neon Function transport boundary before Function invocation.

## Root cause class

`CF_D_CONTAINER_DIRECT_NEON_FUNCTION_EGRESS_COUPLING`

The staging bootstrap proxy performed a direct public HTTPS request from the backend
Container to a runtime-derived Neon Function origin. Ordinary staging product health did
not exercise that egress path, and deterministic tests replaced `httpx.Client` with an
in-process double. Therefore exact-main staging health could be GREEN while the only
first-production-bootstrap egress path remained unproved.

This is not solved by requesting another long-lived secret, reintroducing Neon management
API authority, hardcoding project/branch identifiers, weakening OIDC validation, widening
network access, or treating a transport failure as success.

## Coherent correction

The failing block is hardened end-to-end rather than patching a single caller:

1. `apps/api/cf_d_database_bootstrap.py` keeps deriving the exact Neon Function origin
   from the live staging PostgreSQL branch metadata and endpoint cell, but sends the
   request to one fixed internal virtual egress hostname.
2. `cloudflare/src/index.js` exports `ContainerProxy` and maps only that virtual hostname
   through `Backend.outboundByHost`, using the supported Cloudflare Containers outbound
   interception path.
3. The trusted Worker egress handler accepts only `POST`, validates a bounded exact HTTPS
   Neon Function target in the Frankfurt cell with the dedicated `cfdprodbootstrap`
   function suffix, strips the internal target header, and forwards through Worker
   `fetch()` with redirects disabled.
4. The OIDC Bearer assertion remains short-lived and passes through only for the one
   bootstrap call. No Neon API key, project ID, organization ID or committed DSN is added.
5. Existing product internet behavior is not globally disabled or broadened. The change
   only supplies the missing deterministic bridge for the dedicated bootstrap hostname.
6. Deterministic regression tests prove the ContainerProxy export, virtual-host mapping,
   strict target validation, header stripping, no long-lived Neon management bindings,
   and the staging proxy's runtime-derived target handoff.

## Blast radius and adjacent failure modes

Directly coupled surfaces reviewed:

- staging-only CF-D bootstrap route;
- Cloudflare Worker -> Container request restoration;
- Container outbound network boundary;
- short-lived GitHub OIDC forwarding;
- source-controlled Neon Function verifier/database role convergence;
- production secret bootstrap/reuse gate;
- existing staging and production Worker anchors;
- exact-main production release ordering and rollback boundary.

Adjacent modes addressed or preserved:

- arbitrary URL/port/path/query redirection is rejected before Worker egress;
- the internal target header is never forwarded upstream;
- external caller headers cannot select a second product or tenant authority;
- provider response size remains bounded in the staging proxy;
- redirects and environment proxy inheritance remain disabled;
- malformed/failed provider responses remain fail-closed;
- production mutation remains impossible before the bootstrap succeeds;
- direct Real/broker authority remains unchanged.

## Why preflight missed it

The prior focused tests proved request construction, OIDC validation, bounded streaming,
Windows DACL custody and function-source invariants, but the provider call itself was
mocked. Staging `/healthz` proves the Worker/Container/PostgreSQL product path, not an
otherwise-unused outbound hostname. The provider-deployment/source comparison was also
not part of that deterministic test family.

For future Container integrations, a mocked HTTP client is insufficient evidence for a
provider-specific outbound network boundary. The Cloudflare Worker/Container egress
policy itself must be source-controlled and guarded when it is part of an acceptance
path.

## Protected invariants

- protected V9 `app:app` is unchanged;
- `PUBLIC_MULTI_USER_ENABLED=false` remains unchanged;
- Telegram/VK public activation remains outside this correction;
- broker write remains OFF;
- `trading_methods=false` remains unchanged;
- `REAL_TRADING_ENABLED=false` remains unchanged;
- no transfer/withdrawal/margin/leverage/uncovered-short authority is introduced;
- no provider token, database credential, OIDC assertion or private tenant payload is
  committed or logged;
- CF-D production promotion remains gated by exact-main SUCCESS-only evidence.
