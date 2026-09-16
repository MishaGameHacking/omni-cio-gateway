# V10 Engineering Failure Learning Ledger — FL151

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_NEON_CREDENTIAL_TRANSPORT_DIAGNOSTIC_AMBIGUITY`
- Scope: read-only recovery evidence after the active project-scoped Neon runtime provisioner is denied before production database bootstrap

## Accepted evidence chain

Protected `main` `4d748105128b26935af8c1177386c27a2be39fac` completed the required 11 push workflows successfully. Fresh `V10 Cloudflare Production Release` run `35079319819` / run #66 then passed exact-main post-merge/Sonar provenance, Cloudflare provider authority, Workers Builds authority, Containers registry read, pinned delivery toolchain installation, staging database-secret reuse, isolated exact-SHA staging Worker + Container rehearsal, candidate live acceptance, canonical public-domain configuration and production Worker-anchor reuse.

The production runtime-secret probe correctly reported that the protected production `OMNI_V10_POSTGRES_DSN` was absent and that bootstrap was required. The active project-scoped runtime provisioner stopped before production promotion with:

`CLOUDFLARE_NEON_RUNTIME=STOPPED code=NEON_PROJECT_KEY_BINDING_MISMATCH`

The existing sanitized read-only diagnostic reported HTTP `403` from account/auth, configured organization, exact configured project, exact configured project branches and the bounded project-scoped canonical query, ending in:

`classification=CREDENTIAL_PROJECT_READ_FORBIDDEN`

Production Workers Build promotion, Custom Domain mutation and canonical live acceptance did not execute. Cleanup/quarantine succeeded.

Independent connected-provider evidence confirms the intended Frankfurt project still exists on PostgreSQL 18 and its default branch is ready. The PROJECT OWNER had already reconfirmed the repository Neon binding set before this fresh run. Repeating blind key rotation is therefore not accepted diagnosis.

No Neon API key value, key fingerprint, provider identifier, DSN, database credential, Cloudflare account identifier or private payload is recorded here.

## Root cause of the remaining diagnostic gap

The mutation gate is correctly fail-closed. The newly exposed defect is narrower: every current recovery read uses the same Python `urllib` transport and the same opaque repository secret value. Consequently a uniform `403` cannot distinguish these materially different causes:

1. a syntactically modern Neon Management API key that the provider rejects for the exact project;
2. a repository secret accidentally stored with shell-assignment or quote wrapping, while still being non-empty and therefore passing the current presence-only readiness check;
3. an HTTP transport/proxy/edge discrepancy on the self-hosted runner that returns `403` before the same exact request reaches Neon authorization;
4. a provider-side authorization inconsistency for an otherwise well-formed project-scoped credential.

The existing diagnostic intentionally does not expose secret material or raw provider bodies, but it also carries no safe evidence capable of separating credential serialization from HTTP transport from provider authorization. That ambiguity previously encouraged repeated OWNER secret iteration without new evidence.

Current Neon documentation establishes two relevant stable facts used only for diagnosis: Neon Management API requests use `Authorization: Bearer <API key>`, and newly created API keys use the recognizable `napi_` prefix while older keys remain valid. Project-scoped organization keys are intended to access one explicitly bound project. These facts permit a bounded non-secret format class; they do not permit logging any token content or treating a legacy-format key as invalid.

## Permanent correction

- Keep the active production runtime provisioner and its exact project/branch mutation gate unchanged.
- Extend only the failure diagnostic with a non-secret credential format class:
  - `MODERN_NAPI` when the consumed value has the current provider prefix and no wrapper evidence;
  - `WRAPPED_OR_ASSIGNED` only for deterministic shell-assignment, quote-wrapping or embedded-whitespace shapes that cannot be the raw bearer token expected by the API;
  - `LEGACY_OR_UNKNOWN` for every other non-empty value, because older Neon API keys remain valid and must not be rejected by format alone.
- A credential classified `WRAPPED_OR_ASSIGNED` must never be inserted into an additional diagnostic HTTP header. The direct probe is skipped and reports only bounded `SKIPPED` / `DIRECT_SKIPPED_CREDENTIAL_FORMAT` evidence. This prevents malformed-header exceptions from reflecting credential material in a traceback while preserving the original RED failure.
- For modern or legacy/unknown non-empty shapes, add one exact-project `GET` using an independent direct `http.client` TLS transport that does not use `urllib` proxy resolution.
- The direct probe must target only the configured exact project. It must not enumerate projects or organizations, mutate provider state, follow redirects, log request URLs containing identifiers, log response bodies, or expose the token.
- Emit only bounded status/media-family/equivalence metadata: exact HTTP status, `JSON|HTML|TEXT|OTHER|MISSING`, and whether the direct result matches the primary transport.
- Explicitly mask the credential value before any diagnostic request even though GitHub secret masking is already present.
- Keep diagnostics non-authoritative: transport divergence or a modern key format never converts the original provisioner failure to success.
- Preserve the original process exit status and all production promotion/rollback/domain/live gates.

## Blast radius and adjacent review

Directly reviewed:

- `scripts/probe_v10_neon_authority_diagnostics.py`;
- `scripts/provision_v10_cloudflare_neon_runtime.py` exact project/branch authority gate;
- `scripts/provision_v10_render_neon_preview.py` bearer-header and `urllib` transport implementation;
- `scripts/neon_function_invocation_credential.py` as an existing independent direct-HTTPS/TLS repository pattern;
- `.github/workflows/v10-cloudflare-production-release.yml` failure-only diagnostic invocation;
- `.github/workflows/v10-cloudflare-provider-readiness.yml` current presence-only secret readiness check;
- `tests/test_v10_neon_authority_diagnostics.py` and project-scoped mutation-gate tests;
- external recovery issue #430.

The retained legacy Neon Function bootstrap remains inactive and is not reintroduced by this diagnostic repair. No production database role, PostgreSQL schema, Cloudflare route, DNS/domain, public-user, broker or Real-money authority changes are part of this work.

## Permanent regression / guard

Deterministic coverage requires:

- recognizable modern key format is classified without logging the value;
- wrapped/assigned/embedded-whitespace inputs are classified without logging the value;
- a wrapped/assigned credential never reaches the direct HTTP probe or an Authorization-header construction path;
- wrapped/assigned skip evidence is bounded to `SKIPPED`, `MISSING` and `DIRECT_SKIPPED_CREDENTIAL_FORMAT` without token/project reflection;
- all non-modern non-empty inputs remain `LEGACY_OR_UNKNOWN`, not automatically invalid;
- the direct probe performs exactly one `GET` against the exact configured project path;
- the direct probe performs no `/projects?` enumeration and no organization request;
- TLS certificate/hostname verification remains mandatory;
- direct response body content is never emitted;
- JSON, HTML, text, other and missing response media are reduced to bounded labels;
- matching primary/direct statuses report `MATCH`, mismatched statuses report `DIVERGENT`, and direct network/TLS failure reports `DIRECT_UNAVAILABLE`;
- token/project/provider response material is absent from emitted markers;
- the existing mutation gate remains unchanged and RED on insufficient authority;
- full exact-head CI, Sonar/security/review certification and fresh exact-main post-merge production-release evidence remain mandatory.

## Prevention law

When an external authority failure is observed through one transport and one opaque secret source, repeated configuration changes are not evidence. Before requesting another OWNER credential action, diagnostics must separate secret serialization, transport/edge behavior and provider authorization using bounded read-only probes that never expose secret values or broaden authority. Diagnostics explain RED; they do not authorize GREEN. A credential shape already proven unsafe for an HTTP header must be classified without attempting a second request that could reflect it through client-side validation errors.

## Protected invariants

Unchanged: protected V9 `app:app`; PostgreSQL 18 + RLS/FORCE RLS; `PUBLIC_MULTI_USER_ENABLED=false`; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; no provider secret/fingerprint/private payload disclosure; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
