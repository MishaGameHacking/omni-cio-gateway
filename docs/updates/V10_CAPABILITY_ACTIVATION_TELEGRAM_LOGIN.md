# Omni-CIO V10 — Telegram Login Capability Activation Ledger

`WORKING CAPABILITY ACTIVATION STATE — NOT ACCEPTED MAIN AUTHORITY`

This ledger tracks the material `telegram_login` activation transition under Amendment
13. Accepted current state remains only in `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

## Identity

- Capability ID: `telegram_login`
- User-facing name: Telegram Login
- Owning WP/System Update: WP22A authentication architecture / Amendment 13 activation
- Accepted base `main` SHA: `66ef57dedd07ad68d472cb205da6bb8e87528e94`
- Branch: `activation/telegram-public-user-readiness`
- Dashboard: issue #549
- Canonical Web/runtime target: `https://omnicio.ru` / Cloudflare Worker + Container
- Current accepted capability state: `BLOCKED_EXTERNAL`
- Proposed capability state: `LIVE_OPERABLE`

## Implementation / technical evidence

- [x] Telegram OIDC Authorization Code + PKCE implementation is accepted.
- [x] Browser-bound state/proof, callback validation and session lifecycle are accepted.
- [x] Verified identity -> ordinary product account -> Tenant -> server-side Session is accepted.
- [x] Database-enforced tenant isolation and reserved historical OWNER-scope rejection are accepted.
- [x] Canonical Cloudflare production ingress/release is accepted through Release #84 / run `35379210101`.
- [x] Production runtime-only Telegram provider bindings are present and proven.
- [ ] Real browser login/logout/revocation is proven on canonical Web.

Readiness evidence:

- `V10 Cloudflare Provider Readiness` #81 / run `35367055812` completed `success` on exact protected main `ad01e78bdf38c2014f3c79f41d43da8db695c219`.
- Sanitized binding proof: `CLOUDFLARE_TELEGRAM_LOGIN_READINESS=READY production_bindings=4 staging_bindings=0`.
- No provider secret value is copied into GitHub, CI output, repository files or this ledger.

Repository preparation in this branch:

- explicit Worker -> production Container allowlist for provider-auth binding names;
- staging isolation from provider-auth secret propagation;
- public browser Origin authority decoupled from the internal Container Host;
- registration bound to the existing `PUBLIC_MULTI_USER_ENABLED` fail-closed gate;
- Telegram activation additionally requires `OMNI_V10_TELEGRAM_LOGIN_ENABLED=true`;
- VK ID remains independently gated by `OMNI_V10_VK_ID_LOGIN_ENABLED=false`;
- truthful UI/API reason while provider configuration exists but public or
  capability-specific activation is off.

## External blocker inventory

- [x] Telegram Allowed URL/origin `https://omnicio.ru` is OWNER-attested in accepted PR #551; this readiness change records that non-secret evidence explicitly.
- [x] Telegram OIDC callback `https://omnicio.ru/api/v10/web/auth/telegram/callback` is OWNER-attested in accepted PR #551; no provider secret value is recorded.
- [x] Runtime-only Telegram Client ID / Client Secret in Cloudflare secret custody.
- [x] Runtime-only identity-binding and CSRF keys in Cloudflare secret custody.
- [x] Public-user technical data-minimization inventory is frozen by `V10_TELEGRAM_PUBLIC_USER_ACTIVATION_READINESS_CONTRACT.json`.
- [x] Engineering capacity/rate-limit/DoS controls are frozen and regression-guarded for the current one-Container launch envelope.
- [x] Monitoring/rollback baseline is frozen: Cloudflare Workers metrics + exact-main `/healthz` release acceptance + bounded rollback; no paid logs/tracing expansion is assumed.
- [ ] Public-user legal/operator/privacy-notice sign-off is accepted for the actual operator, jurisdictions and data flows.
- [ ] `PUBLIC_MULTI_USER_ENABLED=true` accepted only after all owning gates close.
- [ ] `OMNI_V10_TELEGRAM_LOGIN_ENABLED=true` accepted only for the Telegram capability.
- [x] `OMNI_V10_VK_ID_LOGIN_ENABLED=false` remains fail-closed in this activation.

No secret value belongs in this file, issue #549, PR comments, CI logs or chat.

## Real-user operability evidence

Not yet accepted. Required later evidence:

- canonical `https://omnicio.ru` login button redirects to Telegram;
- callback verifies real provider identity and establishes only a server-side USER session;
- logout and revoke-all invalidate the correct user sessions;
- provider outage/misconfiguration produces a bounded fail-closed user-visible state;
- no OWNER/admin/demo/auth bypass is used.

## Multi-user / tenant isolation

Accepted structural implementation exists, but the real-user activation step still needs
sanitized live negatives before `LIVE_OPERABLE`:

- USER A cannot read USER B state;
- USER A cannot mutate USER B state;
- guessed object IDs do not widen tenant scope;
- revoke/logout is user-scoped;
- one user's provider/broker credentials cannot cross tenant scope.

## Kill switch / runtime availability

- Accepted capability state: `BLOCKED_EXTERNAL`
- Current runtime availability: provider login unavailable
- Kill switch / temporary suspension active: YES
- Reason: `PUBLIC_MULTI_USER_ENABLED=false` plus remaining public-user/provider registration evidence gates
- Recovery criteria: all blocker inventory items accepted with real sanitized evidence

## Monitoring / recovery

- [x] Provider misconfiguration fails closed.
- [x] Session revoke/logout paths exist.
- [x] Cloudflare release rollback/recovery exists.
- [ ] Provider-specific production availability/incident evidence accepted.

## State transition decision

```text
FROM: BLOCKED_EXTERNAL
TO: LIVE_OPERABLE
DECISION: BLOCKED
EXTERNAL GATES CLOSED: canonical Cloudflare ingress/release + production runtime secret custody
REMAINING BLOCKERS: public-user legal/operator/privacy-notice sign-off plus post-activation real-user/provider-availability and tenant-isolation evidence
EXACT EVIDENCE: issue #549 + current activation branch/PR
```

## GitHub acceptance lifecycle

- [ ] Exact-head DRAFT applicable checks all `success`.
- [ ] Independent review complete.
- [ ] Unresolved blocking review threads = 0.
- [ ] Fresh READY exact-head applicable checks all `success`.
- [ ] Squash merge complete.
- [ ] Exact-new-main Regression Shield `success`.
- [ ] Exact-new-main V10 Engineering Governance `success`.

This source-preparation PR must not change the accepted capability state or flip
`PUBLIC_MULTI_USER_ENABLED` to `true`.
