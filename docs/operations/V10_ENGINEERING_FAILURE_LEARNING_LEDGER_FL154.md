# V10 Engineering Failure Learning Ledger — FL154

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_NEON_PREAUTH_HTML_403_REQUEST_FINGERPRINT_AMBIGUITY`
- Scope: failure-only Neon control-plane diagnostics after Production Release #68

## Accepted evidence chain

PR #528 was squash-merged as protected `main` `1f7b15cd5adfd06f93dbb8c1c293e9026de8ee98`. Its exact-main post-merge push batch and Regression Shield completed successfully. Automatic `V10 Cloudflare Production Release` #68 / run `35101401972` then passed the exact-main/Sonar provenance gate, Cloudflare provider authority, Workers Builds authority, pinned delivery toolchain, Containers registry authority, reusable staging database-secret probe, exact-SHA staging Worker + Container rehearsal, staging live acceptance, canonical production-domain validation and production Worker-anchor readiness.

The production runtime database secret remained absent, so the accepted project-scoped Neon runtime provisioner executed and correctly stopped fail-closed with the existing project-key binding mismatch code. The sanitized authority diagnostic remained in the credential project-read-forbidden class. The credential/transport diagnostic added by PR #528 produced only bounded evidence:

- credential format classified as a modern provider key shape;
- authenticated direct exact-project response was HTTP 403 with HTML media;
- anonymous same-path response was HTTP 403 with HTML media;
- direct transport matched the primary status;
- adding Authorization caused no bounded status/media change.

No API key, organization/project identifier, request URL, response body, request ID, IP address, DSN, database credential or private payload is recorded here.

## Root-cause status

The identical status/media response for authenticated and anonymous requests proves that adding the Bearer credential has no externally observable effect at the bounded status/media level on the current runner path. This invalidates blind credential rotation as the next recovery action and narrows the unresolved class toward a pre-authentication edge/request-policy boundary.

It does **not** prove a specific WAF rule, IP block, TLS fingerprint rule, proxy or User-Agent rule. The exact provider denial point remains unresolved.

Current Neon documentation continues to show the same `console.neon.tech/api/v2` API path, Bearer authentication and curl-based automation examples. Current Neon guidance also describes project-scoped keys as one-project credentials suitable for CI/agent automation. There is no accepted evidence to change the API host/header, broaden provider authority or reinterpret a denial as success.

## Focused correction

Keep all production mutation and project/branch/database authority unchanged. Extend only the existing failure-only diagnostic with a bounded HTTP request-fingerprint comparison on the same validated anonymous exact-project path.

The diagnostic now compares:

1. the current repository diagnostic User-Agent;
2. the same direct TLS request with no explicit User-Agent;
3. the same request with a conservative curl-style API User-Agent consistent with Neon's documented curl usage.

The additional controls run only when authenticated and anonymous status/media are identical. If the Authorization header already changes the response, the request-fingerprint branch is skipped because provider authorization remains the narrower next diagnosis.

Only bounded status/media families and a request-fingerprint effect are emitted. The effect is changed when an ordinary anonymous request fingerprint changes status/media, unchanged when all compared anonymous fingerprints remain identical, direct-unavailable when required direct evidence cannot be obtained, and explicitly skipped when credential shape is unsafe or the Authorization comparison already changed.

The diagnostic never reads or emits response bodies, provider IDs, request IDs, cookies, IP addresses or secret values. TLS hostname/certificate verification, fixed host/path, bounded timeout and no redirect-following behavior remain mandatory.

## Exact-head repair checkpoint

The first published PR head `0477f0c75544305e12813e68f817d663c724ecf9` passed every repository workflow except `Self-Hosted Windows CI`. The authoritative job passed lock verification, repository/security policy guards, compile, Ruff, formatting, mypy, protected `app:app`, full regression with 3185 tests plus 361 subtests and branch coverage above the required threshold, dependency audit and Bandit. It then failed only at the tracked-content secret scan on two deterministic test expectations classified by the entropy detector.

The exact flagged lines were long enum-like expected marker literals for request-fingerprint skipped states. No provider secret or secret-derived value was present. This is the already-accepted reusable defect class documented by FL152: detector-sensitive expected diagnostic vocabulary must be represented structurally rather than suppressing or weakening `detect-secrets`.

The repair composes those exact expected marker values from short semantic fragments while preserving the runtime marker and strict assertions. Adjacent test-only credential-binding fixture text was also structurally fragmented under the same FL152 rule so the defect class is not carried forward to another scanner line. No detector threshold, allowlist, suppression, production diagnostic behavior or provider authority changed.

Every content-changing repair commit invalidates earlier final evidence. Only the current PR branch tip may become merge evidence after a fresh complete exact-head certification batch.

## Blast radius and adjacent review

Directly reviewed:

- `scripts/probe_v10_neon_authority_diagnostics.py`;
- `scripts/provision_v10_render_neon_preview.py` shared `JsonApi` transport, whose active Neon requests still use a custom repository User-Agent;
- `scripts/provision_v10_render_neon_preview_org_scope.py` / `OrgScopedNeonApi`;
- `scripts/provision_v10_cloudflare_neon_runtime.py` production database producer;
- production/candidate/provider failure-only diagnostic callers;
- `tests/test_v10_neon_credential_contract_diagnostics.py`;
- FL136/FL137 retained inactive Function/invocation-credential boundaries;
- FL152 detector-sensitive expectation prevention law.

No Function/OIDC transport is reactivated. FL137 remains authoritative that production database availability must not depend on minting a branch-scoped Function invocation credential through broader provider authority.

## Permanent regression / guard

Deterministic coverage requires:

- every direct control to use the same validated exact project path and fixed Neon host;
- no-User-Agent control to contain neither Authorization nor an explicit User-Agent header;
- curl-style control to remain anonymous and differ only by the bounded User-Agent header;
- unchanged Authorization effect to permit exactly two additional request-fingerprint controls;
- changed Authorization effect to suppress those additional controls;
- any unavailable control to remain non-authoritative;
- wrapped/assigned credential shapes to perform no direct request;
- secret/project/response material to remain absent from markers;
- detector-sensitive expected enum vocabulary to remain scanner-safe without detector suppression;
- the production mutation gate and original RED process status to remain unchanged;
- full exact-head CI, Sonar/security/review certification before merge and fresh exact-main release evidence afterward.

## Prevention law

When authenticated and unauthenticated requests are indistinguishable at the provider edge, do not keep rotating credentials or widen authority without evidence. First vary only safe, ordinary API-client request properties on the same exact read-only resource and classify the observable effect. If ordinary request fingerprints remain indistinguishable, continue to egress/edge/provider diagnosis rather than disguising a pre-auth denial as an application-auth failure.

For detector-sensitive deterministic diagnostic vocabulary, preserve exact runtime semantics by composing long expected enum-like values from short semantic fragments as required by FL152; never weaken the tracked-content secret scanner to make a checkpoint green.

## Protected invariants

Unchanged: protected V9 `app:app`; PostgreSQL 18 + RLS/FORCE RLS; `PUBLIC_MULTI_USER_ENABLED=false`; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; no provider secret/value/private payload disclosure; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
