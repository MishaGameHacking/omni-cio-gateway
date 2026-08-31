# V10 Engineering Failure Learning Ledger — FL068

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, gate CF-C LIVE.

This entry records the exact-head provider-authority failure exposed after build-log diagnostics became precise. It does not grant CF-C acceptance and does not authorize CF-D.

## Exact failure evidence

On exact branch head `a178903416d05aa571f0d2495b466e38d98bc8db`:

1. provider readiness passed;
2. Workers Builds API authority passed;
3. the isolated Neon staging runtime was provisioned;
4. the staging Worker anchor was reused successfully;
5. Workers Builds repository connection, build token, staging database secret and trigger checks passed;
6. a real exact-head Workers Build was selected;
7. the terminal build-log classifier returned `CLOUDFLARE_CONTAINER_REGISTRY_UNAUTHORIZED`;
8. CF-C stopped fail-closed before live Worker/Container acceptance and before any production promotion.

No raw provider build-log payload, token value, full provider account identifier, registry identifier or database credential is required to retain this evidence.

## Root cause boundary

The immediate provider failure is at the Cloudflare Containers managed-registry authority boundary, not at source identity, build-log pagination, staging Worker discovery, Neon provisioning or generic Workers Builds configuration.

Cloudflare currently documents that:

- the API token selected for Workers Builds defines the access granted to the build for interacting with account resources;
- the automatically created Workers Builds token permission list includes Workers Scripts/KV/R2 and related baseline permissions but does not document Containers permissions;
- `Containers Read` grants read access to Containers and `Containers Edit` grants write access to Containers;
- `wrangler containers images list` is the supported read operation for the account's Containers registry;
- a Dockerfile-backed `wrangler deploy` builds and pushes the image to Cloudflare's managed registry.

Therefore a repository workflow must not assume that successful Workers Builds configuration authority implies Containers registry authority. The source can prove the missing boundary earlier and more cheaply, but source code cannot widen an external API token's provider permissions.

## Blast radius

- Every CF-C candidate using a Dockerfile-backed Cloudflare Container depends on effective registry authority in addition to Workers Scripts / Workers Builds configuration authority.
- Without a pre-mutation probe, a known provider-permission defect consumes a full staging database preparation plus a remote Workers Build before failing.
- Treating a read probe as full deployment authority would also be unsafe: image publication is a write operation, so exact-head candidate build and live acceptance remain mandatory.
- Printing Wrangler output to diagnose the failure would risk exposing provider identifiers or future sensitive response content and is forbidden.

## Durable prevention

1. Install the repository-pinned Cloudflare toolchain before any CF-C provider mutation.
2. Run the read-only exact command `wrangler containers images list --json` through the pinned Wrangler CLI before Neon or Cloudflare candidate mutation.
3. Suppress both stdout and stderr from the provider command and surface only source-controlled diagnostic markers.
4. Validate required environment authority and Cloudflare account identifier shape without printing values.
5. Bound the probe with a fixed timeout and no retry loop.
6. A failed registry read stops with exit code `78` and controlled code `CLOUDFLARE_CONTAINERS_REGISTRY_AUTHORITY_REQUIRED`.
7. A successful read only proves registry-read readiness; it never substitutes for container image publication, exact-SHA build acceptance or live Worker/Container acceptance.
8. Keep the existing Workers Builds and staging runtime provider checks fail-closed.
9. Add deterministic tests for exact command construction, output suppression, timeout behavior, authority validation, path containment and workflow ordering.
10. Preserve the provider-permission boundary: no source patch, CI bypass or synthetic success may impersonate an external token permission change.

## Security and authority invariants preserved

- No API token value is emitted or committed.
- No full Cloudflare account identifier is emitted or committed.
- No registry contents are emitted to CI.
- No new paid-plan authority is created.
- No production promotion is performed.
- `PUBLIC_MULTI_USER_ENABLED=false` remains protected.
- Telegram/VK provider activation remains disabled pending their own real provider gates.
- `REAL_TRADING_ENABLED=false`, `trading_methods=false` and broker write OFF remain protected.
- CF-D remains blocked until exact-head CF-C succeeds with real container publication and live runtime evidence.

## External references revalidated

Revalidated on 2026-08-31 against current official Cloudflare documentation for API token permissions, Workers Builds configuration, Wrangler Containers commands and Containers image management. External documentation is supporting contract evidence only; it is not accepted runtime evidence for this branch.
