# V10 Engineering Failure Learning Ledger — FL155

## Classification

- Work unit: `CLOUDFLARE-PUBLIC-PRODUCT-INTEGRATED / CF-D`
- State at discovery: `MAIN_RED_STOP`
- Failure class: `CF_D_NEON_CLIENT_STACK_VS_RUNNER_EGRESS_AMBIGUITY`
- Scope: failure-only Neon control-plane diagnostics after Production Release #69

## Accepted evidence chain

PR #530 was squash-merged as protected `main` `cf959be2a22ac3f98dac44988e284c69e229c3fa`. Its exact-main post-merge batch passed the repository-owned push workflows, and the release gate certified equivalent-tree Sonar evidence from the exact PR head before any provider mutation.

Automatic `V10 Cloudflare Production Release` #69 / run `35113500895` then passed Cloudflare provider authority, Workers Builds authority, Containers registry authority, the pinned delivery toolchain, reusable staging database-secret proof, exact-SHA staging Worker + Container rehearsal, staging live acceptance, canonical production-domain validation and production Worker-anchor readiness.

The production runtime database secret remained absent. The accepted production database provisioner therefore ran and stayed fail-closed on the existing Neon project-binding failure. The sanitized authority diagnostic again reported a project-read-forbidden credential class.

PR #530's bounded failure-only request controls produced the same externally observable result for all compared Python client requests:

- authenticated exact-project request: HTTP 403 with HTML media;
- anonymous same-path request: HTTP 403 with HTML media;
- anonymous request with no explicit User-Agent: HTTP 403 with HTML media;
- anonymous request with a curl-style User-Agent: HTTP 403 with HTML media.

The Authorization effect and ordinary request-fingerprint effect were both unchanged. No API key, project or organization identifier, request URL, response body, request ID, IP address, DSN, database credential or private payload is recorded here.

## Root-cause state

The evidence now excludes both Bearer-header presence and ordinary User-Agent variation as the explanation for the denial observed on the self-hosted Windows release runner. The remaining bounded ambiguity is between:

1. a TLS/HTTP implementation fingerprint specific to Python `http.client` and its TLS stack; and
2. an egress or provider-edge policy that denies the runner regardless of ordinary client stack.

The evidence does not identify a specific provider WAF, IP rule, TLS rule or proxy and must not be presented as proof of one.

Current Neon documentation continues to use the same `console.neon.tech/api/v2` endpoint family, Bearer authentication and curl examples. Project-scoped credentials remain intended for one-project automation. There is no evidence-backed reason to rotate the already-confirmed credential again, broaden its authority, change the provider host or treat the denial as success.

## Focused correction

Preserve all mutation, project, branch, database and PostgreSQL authority unchanged. Extend only the existing failure-only diagnostic after both earlier controls have already proved unchanged.

The added control executes one independent anonymous `curl` transport against the same validated exact-project HTTPS resource. It deliberately receives no Neon credential and no inherited proxy or user configuration authority. The command:

- resolves an installed curl executable before invocation;
- disables curl user configuration;
- permits HTTPS only and retains certificate/hostname verification;
- uses HTTP/1.1 and the same conservative curl-style User-Agent already exercised through Python so the comparison does not collapse into another ordinary User-Agent experiment;
- forces direct/no-proxy behavior to match the existing direct Python connection;
- follows no redirects;
- uses bounded connect/process timeouts;
- discards the response body;
- captures only HTTP status and Content-Type for mapping into the existing bounded media families;
- runs with a sanitized environment containing only Windows system-root variables when present.

A redirect, missing executable, timeout, non-zero curl result, malformed output, oversized output or invalid status is classified as independent-client unavailable. That state is diagnostic-only and never authorizes mutation.

The new client-stack effect is changed only when the real curl status/media pair differs from the already-proven Python curl-style control, unchanged when the pairs are identical, unavailable when curl evidence cannot be established, and explicitly skipped when an earlier narrower diagnostic already changed or became unavailable.

## Checkpoint RED and repair

The first published PR #532 checkpoint `28f7752b29397ce2edffc25b451863b51bc6618b` entered `RED_REPAIR_ONLY` immediately when Engineering Governance consumed the exact-head Sonar finding. Sonar reported one maintainability issue: the credential-transport orchestration function had Cognitive Complexity 16 while the repository threshold is 15. No security finding, authority broadening or provider mutation was implicated.

Root cause: the new independent-client decision was implemented as an additional nested conditional inside an already branch-heavy diagnostic orchestration function. The branch was functionally bounded, but the control-flow composition crossed the maintainability threshold.

Blast radius review covered the direct transport classifier, request-fingerprint classifier, independent-client classifier, skipped-state behavior and all marker-producing call sites. The repair extracts the independent-client decision into a small single-responsibility helper. The helper owns only whether to execute the independent probe and how to classify an earlier unavailable/changed request-fingerprint state; the orchestration function retains the existing sequencing and output contract.

No behavior, security boundary, timeout, curl command, marker field or mutation authority changes in this repair. Existing deterministic tests continue to exercise changed, unchanged, unavailable and skipped branches. Because repository content changes, all prior exact-head evidence is stale and the replacement SHA requires fresh complete certification.

## Blast radius and adjacent review

Directly reviewed:

- `scripts/probe_v10_neon_authority_diagnostics.py`;
- `tests/test_v10_neon_credential_contract_diagnostics.py`;
- Cloudflare production/candidate/provider failure-only diagnostic callers;
- `scripts/provision_v10_render_neon_preview.py` shared Neon `JsonApi` transport;
- `scripts/provision_v10_render_neon_preview_org_scope.py` / `OrgScopedNeonApi`;
- `scripts/provision_v10_cloudflare_neon_runtime.py` as the authoritative production database producer;
- FL152 scanner-safe deterministic diagnostic-vocabulary rule;
- FL154 request-fingerprint evidence;
- retained inactive Function/OIDC boundaries from FL136/FL137.

No shared provider transport is changed speculatively. No Neon Function or invocation-token path is reactivated.

## Permanent regression / guard

Deterministic coverage requires:

- the independent client to be anonymous and to receive no Neon credential in its command or subprocess environment;
- the exact project identifier to be validated before URL construction;
- HTTPS-only, certificate verification, no redirects, bounded timeouts and response-body discard;
- curl user configuration and proxy inheritance to be disabled for the bounded comparison;
- the real curl User-Agent and HTTP version to match the existing Python curl-style comparison as closely as the clients permit;
- subprocess output to be bounded and parsed only as one status line plus one Content-Type line;
- redirects, malformed output, oversized output, missing curl and transport/process failures to remain unavailable rather than GREEN;
- the independent client to run only after both Authorization and Python request-fingerprint effects are unchanged;
- changed, unchanged, unavailable and skipped client-stack states to have deterministic tests;
- secret/project/private-response material to remain absent from emitted markers;
- diagnostic orchestration complexity to stay below the active Sonar maintainability threshold by keeping independent client-stack selection isolated from credential/request sequencing;
- the tracked-content secret scanner to remain unmodified;
- the production provisioner and original RED exit status to remain unchanged;
- full exact-head CI, Sonar/security/review certification before squash merge and fresh exact-main post-merge/release evidence afterward.

## Prevention law

When a provider denial is unchanged by authentication and by safe ordinary request-header variation, do not continue rotating credentials or invent a provider rule. Vary exactly one broader boundary at a time. Before attributing a denial to runner egress/provider edge, compare an independent ordinary client stack on the same anonymous exact resource with the same protocol/header intent. If the independent client is also denied identically, move the next investigation outward to egress/provider edge; if it differs, repair the shared client/transport compatibility boundary instead.

When a diagnostic orchestration function already coordinates several fail-closed states, add a new classification boundary through an isolated helper instead of nesting another decision tree into the coordinator. This keeps security sequencing explicit without allowing maintainability complexity to accumulate.

## Protected invariants

Unchanged: protected V9 `app:app`; PostgreSQL 18 + RLS/FORCE RLS; `PUBLIC_MULTI_USER_ENABLED=false`; broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; transfer/withdrawal/margin/leverage/uncovered-short remain OFF/FORBIDDEN; no provider secret/value/private payload disclosure; WP23+, WEB-VISUAL, Telegram and AI/Cortex remain out of scope.
