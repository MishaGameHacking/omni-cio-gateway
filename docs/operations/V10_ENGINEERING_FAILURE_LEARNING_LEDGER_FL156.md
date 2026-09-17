# V10 Engineering Failure Learning Ledger — FL156

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_NEON_RUNNER_EGRESS_VS_PROVIDER_EDGE_AMBIGUITY`
- Scope: read-only external-boundary diagnosis after Production Release #70

## Accepted evidence chain

PR #532 was squash-merged as exact protected `main` `5ab04d9ea242d6220c4deb1a13d2d844e05b134d`.

Fresh Production Release #70 passed exact-main release provenance, Cloudflare authority, pinned delivery tooling, exact-SHA staging Worker + Container rehearsal, staging live acceptance, canonical production-domain validation and production Worker-anchor readiness before the existing production database bootstrap blocker.

The production bootstrap remained fail-closed. Its failure-only controls observed the same bounded `403 / HTML` response for authenticated, anonymous, User-Agent controls and an independent real curl request on the same self-hosted Windows runner. The resulting authorization, request-fingerprint and client-stack effects were all unchanged.

That evidence excludes an ordinary Python-versus-curl client implementation difference on the runner. It does not identify a specific firewall, IP reputation rule, WAF rule, TLS rule or provider policy.

Independent read-only provider access also confirms the canonical project remains healthy in the intended Frankfurt region on PostgreSQL 18. The project does not currently configure a database IP allowlist and does not block public database connections. Those project database settings do not by themselves prove how the management API edge treats a request.

## Root-cause gap

The next unresolved boundary is broader than client implementation:

1. the self-hosted runner's network egress path may be receiving a provider-edge denial before management-API authorization semantics are reached; or
2. the provider edge/API path may return the same denial independent of that particular runner egress.

Changing credentials cannot distinguish these cases because the accepted anonymous control is already denied identically.

## Focused diagnostic

Vary exactly one broader dimension: **egress origin**.

Use the same anonymous curl request shape from the trusted self-hosted Windows runner and a GitHub-hosted Ubuntu runner. The request targets a fixed repository-owned synthetic nonexistent project identifier rather than the protected real project selector.

This design intentionally requires no Neon credential, protected project selector, database DSN or private provider payload on the GitHub-hosted runner.

Both probes:

- use HTTPS only with normal certificate and hostname verification;
- use HTTP/1.1 and the same conservative curl User-Agent;
- disable redirects, proxy inheritance and curl user configuration;
- issue an anonymous GET only;
- discard the response body;
- emit only bounded HTTP status and media family;
- use bounded connection/process timeouts;
- treat missing curl, redirects, malformed output, transport failures and oversized output as unavailable.

The comparison reports only:

- `CHANGED` — the two status/media pairs differ, which is evidence of egress-path sensitivity;
- `UNCHANGED` — the pairs match, moving the next investigation toward provider-edge/API policy without claiming a specific rule;
- `UNAVAILABLE` — one comparison surface could not be proved and the diagnostic remains RED/inconclusive.

Neither `CHANGED` nor `UNCHANGED` is production acceptance. The real exact-project bootstrap gate remains authoritative and fail-closed.

## Blast radius and adjacent review

Review together:

- the accepted failure-only Neon authority diagnostics;
- the Cloudflare production-release bootstrap boundary;
- self-hosted bootstrap/cleanup rules;
- GitHub-hosted runner secret isolation;
- CI action-download resilience rules;
- provider-secret custody and the rule that third-party/portable verification must not receive runtime credentials merely for diagnostics.

The diagnostic does not change the production provisioner, its exact project/branch requirements, runtime role creation, database migrations, Cloudflare promotion, domain state or broker/product authority.

## Permanent regression / guard

Deterministic coverage requires:

- one fixed synthetic project identifier in source;
- no runtime/provider secret binding in the egress workflow;
- the same curl request intent on both runners;
- HTTPS-only, TLS verification, no redirects, no proxy/user-config inheritance and response-body discard;
- bounded parser and output;
- changed/unchanged/unavailable classifier coverage;
- unavailable evidence to remain RED;
- no IP, DNS answer, provider identifier, URL, response body/header, request ID, cookie, credential or DSN in emitted markers;
- exact source identity on both runners;
- no external checkout action on the self-hosted authority workflow;
- no mutation authority and no conversion of the existing production bootstrap RED to GREEN.

## Prevention law

When authentication, ordinary request fingerprint and independent client-stack controls are all observationally unchanged, do not add more credential or header permutations. Move outward one boundary at a time. To test whether a denial is egress-sensitive without widening secret custody, use the same anonymous request against a fixed non-sensitive synthetic resource from two controlled egress origins and compare only bounded response classes.

A changed result supports an egress-path hypothesis. An unchanged result supports moving the next investigation to provider-edge/API behavior. Neither result establishes a specific provider rule without separate evidence.

## Protected invariants

Protected V9 `app:app`; PostgreSQL 18 + RLS/FORCE RLS; `PUBLIC_MULTI_USER_ENABLED=false`; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; no provider secret/private payload disclosure; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
