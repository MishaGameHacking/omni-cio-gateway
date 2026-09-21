# V10 Telegram Public User Legal / Privacy Activation Runbook

Status: **FOCUSED CAPABILITY ACTIVATION GATE / LIVE REGISTRATION BLOCKED**

This runbook converts the accepted operator attestation, current Russian
personal-data requirements and accepted repository/runtime evidence into a
fail-closed Telegram public-registration gate.

No private tax identifier, residential address, identity-document data or phone
value belongs in GitHub, CI, issue comments or artifacts.

## 1. Accepted operator input

Accepted factual input:

- Omni-CIO operator/controller is the PROJECT OWNER personally;
- legal form for this launch: natural person applying NPD, not an individual entrepreneur;
- OWNER is responsible for organizing personal-data processing;
- a public general contact exists;
- official address and tax identifier remain OWNER-private regulatory records.

This closes only `operator_controller_identity_and_contact`. It does not activate users.

## 2. Current hard localization blocker

Repository evidence currently preserves Neon PostgreSQL 18 in Frankfurt as
production database authority while Amendment 17 keeps Timeweb Moscow as the
Russian migration candidate.

Russian Federal Law 152-FZ article 18(5), in the current localization model,
requires the primary collection/storage operations for personal data of Russian
citizens to use databases in the Russian Federation, subject only to statutory
exceptions that Omni-CIO does not assume.

Therefore Telegram/public-user activation remains false while production
`OMNI_V10_POSTGRES_DSN` uses the accepted Frankfurt authority.

Required migration dependency:

`RU-PG-B -> RU-PG-C -> RU-PG-D -> production cutover acceptance -> Telegram activation review`.

RU-PG-B synthetic parity alone is not production cutover.

## 3. Processor / transfer boundary

### Telegram

Telegram remains identity-provider-only for the initial launch:

- OIDC scope `openid` only;
- no profile/phone scope;
- raw provider subject is not persisted;
- raw OAuth state/browser proof are not persisted.

Before launch, document the actual foreign-recipient flow and complete the
article 12 cross-border assessment/notification where applicable.

### Cloudflare

Cloudflare is a foreign edge/application runtime processor. The Worker receives
the browser request and the current source forwards canonical client IP evidence
to the Container for security semantics.

Before public activation:

- inspect the actual production observability and Workers Logs settings;
- ensure request bodies, auth codes, cookies, session credentials and provider payloads are not intentionally logged;
- document metadata categories and retention;
- complete the article 12 cross-border assessment/notification where applicable;
- do not treat EU/US localization products as Russian database localization.

Cloudflare Customer Metadata Boundary currently offers EU/US boundaries rather
than a Russian boundary, so it cannot replace the Russian primary PostgreSQL
localization gate.

### Support / subject requests

The currently OWNER-attested Gmail address remains a public general contact in
the pre-launch state. Gmail is not accepted as the primary personal-data subject
request intake because foreign storage/localization and transfer treatment has
not been accepted.

Before launch use either:

- a Russian-hosted mailbox under the Omni-CIO domain; or
- an authenticated in-product request channel whose primary storage is the
  accepted Russian PostgreSQL authority.

This document refers to that requirement as **Russian-hosted subject-request channel**.

## 4. Legal bases for the initial launch

Core registration/account/tenant/session:

- 152-FZ article 6(1)(5): contract conclusion/performance at the user's initiative.

Security and abuse protection:

- 152-FZ article 6(1)(7), bounded by necessity and user rights.

Statutory data-subject/regulatory handling:

- 152-FZ article 6(1)(2).

If consent is used for an additional purpose, article 9 requires the consent to
be separate from the other accepted/signed information. Initial launch does not
include a marketing purpose.

## 5. Data minimization / retention

Accepted source facts:

- Telegram scope = `openid`;
- raw Telegram subject absent from PostgreSQL;
- provider-auth transaction max lifetime = 15 minutes;
- production session policy = 2h idle / 24h absolute;
- plaintext session tokens are not persisted.

Launch legal/operational timings are fixed in the legal/privacy contract and
must not be widened casually.

## 6. Regulator gates

Before the first real public registration:

1. prepare and submit the article 22 processing notification using the current
   Roskomnadzor form;
2. record only sanitized registry/acceptance evidence in GitHub;
3. complete the article 12 cross-border assessment and separate notification for
   actual foreign-recipient flows where required;
4. publish the final privacy policy on every personal-data collection surface;
5. deploy the accepted Russian-hosted subject-request channel;
6. keep incident handling ready for the article 21 24h initial / 72h investigation window.

OWNER enters private address/tax identifier only in the regulator filing. Those
values never enter GitHub.

## 7. Activation boundary

Do not set either production flag true until every blocker in
`V10_TELEGRAM_PUBLIC_USER_LEGAL_PRIVACY_CONTRACT.json` is accepted:

- `PUBLIC_MULTI_USER_ENABLED`;
- `OMNI_V10_TELEGRAM_LOGIN_ENABLED`.

Staging remains false. VK ID, broker write, `trading_methods` and
`REAL_TRADING_ENABLED` remain independently false.

## 8. Machine verification

The governance guard must fail closed if:

- current production DB is treated as Russian-localized while Frankfurt remains authority;
- RU-PG-B synthetic parity is substituted for RU-PG-D production cutover;
- regulator/cross-border/public-policy/contact blockers are silently removed;
- production or staging auth flags become true in this pre-activation checkpoint.

## 9. References revalidated 2026-09-21

External legal/provider references were revalidated before this checkpoint:

- current Federal Law 152-FZ articles 6, 9, 12, 14, 18, 18.1, 20, 21 and 22;
- Federal Law 23-FZ of 2025-02-28;
- Federal Law 156-FZ of 2025-06-24;
- Roskomnadzor Order 180 of 2022-10-28;
- Cloudflare Workers Logs documentation;
- Cloudflare Data Localization / Customer Metadata Boundary documentation.

External references support the gate design. GitHub accepted evidence remains
the authority for actual Omni-CIO runtime state.
