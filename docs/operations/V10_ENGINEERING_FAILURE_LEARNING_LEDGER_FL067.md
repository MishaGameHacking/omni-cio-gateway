# V10 Engineering Failure Learning Ledger — FL067

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, gate CF-C LIVE.

This entry records two exact-head defects exposed on `f2e388f3aebdf72e7b3c343a71a98eb0de8ed3e3`: a stale build-history regression fixture and insufficiently specific privacy-safe classification of real Workers Builds deployment failures. It does not grant CF-C acceptance and does not authorize CF-D.

## Failure

1. The authoritative Windows merge gate passed repository/security guards, compilation, Ruff and mypy, then failed one deterministic test in `tests/test_v10_cloudflare_provider_readiness.py`.
2. The failing fixture described an exact candidate build without either `status` or `build_outcome`, while the hardened production implementation intentionally reuses only an exact successful build or an exact build whose provider status is still `queued`, `initializing` or `running`.
3. The live CF-C candidate reached Cloudflare Workers Builds and failed during the Wrangler deployment phase.
4. The build-log reader worked and returned `CLOUDFLARE_BUILD_DEPLOY_PHASE_FAILED`, but that category was too coarse to distinguish known container-registry authorization, Containers access, or first-deploy secret-inheritance failure modes without exposing provider log text.

The production reuse guard is correct and must not be weakened to satisfy a stale test. The test must model the provider lifecycle field explicitly.

## Root cause

The provider-history fixture predated the fail-closed reuse rule introduced to prevent a terminal failed build from being mistaken for a reusable exact-SHA candidate. Cloudflare's build-list fields are provider lifecycle evidence; absence of both lifecycle fields is not sufficient evidence that a build is safe to reuse.

The diagnostic classifier also stopped at phase-level context. This preserved privacy but discarded distinctions already available from bounded, source-controlled phrase matching. A provider failure can therefore remain safely classified without printing raw build logs, account identifiers, tokens, image registry identifiers, database values or other provider payloads.

## Correction

1. Model the reusable exact build fixture as `status=running`.
2. Add a regression proving an exact-metadata terminal `fail` build is not reusable.
3. Preserve the production fail-closed `_build_is_reusable` rule unchanged.
4. Add source-controlled, privacy-safe classifiers for:
   - container image context plus `Unauthorized`;
   - container image context plus `Authentication error` / `ApiError: Forbidden`;
   - the documented first-deploy binding-inheritance failure phrase or code `10057`.
5. Require container context before classifying generic authorization phrases as a Containers-specific failure, preventing unrelated deployment authorization errors from being mislabeled.
6. Surface only controlled diagnostic codes through the existing actionable-failure path; never print arbitrary provider log messages.
7. Preserve generic `CLOUDFLARE_BUILD_DEPLOY_PHASE_FAILED` when evidence is insufficient for a narrower category.
8. Add deterministic propagation tests proving a recognized container category reaches the fail-closed caller while an unrecognized deploy failure remains generic.

## Blast radius

- Reuse ambiguity affects every exact-SHA build-history lookup used by CF-C candidate bootstrap.
- Over-broad reuse could incorrectly attach acceptance logic to a terminal failed provider build; this remains prohibited.
- Under-specific diagnostics affect every real terminal Workers Build failure and can obscure whether the next correction belongs in source or at an external provider authority/plan boundary.
- Over-specific diagnostics would also be unsafe because they could falsely prescribe an external permission change. Context-gated classification therefore remains mandatory.

## Security and authority invariants preserved

- No provider response body or raw build-log line is emitted by the new classifier.
- No Cloudflare account identifier, build token, API token, database credential or private image identifier is added to diagnostics.
- No provider permission is synthesized or bypassed.
- No production promotion is performed by this correction.
- CF-D remains locked until exact-head CF-C succeeds with real provider/runtime evidence.
- `PUBLIC_MULTI_USER_ENABLED=false` remains protected.
- Telegram/VK provider activation remains disabled pending their authorized provider-registration gates.
- `REAL_TRADING_ENABLED=false`, `trading_methods=false` and broker write OFF remain protected.

## External contract evidence

Cloudflare's current Workers Builds API exposes lifecycle evidence separately from candidate metadata, and its current Containers/Workers tooling can report container deployment authorization failures after the Worker upload has already succeeded. The correction uses those external contracts only to make diagnostics more precise; it does not treat documentation or inferred provider state as successful runtime evidence.
