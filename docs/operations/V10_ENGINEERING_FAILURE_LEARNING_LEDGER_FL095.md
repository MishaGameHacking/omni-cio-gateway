# V10 Engineering Failure Learning Ledger — FL095

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, focused CF-D recovery PR `#450` after accepted main `2491ad5fb95321970d63e41ae36d3c30d04dbb3c`.

This entry records the exact Sonar findings exposed for exact PR head `b19d499b4cf97eb31808486072204e5ec1ba7611`. It does not authorize a new Work Package, public multi-user activation, Telegram/VK activation, broker write or Real execution.

## Failure evidence

Exact head `b19d499b4cf97eb31808486072204e5ec1ba7611` completed all 13 repository pull-request workflows with `success`, including the authoritative self-hosted Windows lane and the owning WP16–WP22A audits. The branch therefore had independent repository evidence for runtime/tests/contracts, but SonarQube Cloud remained RED with **Security Rating on New Code = D**, where A is required.

A later GitHub UI evidence capture exposed the three previously opaque annotations in `apps/api/cf_d_database_bootstrap.py`:

1. two `python:S4423` findings on the `ssl.create_default_context(...)` calls: use a stronger protocol or rely on Python 3.10+ secure defaults;
2. one `python:S3776` finding on the CF-D route installer: Cognitive Complexity `23`, allowed `15`.

The accepted toolchain already uses Python `3.14.6`, so the TLS findings did not prove that runtime negotiation had actually fallen below TLS 1.2. They did prove that the new security boundary did not express its minimum protocol contract in a form independently verifiable by the mandatory analyzer.

Public SonarPython source confirms the S4423 behavior: for `ssl.create_default_context`/`SSLContext`, an analyzer that cannot prove the configured source version is Python 3.10+ accepts an explicit `minimum_version` of TLS 1.2 or stronger. SonarPython S3776 uses a default maximum Cognitive Complexity of 15.

## Root cause class

`CF_D_TLS_FLOOR_AND_ROUTE_ERROR_ORCHESTRATION_NOT_EXPLICIT`

Two directly related representation defects remained after the provider-authority correction:

- the Container HTTPS trust context was returned directly from `ssl.create_default_context(...)`, so the source did not carry an explicit minimum TLS protocol even though the accepted runtime has secure Python/OpenSSL defaults;
- successive CF-D recovery hardening accumulated SHA, OIDC, provider-context, TLS, transport, bounded-response and payload-validation branches inside one route registration function, causing the security/error orchestration to exceed the repository's mandatory readability threshold.

Neither defect justifies a Sonar suppression, quality-profile change, threshold increase, Python-version trick or removal of fail-closed checks.

## Coherent correction

The exact finding set is corrected as one batch:

1. Create the TLS context through one helper, assign it to a named `SSLContext`, and explicitly set `minimum_version = ssl.TLSVersion.TLSv1_2` before returning it.
2. Preserve server certificate verification and hostname checking from `ssl.create_default_context`; do not set `CERT_NONE`, disable hostname validation or lower the protocol floor.
3. Use the same TLS 1.2+ floor for the Cloudflare ephemeral-CA path and the non-Cloudflare local/test fallback path.
4. Preserve Cloudflare runtime fail-closed behavior: when the runtime marker is active and the ephemeral Container CA is unavailable, bootstrap still stops with `CLOUDFLARE_CF_D_EGRESS_TLS_UNAVAILABLE`.
5. Extract request authorization, staging-provider consistency, TLS acquisition, provider transport, provider-payload validation and ready-response construction into bounded module-level helpers.
6. Route failures use one internal typed stop carrying only a bounded error code/status; no secret or provider identifier is attached.
7. Preserve all existing external behavior: exact SHA, OIDC, request-scoped provider context, no environment proxy inheritance, no redirects, bounded response body, exact production role/SHA/DSN validation and no destination authority in the Container.
8. Add deterministic TLS-policy tests proving TLS 1.2 minimum, `CERT_REQUIRED` and hostname verification on the new helper/fallback path.

## Blast radius searched

Reviewed directly coupled surfaces:

- `apps/api/cf_d_database_bootstrap.py`;
- `apps/api/cloudflare_runtime.py` route installation/startup behavior;
- `tests/test_v10_cloudflare_cf_d_bootstrap_egress.py`;
- `tests/test_v10_cloudflare_oidc_database_bootstrap.py`;
- the trusted Worker egress implementation and secret-bound Function-origin contract;
- the Cloudflare release-acceptance contract;
- the accepted Python 3.14.6/httpx 0.28.1 toolchain baseline.

Repository-wide search also found older accepted `ssl.create_default_context` usage in T-Bank/Watchtower/Real-trading support code. Those are not part of this CF-D new-code finding set, and Python 3.10+ defaults already provide the same TLS 1.2 floor. This focused repair therefore does not churn unrelated accepted broker/watchtower code or cross a future authority boundary merely to make a PR scanner green.

## Why preflight missed it

Focused preflight verified actual HTTPS context creation, Cloudflare CA fail-closed behavior, request-scoped provider failures, Worker destination authority, executable Node policy and repository tests. It did not reproduce Sonar's source-version inference for direct-return SSL contexts, and it did not measure Sonar Cognitive Complexity for the route installer.

The missing evidence was therefore analyzer-visible source structure rather than a failed runtime positive/negative test.

## Permanent prevention rules

For new Python network-security boundaries:

- express the minimum TLS version explicitly when protocol strength is part of the acceptance contract, even when the accepted Python runtime already has a secure default;
- retain certificate and hostname verification and add behavioral tests for all three properties;
- do not let one route/controller accumulate independent authentication, provider, transport, parsing and recovery branches; extract responsibilities before the mandatory analyzer threshold is exceeded;
- when Sonar annotation payload becomes available after an opaque failure, record the exact finding set and stop speculative repairs;
- never use `NOSONAR`, rule exclusions, a higher complexity threshold or weaker security settings as a recovery shortcut.

## Protected invariants

- protected V9 `app:app` unchanged;
- `PUBLIC_MULTI_USER_ENABLED=false` unchanged;
- broker write OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no transfer/withdrawal/margin/leverage/uncovered-short authority;
- no provider token, database credential, OIDC assertion, exact provider-origin value or private tenant payload committed or logged;
- CF-D production promotion remains exact-main/post-merge SUCCESS-only.
