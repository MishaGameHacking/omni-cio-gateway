# V10 Engineering Failure Learning Ledger — FL165

## Scope

Current defect: issue #556 / MAIN_RED_STOP after accepted PR #554.

Exact failing main: `2e5f587519aac41351048c177d8365ec6fda40d7`.

Cloudflare Production Release #83 / run `35372118125` reached the exact-main staging rehearsal and failed the gated staging Workers Build during the deploy phase. Production promotion was skipped and the terminal release DAG failed closed.

This entry records the source-controlled repair class only. It does not declare the external provider healthy, does not fabricate a successful rerun, and does not authorize Telegram/public-user activation.

## Failure evidence

1. Exact-main post-merge verification reached `CLOUDFLARE_POSTMERGE_GATE=READY`.
2. Cloudflare provider authority, Workers Builds authority, the pinned delivery toolchain, Containers registry read authority, the staging Worker anchor and the reusable staging database secret all passed.
3. The gated manual exact-SHA staging build was created successfully.
4. The remote build terminated `fail`.
5. The privacy-safe classifier emitted `CLOUDFLARE_BUILD_DEPLOY_PHASE_FAILED`; the caller correctly failed closed as `CLOUDFLARE_STAGING_BUILD_FAILED`.
6. Production promotion and production recovery were skipped.
7. The release DAG terminal gate failed because the required staging rehearsal did not succeed.

The preceding exact-main Cloudflare Production Release #82 succeeded through the same staging and production provider authorities.

## Root cause

The repository configured the same source build in two independent places:

- the Workers Builds trigger uses `build_command = "npm run build"`;
- `wrangler.jsonc` also configured that network-dependent source build as Wrangler `build.command`.

The deploy command then runs `wrangler deploy`. Cloudflare documents Wrangler custom builds as executing as part of `wrangler deploy`, while Workers Builds itself is a build/deploy two-step pipeline. The source therefore allowed the deploy phase to re-enter source-identity generation, `npm ci` and Web compilation after Workers Builds had already completed the explicit build phase.

That duplicated build path expands the remote dependency/network failure surface, increases release time, and makes nested build failures appear only as a generic deploy-phase failure after the deploy command has started.

PR #554 changed no deployment/runtime inputs under `apps/`, `omni_cio/`, `requirements*.txt`, `Dockerfile.cloudflare`, `package.json` or `wrangler.jsonc`. The source-controlled duplicate build re-entry is therefore the directly relevant reusable defect in the failing path and must be removed before any provider failure is treated as transient.

## Blast radius

The defect affects both gated staging and gated production Workers Builds because both use the same `wrangler.jsonc` and the same explicit Workers Builds build command.

Without a permanent guard:

- every exact-SHA release can execute the source build twice;
- the second `npm ci` can introduce an avoidable network/supply-chain availability dependency inside deploy;
- staging and production can fail in deploy after a successful build phase;
- the generic deploy classifier can obscure that the failing work was a repeated source build;
- a same-SHA rerun can appear to “fix” the release by luck without removing the reusable defect.

## Correction

1. Keep `npm run build` as the explicit Workers Builds build command for staging and production.
2. Remove the top-level Wrangler custom `build` block so `wrangler deploy` does not re-enter the source build.
3. Preserve Wrangler's normal Worker bundling/upload and full Container rollout.
4. Preserve `package.json`'s pinned secure build script, including source-SHA generation and `npm ci --ignore-scripts` for the Web application.
5. Extend the release acceptance contract so build ownership is explicit and Wrangler custom-build re-entry is forbidden.
6. Add deterministic regression coverage that injecting any Wrangler custom build fails the repository guard.
7. Require the production build orchestrator to retain its explicit `_BUILD_COMMAND = "npm run build"` marker.

## Security and authority invariants preserved

- no Cloudflare token, build token, account identifier, raw provider log or secret value is added to source/evidence;
- staging/production database secret custody is unchanged;
- no direct Git auto-deploy is enabled;
- full Container rollout remains required;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- `OMNI_V10_TELEGRAM_LOGIN_ENABLED=false`;
- `OMNI_V10_VK_ID_LOGIN_ENABLED=false`;
- broker write remains OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`.

## Acceptance

This repair remains RED until the focused branch passes exact-head applicable CI/Sonar/review, is squash-merged, exact-new-main post-merge verification succeeds, and a fresh Cloudflare Production Release completes successfully on the resulting exact main.
