# V10 Timeweb Public Ingress Acceptance Runbook

Scope: branch-local `P4_OMNICIO_RU_DNS_TLS` under Amendment 21.

The P3 branch-local source checkpoint is certified GREEN on exact head
`7a9051bf8775977b1ae1324fe6d1b460c1d21aec`. That source evidence does not claim
that a production PostgreSQL cutover or recovery rehearsal has physically happened.
P4 source implementation is therefore an acceptance verifier, not a DNS/domain
provisioner.

## Authority boundary

The canonical public origin is exactly `https://omnicio.ru`.

Official Timeweb App Platform guidance documents custom-domain attachment through the
App Platform panel: open the application, go to **Settings**, edit **Domains**, select
or enter the domain, and save. Timeweb then issues a free Let's Encrypt certificate for
the attached domain and renews it automatically.

Do not invent an undocumented provider endpoint for domain or DNS mutation. If the
domain is external to the Timeweb panel, use the A-record value shown by Timeweb and
perform that external DNS action only under the owning P4 split gate.

The repository controller is intentionally GET-only against the Timeweb App API. It does
not create, resize, stop, deploy, patch, attach, delete, or otherwise mutate an App
Platform resource.

## Preconditions before external cutover

1. Exact protected `main` SHA is known.
2. P3 production PostgreSQL acceptance/recovery evidence exists outside GitHub secrets;
   only its sanitized SHA-256 evidence digest is supplied to P4.
3. The exact release is active in the existing `omni-cio-v10` Timeweb application.
4. A distinct successful provider deployment SHA is known as the last-known-good
   application rollback target.
5. `PUBLIC_MULTI_USER_ENABLED=false` and
   `OMNI_V10_TELEGRAM_LOGIN_ENABLED=false` remain unchanged.
6. Representative Russian ordinary-Internet/no-VPN evidence can be collected after DNS
   and TLS settle.

P4 does not activate Telegram Login or public registration. P5 remains blocked until its
own legal/privacy/capacity/monitoring and real-login gates pass.

## External domain action

When the P4 split gate is explicitly approved:

1. In Timeweb Cloud open **App Platform** and the canonical `omni-cio-v10` application.
2. Open **Settings** -> **Domains** -> **Edit**.
3. Attach exactly `omnicio.ru`. Do not attach the historical `omni-cio.ru` domain.
4. If Timeweb identifies the domain as external, apply exactly the A record shown in the
   panel. Do not guess an IP address.
5. Wait for DNS propagation and Timeweb's automatic Let's Encrypt issuance.
6. Do not enable autodeploy, public-user flags, Telegram activation, broker write, or
   Real Trading.

## Observe

Run the manual workflow
`.github/workflows/v10-timeweb-public-ingress-acceptance.yml` from protected
`main` with the exact main SHA and `operation=observe`.

The observer uses normal HTTPS certificate and hostname verification, refuses redirects,
and checks:

- `https://omnicio.ru/livez` returns the exact accepted release SHA;
- `https://omnicio.ru/healthz` proves PostgreSQL readiness and non-synthetic runtime;
- the Web root returns HTML;
- HSTS, CSP, COOP, nosniff, Referrer-Policy, Cache-Control and Vary boundaries are present;
- no Cloudflare/Render response-header marker is observed.

Observation is read-only and does not require the Timeweb provider token.

## Accept

After successful observation, invoke the same workflow with `operation=accept`,
confirmation `ACCEPT_OMNICIO_RU_TIMEWEB_PUBLIC_INGRESS`, and only sanitized evidence:

- SHA-256 of the accepted P3 recovery evidence;
- SHA-256 of representative Russian ordinary-Internet/no-VPN evidence;
- exact distinct last-known-good rollback release SHA;
- SHA-256 of the rollback evidence.

The accept path re-runs public HTTPS verification and then uses
`TIMEWEB_CLOUD_API_TOKEN` only for read-only App Platform GET operations. It verifies
the canonical application/repository/branch/framework, autodeploy-off state, exact active
commit, `omnicio.ru` domain attachment, production PostgreSQL runtime binding, disabled
public/Telegram/VK flags, absence of retired-provider environment bindings, and successful
provider history for both current and rollback SHAs.

No raw token, DSN, provider resource ID, private user data or no-VPN evidence payload is
printed or persisted.

## Rollback / stop conditions

If any check fails, P4 remains unaccepted. Keep the last-known-good application release
and the prior DNS state where still safely reversible. Never repair P4 by weakening TLS,
removing tenant/RLS checks, enabling public users, restoring a retired Cloudflare hop, or
inventing a provider API.

P4 acceptance still does not authorize P5, broker write, `trading_methods=true`, or
`REAL_TRADING_ENABLED=true`.
