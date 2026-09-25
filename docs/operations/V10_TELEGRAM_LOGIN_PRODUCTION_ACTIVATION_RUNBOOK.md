# V10 Telegram Login Production Activation Runbook

Scope: capability-specific activation for `telegram_login` under Amendment 13.

This runbook contains names and public callback/origin values only. Never paste the
Telegram Client Secret, provider tokens, identity-binding key, CSRF key or any other real
secret into GitHub, chat, CI logs, screenshots or artifacts.

## Login identity vs optional Telegram bot

Omni-CIO public registration/login authenticates the human **Telegram USER account** through OIDC. Login must not require a Telegram bot chat, a `/start` command, a bot-linking record, or the `telegram:bot_access` scope. The current login implementation requests only `openid`.

Telegram's provider setup currently uses a BotFather-managed application representation to issue the OIDC Client ID/Secret and register Allowed URLs. Treat that only as Telegram Login client-registration metadata. It does **not** mean the user's Omni-CIO account is registered by chatting with the future Omni-CIO Telegram bot.

The optional Omni-CIO Telegram bot is a separate future WP23+ companion surface. It may be connected only from an already authenticated Omni-CIO account/session and must bind to that existing USER/Tenant server-side. It cannot create an account, mint/select a Tenant, or replace the OIDC login path.

## Canonical production registration

Official Telegram Login/OIDC reference:
`https://core.telegram.org/bots/telegram-login`

Register with BotFather Login Widget / OIDC:

- Allowed origin: `https://omnicio.ru`
- Redirect URI:
  `https://omnicio.ru/api/v10/web/auth/telegram/callback`

Telegram documents Authorization Code flow with PKCE and requires Allowed URLs to be
pre-registered before redirect/login processing. This registration must not request
`telegram:bot_access`; bot messaging is not part of account creation or login.

Accepted repository evidence now records the OWNER attestation already preserved in merged PR #551: both exact values above were registered before the readiness gate. This is a non-secret external-action attestation only; it does not expose Client ID/Secret values and does not by itself activate public users.

## Timeweb runtime secret custody

Provider/runtime values must exist only in approved Timeweb App Platform environment/secret custody after the Timeweb candidate gate:

- `OMNI_V10_TELEGRAM_OIDC_CLIENT_ID`
- `OMNI_V10_TELEGRAM_OIDC_CLIENT_SECRET`
- `OMNI_V10_IDENTITY_BINDING_KEY_HEX`
- `OMNI_V10_CSRF_BINDING_KEY_HEX`

The identity key also has one non-secret continuity companion:

- `OMNI_V10_IDENTITY_BINDING_FINGERPRINT_SHA256`

The fingerprint is SHA-256 of the decoded 32-byte identity-binding key, not SHA-256 of
the 64-character hexadecimal text. It is integrity metadata, not a substitute secret.
The runtime requires an exact match whenever Telegram credentials are configured and
fails startup with `TELEGRAM_AUTH_IDENTITY_BINDING_FINGERPRINT_MISMATCH` on drift.

The production Timeweb app may receive only this reviewed allowlist. Synthetic/staging
proof must not inherit production provider-auth values.

Do not store credential values in repository files, GitHub Actions logs/artifacts or
retired Cloudflare configuration. The fingerprint value may be retained as sanitized
operational evidence, but the underlying identity-binding key must never be copied with it. Approved Timeweb runtime environment custody is the future
authority; that custody is not yet accepted in the current pre-activation state.

## Public activation flags

All source-controlled activation switches remain off in this preparation:

- `PUBLIC_MULTI_USER_ENABLED=false`;
- `OMNI_V10_TELEGRAM_LOGIN_ENABLED=false`;
- `OMNI_V10_VK_ID_LOGIN_ENABLED=false`.

Provider credentials alone must not activate login/registration. A later focused Telegram
activation may set only `PUBLIC_MULTI_USER_ENABLED=true` and
`OMNI_V10_TELEGRAM_LOGIN_ENABLED=true` after the owning gates close.
`OMNI_V10_VK_ID_LOGIN_ENABLED` remains `false` until the separate VK ID capability
has its own accepted provider/live evidence.

When public multi-user is false, configured providers report
`PUBLIC_MULTI_USER_DISABLED`. When public multi-user is true but a provider's own switch
is false, that provider reports `PROVIDER_ACTIVATION_DISABLED`.

## Current provider readiness state

The former Cloudflare readiness proof (run `35367055812`) is preserved as
historical evidence only. Amendment 18 retired Cloudflare and the OWNER reports its
external resources/account were decommissioned, so that proof cannot satisfy current
activation readiness.

Before activation, a Timeweb-specific sanitized proof must establish that the four
reviewed runtime values are present in the accepted production app environment without
printing their values, and that no staging/synthetic path receives production auth
secrets. The proof must bind to the exact accepted GitHub main SHA and accepted Timeweb
release.

## Acceptance sequence

1. source-preparation PR exact-head DRAFT/READY GREEN and squash merge;
2. exact-new-main Regression Shield + Engineering Governance SUCCESS;
3. non-delegable Telegram Allowed URL/callback registration;
4. Timeweb App Platform candidate/release is accepted for the exact GitHub main SHA;
5. Timeweb runtime secret provisioning occurs without exposing values;
6. sanitized Timeweb readiness proves the reviewed bindings exist only in the accepted production runtime;
7. repository pre-activation readiness contract passes: data minimization, bounded capacity/abuse controls, monitoring/rollback baseline and explicit unresolved legal/operator gate;
8. operator/controller legal model and processing-purpose/legal-basis inventory are accepted without placing private regulatory identifiers in GitHub;
9. Timeweb PostgreSQL 18 production cutover is accepted with Russian location and recovery evidence;
10. Roskomnadzor processing notification is accepted with sanitized evidence;
11. Telegram cross-border processor-flow assessment plus any required notification is accepted;
12. Russian-hosted or in-product/Russian-stored data-subject request channel is accepted;
13. canonical omnicio.ru DNS/TLS and representative Russian no-VPN acceptance are complete;
14. final Privacy Policy is deployed on every personal-data collection surface;
15. focused activation PR changes only the owning public-user activation state;
16. production release SUCCESS;
17. real canonical-Web USER login -> callback -> ordinary product account -> Tenant ->
    server-side Session;
18. logout/revoke, provider-availability and multi-user isolation negatives;
19. capability state updates only from accepted real evidence.

At no point does login activation authorize broker write or Real-money execution.


## Two-phase Timeweb activation evidence seal

P5 uses a read-only, two-phase acceptance controller. No workflow in this gate mutates Timeweb App Platform settings, provider credentials, DNS, PostgreSQL, or deployment state.

Phase 1 produces `READY_TO_ACTIVATE` only when all of the following are true:

- the observed protected `main` SHA equals the expected release SHA;
- `/livez` and `/healthz` are healthy on `https://omnicio.ru`;
- the public provider surface reports Telegram as configured while public access remains disabled with `PUBLIC_MULTI_USER_DISABLED`;
- sanitized P3, P4, external legal/privacy/provider/capacity and rollback evidence digests are supplied;
- the rollback SHA is distinct from the current release.

The controller hashes that exact evidence set into a deterministic readiness seal. The seal must be carried unchanged into final acceptance. This prevents accepting a different release or different prerequisite set after the readiness decision.

Only after `READY_TO_ACTIVATE` may the bounded Timeweb runtime configuration action set both:

- `PUBLIC_MULTI_USER_ENABLED=true`;
- `OMNI_V10_TELEGRAM_LOGIN_ENABLED=true`.

The same action must preserve `OMNI_V10_VK_ID_LOGIN_ENABLED=false`. It must not change broker authority, `trading_methods`, `REAL_TRADING_ENABLED`, TLS verification, or any unrelated runtime permission.

Phase 2 may produce `LIVE_OPERABLE` only when the same exact SHA and readiness seal are presented, the public provider surface reports Telegram `enabled=true`, and sanitized real-user acceptance evidence covers login/callback/account/Tenant/session, logout/revoke/re-login, provider fail-closed behavior and cross-tenant negatives.

A digest is only a binding mechanism for previously accepted evidence. Supplying an arbitrary digest does not create or replace legal, regulatory, provider, privacy, recovery or real-user evidence.


### GitHub production-environment gate

The P5 workflow is manual-only and uses the existing `timeweb-production` GitHub Environment as a release/acceptance protection boundary. Before any readiness or acceptance probe it re-verifies that environment with the repository's read-only environment-policy verifier. Workflow permissions are limited to `actions: read` and `contents: read`; no Timeweb or Telegram credential value is injected into the workflow.

The actual Timeweb runtime-variable transition remains a bounded provider-panel action outside this read-only workflow. Timeweb App Platform variables are deployment settings for the application; do not copy their values into GitHub inputs, comments, logs or evidence files.

After the provider-panel change, redeploy/restart the application as required by Timeweb and then run the `accept` phase against the canonical production runtime. A provider-panel change by itself is never `LIVE_OPERABLE`.


## Identity-binding continuity and rotation

`OMNI_V10_IDENTITY_BINDING_KEY_HEX` is durable account/Tenant identity material, not
an ordinary disposable session key. It derives the keyed lookup from a verified Telegram
subject to the existing internal account. Replacing the key silently would make existing
bindings unresolvable.

Every configured production runtime must therefore also set
`OMNI_V10_IDENTITY_BINDING_FINGERPRINT_SHA256`. The runtime computes SHA-256 over
the decoded 32-byte key and compares it with the configured fingerprint before exposing
Telegram as configured. Missing, malformed or mismatched continuity metadata is a
startup/configuration failure.

Silent identity-key rotation is forbidden once external identity bindings exist.
Changing both the key and fingerprint together does not make rotation safe because the
database still contains HMAC bindings derived with the previous key. Intentional future
rotation requires a separately reviewed rekey migration/recovery procedure preserving
account/Tenant identity and cross-tenant isolation.

The CSRF binding key has different semantics: rotating it invalidates browser CSRF
continuity and may force re-authentication, but it must never replace the durable
identity-binding key.

## P5 capacity and concurrency boundary

The production runtime uses a bounded PostgreSQL connection pool with transaction-local
affinity. P5 requires a pool size of four and a five-second acquisition deadline.
Synchronous session lookup is offloaded from the ASGI event loop so an unavailable or
slow database request cannot globally block unrelated event-loop work.

The current provider-auth abuse limiter is process-local. Therefore P5 does not authorize
horizontal App Platform fan-out or a Timeweb Load Balancer across multiple application
instances. Timeweb documents horizontal application scaling by placing multiple
applications behind a Load Balancer. Such a topology requires a separately reviewed
distributed abuse-control/rate-limit design before it may become production authority.

Capacity/load acceptance must therefore prove the bounded single-application topology
for this activation. This restriction does not prohibit a future reviewed scale-out
architecture; it prevents local rate limits from being silently diluted across instances.
