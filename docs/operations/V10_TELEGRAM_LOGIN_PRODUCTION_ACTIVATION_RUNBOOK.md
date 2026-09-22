# V10 Telegram Login Production Activation Runbook

Scope: capability-specific activation for `telegram_login` under Amendment 13.

This runbook contains names and public callback/origin values only. Never paste the
Telegram Client Secret, provider tokens, identity-binding key, CSRF key or any other real
secret into GitHub, chat, CI logs, screenshots or artifacts.

## Canonical production registration

Official Telegram Login/OIDC reference:
`https://core.telegram.org/bots/telegram-login`

Register with BotFather Login Widget / OIDC:

- Allowed origin: `https://omnicio.ru`
- Redirect URI:
  `https://omnicio.ru/api/v10/web/auth/telegram/callback`

Telegram documents Authorization Code flow with PKCE and requires Allowed URLs to be
pre-registered before redirect/login processing.

Accepted repository evidence now records the OWNER attestation already preserved in merged PR #551: both exact values above were registered before the readiness gate. This is a non-secret external-action attestation only; it does not expose Client ID/Secret values and does not by itself activate public users.

## Timeweb runtime secret custody

Provider/runtime values must exist only in approved Timeweb App Platform environment/secret custody after the Timeweb candidate gate:

- `OMNI_V10_TELEGRAM_OIDC_CLIENT_ID`
- `OMNI_V10_TELEGRAM_OIDC_CLIENT_SECRET`
- `OMNI_V10_IDENTITY_BINDING_KEY_HEX`
- `OMNI_V10_CSRF_BINDING_KEY_HEX`

The production Timeweb app may receive only this reviewed allowlist. Synthetic/staging
proof must not inherit production provider-auth values.

Do not store the values in repository files, GitHub Actions logs/artifacts or retired
Cloudflare configuration. Approved Timeweb runtime environment custody is the future
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
