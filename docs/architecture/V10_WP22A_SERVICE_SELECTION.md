# Omni-CIO V10 — WP22A Service Selection Gate

Status: **REOPENED BY OWNER-APPROVED PUBLIC-HOSTED PLANNING CORRECTION / NO PROVIDER APPLY AUTHORIZED**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**

## 1. Why this gate is reopened

The earlier WP22A Phase-A selection was optimized for a browser-only PROJECT OWNER accessing the Lenovo Personal Node through Cloudflare Access + Tunnel. That design is useful historical/pre-production engineering evidence, but it no longer satisfies the 2026-08-18 final-product requirement.

The final product must be a public multi-user Web service whose ordinary availability does **not** depend on PROJECT OWNER home IP/Wi-Fi/router/LAN/Internet/Lenovo.

Controlling amendments after acceptance:

- `docs/master-plan/OMNI_CIO_V10_PRODUCT_USER_AND_ENGINEERING_AUTHORITY_BOUNDARY_AMENDMENT.md`;
- `docs/master-plan/OMNI_CIO_V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_AMENDMENT.md`;
- `docs/architecture/V10_PUBLIC_FREE_MULTI_USER_HOSTED_RUNTIME_CONTRACT.json`.

This file therefore supersedes the old statement `SELECTED FOR IMPLEMENTATION` for final public production. No provider mutation is authorized by this planning change.

## 2. Required final outcome

Select one production architecture for the existing source-controlled Omni-CIO Web/API and tenant-private state that satisfies all of the following:

- ordinary modern phone/desktop browser over normal Internet;
- public HTTPS hostname;
- no native VPN/device client for ordinary USER access;
- **managed-cloud production origin independent of OWNER home infrastructure**;
- one source-controlled Web App/Core, no competing site/repository/runtime stack;
- Telegram/VK -> internal Omni-CIO account -> server-side USER session as product authentication;
- API + database-enforced tenant isolation;
- tenant-scoped encrypted broker/private-data boundary;
- secure secrets/backup/recovery/replacement-runtime design;
- GitHub-controlled deployment/release provenance and rollback;
- measured capacity/abuse controls;
- privacy/personal-data/legal and broker-terms compatibility;
- preserved `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` until their owning future gates.

## 3. Cloudflare role retained but narrowed

Cloudflare remains a strong candidate for **edge functions** such as:

- authoritative/proxied DNS;
- public TLS/certificate lifecycle;
- WAF/DDoS/edge controls;
- optional origin protection/Tunnel where appropriate;
- source-controlled provider automation.

Official Cloudflare Tunnel behavior is still relevant: `cloudflared` can connect an origin outbound-only without a public origin IP and map a public hostname to a service. That property is useful for origin protection.

However, a Cloudflare Tunnel whose **sole production origin is the PROJECT OWNER's home Lenovo/network** is explicitly ineligible as the final V10 public-production architecture because loss of OWNER home power/Internet would remove service availability.

Cloudflare Access/account-member identity must not be the canonical Omni-CIO USER authentication system. It may remain an engineering/staging pre-auth layer only where separately justified.

## 4. Production-origin provider selection is not yet made

This planning correction intentionally does **not** hard-code Render, Timeweb, Cloudflare Workers/Containers, AWS, another VPS, or any other new V10 production host.

The implementation phase must perform a current service-selection decision using official provider information and the V10 engineering rules. At minimum compare:

- region/data-location and personal-data/legal suitability;
- managed PostgreSQL/storage/secret support;
- availability/restart/redeploy characteristics;
- encrypted backup/restore and off-device recovery;
- GitHub Actions/API/IaC automation;
- least-privilege runtime identities;
- private networking/edge integration;
- logging/monitoring without secret/private-data leakage;
- capacity/load/abuse controls;
- rollback/replacement-node procedure;
- pricing/free-tier limitations and predictable cost;
- provider lock-in/exit path.

A new recurring paid provider commitment requires OWNER approval after exact cost/authority consequences are presented. Planning may compare providers without purchasing or mutating anything.

## 5. Reusable controls from accepted Phase A

The following controls remain valuable and should be reused where compatible with the hosted architecture:

- exact Host validation;
- trusted reverse-proxy/protocol boundary;
- Secure/HttpOnly/SameSite server-side session cookies;
- session rotation, bounded idle/absolute lifetime, logout/revoke;
- CSRF and exact Origin/Referer checks on unsafe methods;
- CORS deny-by-default;
- bounded login/mutation rate limits;
- HSTS, CSP, `nosniff`, restrictive referrer policy and `no-store` where appropriate;
- direct-origin/API negative tests;
- fail-closed provider/runtime rollback;
- provider/runtime secrets kept out of source/PR CI;
- exact-head CI and post-merge Regression Shield.

The following old assumptions are **not** reusable as final product authority:

- Cloudflare account-member identity -> product USER session;
- exact OWNER fingerprint as product login;
- hard-coded OWNER user/tenant session bootstrap;
- Lenovo loopback backend as final production origin;
- final user experience restricted to PROJECT OWNER;
- permanent public multi-user disablement.

### 5.1 Historical Phase-A TLS markers — regression provenance only

The accepted Phase-A implementation used the following Cloudflare-specific TLS/certificate assumptions. They are retained here only so inherited regression guards can recognize the historical boundary while the final provider-selection gate is reopened:

- `Universal SSL`;
- `active Cloudflare full-DNS zone`;
- `first-level subdomain`;
- `Cloudflare owns edge-certificate issuance, renewal and deployment`;
- `X-Forwarded-Proto`.

These strings are **not binding final public-hosted provider requirements**. The finally selected provider/edge design must instead prove equivalent or stronger public TLS/certificate issuance, renewal, hostname coverage and an explicit trusted forwarded-protocol boundary. No historical marker authorizes provider apply or makes Cloudflare the final application host.

## 6. Broker/public-service separation

Production-origin selection must not assume T-Invest public connector permission. Current T-Invest documentation says ordinary client API access does not permit a public service with data retransmission.

Therefore the public Web/account platform and T-Invest-backed public features are separate activation gates. Hosted-provider selection must allow broker-backed functionality to remain fail-closed without preventing the account/Web platform from existing.

## 7. Exit from service-selection gate

This gate is not PASS merely because Cloudflare Phase A previously existed.

PASS for the corrected public target requires:

1. current official provider review;
2. explicit production-origin choice that satisfies no-home dependency;
3. data/secret/tenant isolation design;
4. recovery/rollback/capacity/cost/legal analysis;
5. source-controlled architecture/IaC intent with no production secrets;
6. deterministic tests/guards;
7. normal exact-head CI/review/merge/post-merge acceptance.

Until then, no final public production origin is selected and no provider mutation is authorized.
