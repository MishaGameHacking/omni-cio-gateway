# V10 Engineering Failure Learning Ledger — FL093

## Scope

Current System Update: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED`, CF-D focused recovery PR `#450` after accepted main `2491ad5fb95321970d63e41ae36d3c30d04dbb3c`.

This entry records the exact-head security-analysis failure after the request-scoped branch-context and formatter corrections. It does not authorize public multi-user activation, Telegram/VK activation, broker write, Real execution or a new Work Package.

## Failure evidence

Exact PR head `9ecc7ffb304fc495ccd69450e4d60c06d3bbbdf8` completed all 13 repository pull-request workflows with `success`, including the authoritative self-hosted Windows gate and all WP16–WP22A owning audits. A fresh manual Gitar review reported `Approved`, four resolved findings and no open issues.

SonarQube Cloud still failed the exact same head with **Security Rating on New Code = D** where A is required and reported three annotations. The connected GitHub surface exposes the failing rating and annotation count but not the private annotation payload, so this entry does not invent scanner text or claim that a specific rule location was returned.

The remaining changed network block was therefore reviewed directly against the observable data flow and the public SonarSource SSRF guidance. The code validated `request.url` inside `destinationUrl(...)`, but returned the original URL string and then rebuilt the network request from that original-derived value in `fetchCfDTrustedNeonRequest(...)`.

## Root cause class

`CF_D_VALIDATED_DESTINATION_NOT_CANONICALLY_BOUND_TO_NETWORK_SINK`

The external provider destination was already constrained by strict HTTPS/hostname/path policy and was no longer controlled by the Container. However, the network-sink helper still accepted a `Request`, re-read its URL and used a value derived from that URL as the fetch destination after validation.

That representation is weaker than the authority model requires: a trusted destination should be derived independently from the Worker runtime database binding plus validated branch metadata, and the network sink should be bound to that independently derived canonical destination rather than to the candidate request URL itself.

Public SonarSource guidance for SSRF remediation makes the same distinction: parse/validate the URL and pass the validated URI to the HTTP client instead of continuing to use the original tainted location. This correction is therefore a real least-authority improvement independent of whether the unavailable private annotation text names S5144 specifically.

## Coherent correction

The trusted Worker network boundary is hardened as one unit:

1. The expected Neon SQL URL is derived only from the already-validated Worker `OMNI_V10_POSTGRES_DSN` binding.
2. The expected Neon Function URL is derived only from that validated binding plus strictly validated `neon.branch_id` metadata.
3. `fetchCfDTrustedNeonRequest(...)` receives the independently derived expected URL separately from the candidate `Request`.
4. The candidate request URL must exactly equal the canonical expected URL, but it is never used as the fetch destination.
5. The network request is reconstructed against the canonical expected URL with destination-specific fixed redirect semantics and an explicit header allowlist.
6. Database forwarding is limited to the four Neon SQL protocol headers required by the accepted branch lookup; Function forwarding is limited to `Authorization`, `Accept` and `Content-Type`.
7. Arbitrary candidate headers, Host and legacy target-selection material cannot flow to the provider request.
8. The existing method, scheme, userinfo, port, path, query, fragment, Frankfurt and Function/SQL hostname policies remain fail-closed.
9. Executable Node regressions prove forged candidate URLs are rejected before fetch, an untrusted expected URL is rejected before fetch, and a valid request reaches the provider only through the independently supplied canonical URL with extra headers removed.
10. No Sonar suppression, exclusion, Quality Gate change or provider-authority widening is introduced.

## Blast radius searched

Directly coupled surfaces reviewed:

- Container virtual bootstrap request and HTTPS interception;
- Worker `outboundByHost` handler;
- Worker runtime PostgreSQL binding validation;
- Neon SQL-over-HTTP branch lookup;
- branch-ID-to-Function-origin derivation;
- provider request reconstruction and redirect handling;
- short-lived OIDC forwarding;
- Node executable egress tests and Python integration guards;
- production bootstrap/release ordering and rollback.

Analogous accepted source was also reviewed: the source-controlled Neon bootstrap Function derives its SQL destination from a validated connection-string hostname and constructs the outgoing HTTPS endpoint from that validated hostname rather than forwarding an inbound URL.

## Why this is not analyzer-driven weakening

The fix reduces authority at the network sink. It removes candidate-URL selection from the fetch target, strips non-allowlisted headers, and retains all existing fail-closed destination checks. It does not mark a vulnerability false-positive, suppress a rule, weaken a hostname pattern, broaden a provider region, introduce a management API credential or change any product/broker authority.

The exact new head requires a fresh complete verification cycle. If Sonar remains below A, the remaining annotation set is a new evidence-backed defect class and must be diagnosed again rather than suppressed.

## Protected invariants

- protected V9 `app:app` unchanged;
- `PUBLIC_MULTI_USER_ENABLED=false` unchanged;
- Telegram/VK public activation remains outside this correction;
- broker write OFF;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- no transfer/withdrawal/margin/leverage/uncovered-short authority;
- no provider token, database credential, OIDC assertion or private tenant payload committed or logged;
- CF-D production promotion remains gated by exact-main SUCCESS-only evidence.
