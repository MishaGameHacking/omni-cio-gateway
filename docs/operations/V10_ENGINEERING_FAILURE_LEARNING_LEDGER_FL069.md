# V10 Engineering Failure Learning Ledger — FL069

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, gate CF-C LIVE.

This entry records the exact-head CF-C failure observed on `c75783faa080d19f397744c24e8525b9c3a86261` after the external Cloudflare Containers permission boundary was corrected. It does not grant CF-C acceptance and does not authorize CF-D.

## Exact failure evidence

On the rerun of `V10 Cloudflare Candidate Deployment` for exact head `c75783faa080d19f397744c24e8525b9c3a86261`:

1. provider readiness passed;
2. Workers Builds authority passed;
3. stale staging autobuild quarantine passed;
4. the exact repository-pinned Cloudflare delivery toolchain installed successfully;
5. the pre-mutation Containers registry read probe passed with `CLOUDFLARE_CONTAINERS_REGISTRY_READ=READY`;
6. the isolated Neon staging runtime role and grants were provisioned successfully;
7. the staging Worker anchor was reused successfully;
8. the source created a nonmatching sentinel trigger and started a manual build bound to the exact branch and SHA;
9. the source immediately deleted that trigger before waiting for the build terminal state;
10. the remote build terminated `fail`; privacy-safe diagnostics classified it as `CLOUDFLARE_BUILD_COMMAND_PHASE_FAILED`;
11. live Worker/Container acceptance was skipped and the cleanup path completed successfully.

No production promotion occurred.

## Root-cause class

The durable engineering defect is an unsafe active-build lifecycle assumption in the source-controlled gated candidate orchestrator.

The earlier exact CF-C head `f2e388f3aebdf72e7b3c343a71a98eb0de8ed3e3` reached the Wrangler deployment phase with the same package build command. Between that head and `c75783f`, the build command did not change; the candidate orchestration changed to create a sentinel manual trigger and retire that trigger immediately after the build-start API returned.

Cloudflare documents manual build creation, build lifecycle/status, build cancellation and trigger deletion as separate operations. The current first-party contract does not state that deleting the owning trigger while its build is queued, initializing or running is safe. The source therefore crossed a provider-lifecycle boundary without evidence.

This is sufficient to correct even without exposing raw provider logs: an active build must retain the configuration object that created it until it reaches terminal state unless the provider explicitly guarantees otherwise.

## Blast radius

- Every gated CF-C manual candidate build uses the same trigger lifecycle.
- A trigger removed before terminal state can invalidate or race provider-side build configuration resolution.
- Immediate deletion is unnecessary for push-safety because the gated trigger already uses a branch sentinel that does not match `system/cloudflare-public-product`.
- Retaining a matching push trigger would be unsafe, so the sentinel requirement remains mandatory.
- Cleanup still must remove the temporary trigger after success or failure; a failed/timeout attempt must additionally cancel any nonterminal staging build through the existing quarantine path.
- No unrelated production trigger, provider token, database authority or broker boundary is changed by this correction.

## Correction

1. Keep the gated sentinel trigger present while the exact manual build is active.
2. Wait for the exact build to reach terminal provider state before ordinary trigger cleanup.
3. Preserve the existing post-attempt quarantine path as the single cleanup authority.
4. On success, cleanup deletes the now-unneeded sentinel trigger after terminal build acceptance.
5. On failure or timeout, cleanup deletes the trigger and cancels any remaining nonterminal staging build fail-closed.
6. Preserve refusal of preexisting triggers, exact branch+SHA build binding, no auto-build reuse, and no persistent push trigger.
7. Update the machine contract and source guard so immediate trigger deletion becomes forbidden.
8. Add deterministic positive and terminal-failure tests proving cleanup occurs only after the build wait path.

## Why prior preflight missed it

The deterministic tests proved exact manual build creation, sentinel branch filtering and eventual cleanup independently, but did not assert lifecycle ordering between active build wait and trigger deletion. The machine contract incorrectly encoded immediate deletion as required behavior, so the guard protected the defect instead of detecting it.

The durable regression guard now owns that ordering explicitly.

## Security and authority invariants preserved

- No raw Cloudflare build log payload is emitted.
- No API token, account identifier, registry identifier or database credential is added to source/evidence.
- Containers permission remains external provider authority and is not synthesized in code.
- No automatic paid overage or higher-plan authority is introduced.
- No production promotion occurs in this correction.
- `PUBLIC_MULTI_USER_ENABLED=false` remains protected.
- Telegram/VK activation remains blocked on their own real provider gates.
- `REAL_TRADING_ENABLED=false`, `trading_methods=false` and broker write OFF remain protected.
- CF-D remains blocked until real exact-head CF-C Worker + Container live acceptance succeeds.

## External contract evidence

Revalidated on 2026-08-31 against current first-party Cloudflare Workers Builds API/build documentation. The API exposes separate trigger creation/deletion, manual build creation, build lifecycle/status and cancellation operations. No first-party guarantee was found that authorizes deleting the owning trigger before an active build reaches terminal state. Documentation is supporting engineering evidence only; the corrected flow still requires real exact-head provider acceptance.
