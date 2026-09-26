# Omni-CIO V10 — Security Boundaries

Status: **ACTIVE ARCHITECTURE / AMENDMENT 18 TIMEWEB + TELEGRAM AUTHORITY**  
Runtime effect: **none until owning Exit Gates**

Current provider boundary: GitHub is engineering/provenance authority, Timeweb Cloud
is the selected V10 production infrastructure, and Telegram Login is the only
human product login provider. Cloudflare, Neon, Render, Cloud.ru and VK ID are
historical/retirement contours and receive no new feature authority.

## 1. Objective

Define authority boundaries so compromise of Web, Telegram, AI, GitHub, cloud edge/runtime or one USER account cannot automatically become cross-tenant disclosure, broker-secret disclosure or uncontrolled real-money authority.

Security model: **least privilege + tenant isolation + explicit authority + fail closed + evidence before action**.

## 2. Authority zones

### Zone A — GitHub engineering plane

May contain code, tests, schemas, migrations, safe defaults, policies/prompts/tool contracts/evals, CI/deployment/recovery logic and non-secret release metadata.

Must not contain real broker/Telegram/provider/recovery secrets, any retained legacy VK secret, full account IDs, private tenant portfolio/database payloads, private encryption keys or raw backups.

GitHub access is engineering authority only. It never grants a product USER session, tenant authority or trading authority.

### Zone B — CI / self-hosted runner

CI executes repository code and is treated as potentially dangerous if workflow trust is lost.

Required:

- reviewed exact-head source;
- runner/runtime identities separated;
- runner cannot read production tenant secrets/private backups;
- reviewed release/deploy identity separated from arbitrary PR code;
- clean workspace;
- privileged provider/deployment secrets unavailable to unaccepted PR code;
- no fabricated clean-room/OWNER evidence.

Lenovo `omni-cio-ci` is engineering continuity/authority evidence, **not** public production hosting.

### Zone C — Public hosted V10 runtime

The final public Web/API/private-state production runtime is an approved managed-cloud architecture independent of PROJECT OWNER home IP/Wi-Fi/router/LAN/Internet/power/Lenovo.

Sub-boundaries include Web/API, deterministic Core, tenant data/session layer, background jobs, Research, Telegram adapter, future AI worker, future Execution service, database/backup and edge/provider integration.

The public runtime must not become one broad identity that automatically has every tenant secret and every future trading authority. Least-privilege service identities and scoped decryption/access paths are mandatory where practical.

### Zone D — Tenant private-data / secret plane

For public V10, private state and broker credentials are tenant-owned hosted data, subject to accepted security/privacy/legal gates.

Canonical secret ownership:

`USER -> Tenant -> BrokerConnection -> READ / TRADE_OPTIONAL`

Requirements:

- no application-global USER broker token;
- encrypted at rest;
- raw secret never returned to browser after submission;
- no Web Storage/GitHub/CI/artifact exposure;
- tenant-aware authorization before runtime secret use;
- no Cortex/ordinary CI/unrelated-tenant raw secret access;
- rotation/revocation/audit metadata;
- recovery keys separated from protected data where applicable;
- backup/restore preserves tenant scope.

Protected V9 local/DPAPI secret contours remain valid historical/recovery authority until their owning V10 cutover.

### Zone E — Broker authority

Three capability classes remain isolated:

1. **READ** — monitoring/account/portfolio/market information only.
2. **Sandbox** — virtual-only authority.
3. **TRADE / Real** — optional same-tenant trading credential, separately gated; no transfer/withdrawal authority.

Public V10 execution eligibility remains:

`VERIFIED_READ_ACCOUNTS ∩ VERIFIED_TRADE_ACCOUNTS`

for the same tenant. No code may silently use a TRADE token as a convenience READ fallback or share one tenant's credential with another.

### Zone F — USER approval versus PROJECT OWNER authority

PROJECT OWNER engineering/business approval and a product USER's own portfolio/Real approval are different authorities.

`START V10`, GitHub merge, provider ownership or infrastructure access authorizes no user investment action.

When PROJECT OWNER uses Omni-CIO, the OWNER is an ordinary USER.

Future Real approval requires the authenticated USER acting only for that USER's own tenant/account, immutable plan/hash, recent/step-up product authentication, short lifetime and fresh preflight. Material drift invalidates approval.

### Zone G — AI authority

AI may call only allowlisted typed tools and is denied direct broker write, raw broker secrets, unrestricted SQL/filesystem/network/admin shell, GitHub protection bypass and Real-money approval authority.

Retrieved content is untrusted data, never policy authority.

### Zone H — Public Web / product authentication ingress

WP22A is the External Web Access / Product Authentication Security Gate.

Before corrected WP22A and launch gates pass, `PUBLIC_MULTI_USER_ENABLED=false` and production public activation remains locked.

Final public ingress requires:

- reviewed public TLS/certificate lifecycle;
- trusted edge/reverse-proxy/protocol chain;
- Telegram Login -> verified identity -> internal Omni-CIO account -> server-side USER session;
- GitHub/Timeweb engineering or provider identity kept outside product identity;
- Secure/HttpOnly/SameSite session controls, rotation/revocation/expiry;
- CSRF + Origin/Referer/Host/CORS controls;
- login/API abuse/rate limiting;
- direct API negative tests;
- database-enforced tenant isolation;
- cross-tenant IDOR/cache/job/backup/RAG negatives;
- production recovery independent of OWNER home access.

Timeweb managed ingress is the selected current public-production boundary. Cloudflare is not an authorized current/future V10 hop, and OWNER home Lenovo must never become the public-production origin.

## 3. Data classifications

### Public/low sensitivity

Code, architecture docs, public market/source references and non-secret release metadata.

### Internal engineering

Policies/prompts, synthetic tests/evals, deployment schemas and sanitized diagnostics.

### Tenant-private financial/product data

Positions, balances, operations, imported reports, decisions/plans/journal, research personalization, tenant-specific jobs/audit state and analytics.

Such data is not repository configuration and is inaccessible across tenants.

### Secret

Broker credentials, Telegram/provider secrets, any retained legacy VK secret, private encryption/recovery material, session secrets and authorization headers.

Secrets are never committed. Hosted secrets require approved encryption/access/rotation/recovery boundaries.

## 4. Critical negative guarantees

```text
GitHub/provider ownership    != product USER/tenant authority
PROJECT OWNER               != special product superuser
USER A session              != Tenant B authority
Object ID                   != authorization
Web session                 != raw secret access
GitHub/Timeweb identity     != Omni-CIO USER session
Read token                  != trading token
USER A broker token         != shared/global token
AI output                   != plan approval
Plan approved once          != changed-plan approval
Possible broker submit      != safe retry permission
Submitted order             != filled order
Public product target       != permission to expose unfinished service
Lenovo/home availability    != public production availability dependency
```

## 5. Kill-switch hierarchy

Protected V9/current safety switches remain binding until owning accepted WPs replace them:

- `REAL_TRADING_ENABLED=false` — master Real rollback;
- `WATCHTOWER_ENABLED=false` where applicable;
- `PUBLIC_MULTI_USER_ENABLED=false` — public-product activation remains off until corrected launch gates.

Disabling one optional component must not widen another component's authority.

## 6. Public-hosting and legal/broker gates

Public Web/account service and public broker-backed functionality are separate authority boundaries.

Current T-Invest ordinary client API terms do not grant public-service data-retransmission rights. A user-supplied token is not a broker-terms waiver. Public T-Invest-backed functionality remains fail-closed pending accepted permission/compliant architecture.

Hosted tenant-private data/credentials additionally require privacy/personal-data, retention, processor/location, backup/recovery and production legal acceptance.

Initial user access is free (`BILLING_ENABLED=false`, `TRIAL_ENABLED=false`, `SUBSCRIPTION_ENFORCEMENT=false`, `PREMIUM_FEATURE_GATING=false`). Future monetization is separate scope and cannot be used to bypass product/security gates.

## 7. Security-change rule

Any change crossing one of these boundaries requires explicit current-WP scope, threat review, deterministic negative tests where possible, least-privilege analysis, rollback/kill switch where relevant and ADR/amendment when the boundary changes architecturally.

No public activation, hosted secret custody, broker capability or cross-tenant operational surface is accepted solely because source code exists.
