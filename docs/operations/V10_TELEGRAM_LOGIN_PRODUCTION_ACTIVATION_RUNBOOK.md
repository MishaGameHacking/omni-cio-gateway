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

## Cloudflare secret binding names

Provider/runtime values must exist only in approved Cloudflare secret custody:

- `OMNI_V10_TELEGRAM_OIDC_CLIENT_ID`
- `OMNI_V10_TELEGRAM_OIDC_CLIENT_SECRET`
- `OMNI_V10_IDENTITY_BINDING_KEY_HEX`
- `OMNI_V10_CSRF_BINDING_KEY_HEX`

The Worker passes only this reviewed allowlist to the production Container. Staging does
not receive these provider-auth bindings from the production path.

Do not store the values in `wrangler.jsonc`, repository files or GitHub Actions secrets
merely to relay them into Cloudflare. Worker Secrets / approved Cloudflare secret custody
is the runtime authority.

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

## Sanitized Cloudflare readiness proof

The canonical read-only proof reuses the existing `V10 Cloudflare Provider Readiness`
workflow and its already-reviewed Cloudflare control-plane credential boundary. After this
checker is accepted on protected `main`, dispatch that workflow on `main` and require:

`CLOUDFLARE_TELEGRAM_LOGIN_READINESS=READY production_bindings=4 staging_bindings=0`

The probe reads only Worker secret-binding metadata. It requires exactly the four reviewed
production bindings above as `secret_text`, rejects duplicate/type drift, fails closed if a
provider response exposes a secret value, and proves that none of the four bindings exists
on `omni-cio-v10-web-staging`. It never copies Telegram/provider secret values into
GitHub secrets, repository files, logs, outputs or artifacts.

A feature-branch/manual run is not final activation evidence. The authoritative readiness
run is the accepted checker on protected `main`, before the separate activation change.

## Acceptance sequence

1. source-preparation PR exact-head DRAFT/READY GREEN and squash merge;
2. exact-new-main Regression Shield + Engineering Governance SUCCESS;
3. non-delegable Telegram Allowed URL/callback registration;
4. Cloudflare secret provisioning without exposing values;
5. read-only/sanitized readiness check proving named bindings exist;
6. repository pre-activation readiness contract passes: data minimization, bounded capacity/abuse controls, monitoring/rollback baseline and explicit unresolved legal/operator gate;
7. public-user legal/operator/privacy-notice sign-off is accepted for the actual launch context;
8. focused activation PR changing only the owning public-user activation state;
9. production release SUCCESS;
10. real canonical-Web USER login -> callback -> ordinary product account -> Tenant ->
    server-side Session;
11. logout/revoke, provider-availability and multi-user isolation negatives;
12. update capability state only from accepted real evidence.

At no point does login activation authorize broker write or Real-money execution.
