# V10 Engineering Failure Learning Ledger — FL153

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_NEON_HTML_403_AUTHORIZATION_EFFECT_AMBIGUITY`
- Scope: production Neon bootstrap recovery after accepted PR #526

## Accepted evidence chain

PR #526 landed as protected `main` `64ab95951ea9ab3958e84336103a8921db6f2d11`. Its required exact-main push workflows reached terminal `success`, and the automatic `V10 Cloudflare Production Release` #67 / run `35094750445` passed the exact-main/Sonar provenance gate, Cloudflare provider authority, Workers Builds authority, Containers registry authority, pinned delivery toolchain, reusable staging database-secret probe, exact-SHA staging Worker + Container rehearsal, staging live acceptance, canonical production-domain validation and production Worker-anchor readiness.

The production runtime database secret remained absent, so the exact project-scoped Neon bootstrap path executed and correctly stopped fail-closed with:

`CLOUDFLARE_NEON_RUNTIME=STOPPED code=NEON_PROJECT_KEY_BINDING_MISMATCH`

The existing sanitized authority diagnostic again classified the exact credential as `CREDENTIAL_PROJECT_READ_FORBIDDEN`.

The independent transport diagnostic added by PR #526 emitted only bounded non-secret evidence:

`credential_format=MODERN_NAPI primary_exact_project_status=403 direct_exact_project_status=403 direct_response_media=HTML transport_equivalence=MATCH`

No API key, project/organization identifier, response body, request URL, DSN, database credential or private payload is recorded here.

## Root cause status

PR #526 resolved an observability gap rather than the provider authorization failure itself. Fresh production evidence now proves that the repository secret has the modern `napi_` key shape and that two independent client stacks — the existing `urllib` transport and a direct TLS `http.client` request to the exact canonical project endpoint — receive the same HTTP `403`.

That evidence rules out the previously plausible wrapped/assigned-secret shape, an `urllib`-only proxy divergence and direct-network unavailability. It does not yet distinguish two materially different remaining classes:

1. the Bearer credential is specifically rejected by Neon/provider authorization; or
2. the runner reaches an edge policy that returns the same HTML `403` before Bearer authentication is materially evaluated.

The `HTML` media family is therefore important but not by itself proof of either class.

Current official Neon API documentation still specifies Bearer authentication, the `https://console.neon.tech/api/v2` API base and `GET /projects/{project_id}` for exact project details. Neon also documents project-scoped organization API keys as member-level access to their specified project. No official evidence supports changing the API hostname/header or bypassing exact project authorization.

## Permanent correction

Keep the production runtime provisioner and all project/branch/database mutation authority unchanged.

Extend only the failure diagnostic:

- after the authenticated direct exact-project probe, perform one bounded direct-TLS control request to the identical exact API path with no `Authorization` header;
- never perform either direct probe when the credential shape is classified as wrapped/assigned;
- emit only the anonymous HTTP status and bounded response-media family;
- emit a bounded `authorization_effect` classification:
  - `UNCHANGED` when authenticated and anonymous status + media are identical;
  - `CHANGED` when adding Bearer authorization changes status or media;
  - `DIRECT_UNAVAILABLE` when either direct probe is unavailable;
  - `SKIPPED_CREDENTIAL_FORMAT` for unsafe/malformed wrapped credential shape;
- do not read, log or classify response bodies, cookies, request IDs or provider identifiers;
- preserve strict TLS certificate/hostname verification, fixed `console.neon.tech:443`, exact path validation, short timeout and no redirect-following behavior;
- preserve the original provisioner exit status. Diagnostic evidence is read-only and never converts RED to GREEN.

## Blast radius and adjacent review

Directly affected:

- `scripts/probe_v10_neon_authority_diagnostics.py`;
- `tests/test_v10_neon_credential_contract_diagnostics.py`;
- production/staging failure-only callers that already invoke the diagnostic without trusting its exit code.

Reviewed unchanged authority boundaries:

- `scripts/provision_v10_cloudflare_neon_runtime.py` exact project/branch authority and PostgreSQL bootstrap;
- `scripts/provision_v10_render_neon_preview.py` canonical Neon API base and Bearer transport;
- `.github/workflows/v10-cloudflare-production-release.yml` original RED-exit preservation;
- Cloudflare candidate/promotion/domain/rollback gates;
- PostgreSQL 18, runtime roles/grants, migrations and RLS/FORCE RLS;
- protected V9 and broker/Real-money surfaces.

## Permanent regression / guard

Deterministic coverage requires:

- authenticated and anonymous probes use the identical exact project path;
- the anonymous control contains no `Authorization` header;
- same `403` + `HTML` on both probes classifies `authorization_effect=UNCHANGED`;
- anonymous API `401/JSON` versus authenticated `403/HTML` classifies `authorization_effect=CHANGED`;
- either direct probe unavailable classifies `DIRECT_UNAVAILABLE`;
- wrapped/assigned credentials trigger no direct or anonymous HTTP request;
- token/project identifier/private response material never appears in markers;
- existing project-scoped authority classifications remain unchanged;
- full exact-head CI, Sonar/security/review and exact-main release evidence remain mandatory before this learning affects recovery decisions.

## Prevention law

An authenticated provider denial must not be inferred from HTTP status alone when an edge can produce the same status before application authentication. When the response media or transport behavior is anomalous, compare the authenticated request to a safe unauthenticated control on the same exact endpoint before choosing a credential or network remediation. The comparison is diagnostic evidence only and must not weaken the mutation gate.

## Protected invariants

Unchanged: protected V9 `app:app`; PostgreSQL 18 + RLS/FORCE RLS; `PUBLIC_MULTI_USER_ENABLED=false`; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
