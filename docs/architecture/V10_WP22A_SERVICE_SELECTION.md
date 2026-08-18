# Omni-CIO V10 — WP22A Service Selection Gate

Status: **MANAGED-CLOUD ORIGIN RECOMMENDED / OWNER COST APPROVAL REQUIRED / NO PROVIDER APPLY AUTHORIZED**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**

## 1. Authority transition

The earlier WP22A Phase-A selection was optimized for a browser-only PROJECT OWNER accessing the Lenovo Personal Node through Cloudflare Access + Tunnel. That design remains historical/pre-production engineering evidence, but it does not satisfy the final public multi-user product requirement.

The OWNER-approved public-hosted correction requires a normal public Web service whose availability does **not** depend on PROJECT OWNER home IP/Wi-Fi/router/LAN/Internet/Lenovo and whose normal Russian USER path remains practically reachable from ordinary Russian networks.

The implementation review recorded in:

- `docs/architecture/V10_WP22A_MANAGED_CLOUD_ORIGIN_DECISION.md`;
- `docs/architecture/V10_WP22A_MANAGED_CLOUD_ORIGIN_CONTRACT.json`;

now recommends **Cloud.ru Evolution** as the managed-cloud provider boundary, pending exact recurring-cost approval by PROJECT OWNER before any provider resource is created.

Historical lifecycle marker for regression provenance only: `Production-origin provider selection is not yet made`. That statement described the reopened gate before the current Phase-1 recommendation and is **superseded as current human authority** by this section. Machine-readable current authority is the managed-cloud-origin contract, whose state is `RECOMMENDED_PENDING_OWNER_COST_APPROVAL` and `provider_apply_authorized=false`.

No provider mutation is authorized by this recommendation.

## 2. Required final outcome

The recommended production architecture must continue to satisfy all accepted V10 properties:

- ordinary modern phone/desktop browser over normal Internet;
- reliable normal access for the intended Russian USER population;
- public HTTPS hostname;
- explicit **public TLS/certificate lifecycle** with reviewed issuance, renewal, runtime delivery and rollback;
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

## 3. Current recommendation

Pending OWNER recurring-cost approval, the recommended boundary is:

```text
ordinary Internet browser
        |
        v
Cloud.ru Evolution DNS
        |
        v
Cloud.ru Evolution L4 Network Load Balancer
public IP + health checks
minimum 2 resource units
        |
        +-------------------+
        |                   |
        v                   v
Evolution VM A         Evolution VM B
Nginx TLS + Omni-CIO   Nginx TLS + Omni-CIO
        |                   |
        +---------+---------+
                  |
                  v
         private VPC/subnet
                  |
                  v
       Managed PostgreSQL
        Primary + Standby
                  |
          +-------+-------+
          |               |
          v               v
 Secret Management   encrypted recovery
 / Key Management    / Object Storage
```

Binding recommendation properties:

- provider/runtime: Cloud.ru Evolution VMs in Russia;
- runtime: two application VMs behind Evolution NLB, not one permanent application node;
- DNS: Evolution DNS;
- TLS certificate lifecycle: Evolution Certificate Manager + Let's Encrypt;
- TLS termination: Nginx on the runtime VMs because Evolution NLB is L4;
- database: private Managed PostgreSQL Standard, two-node Primary/Standby;
- database public IP: forbidden;
- tenant/runtime secret store: Secret Management with Key Management or reviewed provider system key;
- outbound Internet: reviewed sNAT;
- provider automation: Terraform for currently supported Evolution resources plus Cloud.ru Public API for current NLB v2, all driven from reviewed GitHub source;
- public broker connector: fail-closed independently of public Web/account availability.

Current Cloud.ru Load Balancer v2 documentation says a L4 load balancer has a minimum of **2 resource units** and that Terraform is currently **not supported** for Load Balancer management. Therefore NLB automation must use the reviewed Cloud.ru Public API rather than a stale Terraform assumption. Terraform remains preferred for supported resources.

Cloud.ru Container Apps is **not** the selected primary runtime. Current Cloud.ru documentation states that Container Apps does not support Managed PostgreSQL connectivity and that an external database opened to the Internet is not a safe scenario; therefore the secure reviewed path uses VMs + private VPC + Managed PostgreSQL.

## 4. Cloudflare primary edge rejected for normal Russian USER traffic

Cloudflare remains useful historical engineering knowledge, but it is no longer a strong candidate for the **primary or sole** Russian-user production edge.

Cloudflare's own incident analysis from 2025 and support guidance updated on 2026-04-23 report systematic Russian-ISP throttling of Cloudflare-protected websites, with Russian visitors likely to experience failures or unusable sites. That conflicts with the V10 requirement that a normal USER in Russia can open Omni-CIO through an ordinary Internet browser without a VPN/native client.

Therefore:

- Cloudflare Tunnel is removed from the recommended normal public product path;
- Cloudflare proxied HTTP/TLS must not be the sole/primary Russian-user edge;
- Cloudflare/GitHub/provider membership remains forbidden as product identity;
- any future Cloudflare secondary/non-primary role requires a separate reachability, cross-border/personal-data, cost and failure-mode review.

The earlier Phase-A Cloudflare source remains dormant historical regression evidence only and does not authorize final production use.

## 5. Russian personal-data boundary

For the intended Russian USER population, the primary identity/session/tenant data plane is Russia-region only unless a later legal review accepts a statutory exception.

The current official text of Federal Law No. 152-FZ Article 18 part 5 is treated as a production localization gate. Cloud.ru Evolution currently states that its infrastructure is located in the Russian Federation and that Evolution is attested for 152-FZ UZ-1.

Provider attestation does **not** remove Omni-CIO's own operator, access-control, application-security, privacy, consent, notification or other legal duties. Production legal signoff remains mandatory. Cross-border processing remains fail-closed until separately reviewed.

## 6. Reusable controls from accepted Phase A

The following controls remain valuable and must be reused where semantically valid:

- exact Host validation;
- trusted reverse-proxy/protocol boundary;
- Secure/HttpOnly/SameSite server-side session cookies;
- session rotation, bounded idle/absolute lifetime, logout/revoke;
- CSRF and exact Origin/Referer checks on unsafe requests;
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
- Cloudflare proxied path as the only normal Russian USER path;
- final user experience restricted to PROJECT OWNER;
- permanent public multi-user disablement.

### 6.1 Historical Phase-A TLS markers — regression provenance only

The accepted Phase-A implementation used the following Cloudflare-specific assumptions. They remain quoted only so inherited regression guards can recognize dormant historical source while WP22A is reworked:

- `Universal SSL`;
- `active Cloudflare full-DNS zone`;
- `first-level subdomain`;
- `Cloudflare owns edge-certificate issuance, renewal and deployment`;
- `X-Forwarded-Proto`.

These are **not binding final public-hosted provider requirements**. The current recommendation instead uses Evolution DNS + Certificate Manager/Let's Encrypt + Nginx TLS behind Evolution NLB.

## 7. DDoS/WAF and abuse-control boundary

Cloud.ru documents baseline infrastructure protection including channel-capacity DDoS protection and perimeter segmentation. That infrastructure control is useful but is not treated as an application WAF.

Before public activation, the base source-controlled path must prove Nginx and application controls for request/connection limits, Host, HSTS/CSP/security headers, CSRF, Origin/Referer, CORS, server-side session/tenant authorization, malformed/oversized requests and direct-origin bypass.

Cloud.ru also offers Qrator/StormWall DDoS/WAF services. They are **not silently included** in the base recommendation because current managed WAF options materially change recurring cost and TLS certificate/private-key custody. If abuse/load evidence requires a managed WAF, that becomes a separate explicit WP22A cost/security decision before public scale.

## 8. Provider comparison disposition

### Cloud.ru Evolution

**RECOMMENDED_PENDING_OWNER_COST_APPROVAL.** Strongest reviewed combination of Russian placement, private Managed PostgreSQL, Primary/Standby, Secret Management/KMS, native DNS/NLB/Certificate Manager and source-controlled Terraform/API automation.

### Timeweb Cloud

**FALLBACK_LOWER_COST.** Russian regions, Managed PostgreSQL, private networking and Terraform/API support are attractive, but the current review did not establish an equivalent general native Secret Management/KMS boundary for tenant broker credentials.

### Yandex Cloud

**SECURITY_STRONGER_HIGHER_COST_ALTERNATIVE.** Mature Russian Managed PostgreSQL + Lockbox + KMS; retained if later availability/security requirements justify the higher cost.

### Render

**REJECT_PRIMARY_PRODUCTION_DATA_PLANE** for public V10 Russian-user personal data because the reviewed regions do not include Russia and free Web/Postgres limitations are not production-suitable. Protected V9 `app:app` remains unchanged.

### Cloudflare primary edge

**REJECT_PRIMARY_OR_SOLE_RUSSIAN_USER_PRODUCTION_EDGE** because Cloudflare's own current support evidence says ISP throttling can make protected sites unusable for Russian users.

## 9. Cost boundary

Current official Cloud.ru references give a lower-bound engineering estimate, not a purchase quote:

- Managed PostgreSQL Primary/Standby reference: about **3,792.05 RUB/month**;
- two reference application VMs with 20 GB boot disks: about **1,722.99 RUB/month**;
- sNAT: about **149.33 RUB/month**;
- current Evolution NLB minimum 2 resource units + public IP: about **1,305.89 RUB/month**, before traffic;
- one public Evolution DNS zone for 30 days: about **32.94 RUB/month**;
- Evolution Certificate Manager: currently free.

Reference initial stack: about **7,003.20 RUB/month**.

Excluded from that lower bound: domain registration, extra Object Storage/traffic/monitoring, managed external WAF/DDoS, larger VMs, later scale and Business Multi-AZ PostgreSQL.

The exact provider cart must be revalidated immediately before purchase. A new recurring paid provider commitment requires explicit OWNER approval after the exact cap and shutdown/delete path are presented.

Until that approval:

- `provider_apply_authorized=false`;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- no live provider resource is created;
- no provider credential is accepted into a PR;
- no production DNS/public ingress is activated.

## 10. Broker/public-service separation

Production-origin selection does not imply T-Invest public connector permission. Current accepted V10 policy keeps broker-backed public functionality fail-closed until separate contractually valid permission/compliant design is accepted.

The public Web/account platform can therefore proceed while T-Invest public production features remain disabled.

## 11. Exit from service-selection gate

The technical recommendation may become accepted source authority only after:

1. current official provider/reachability review;
2. explicit production-origin/edge choice satisfying no-home and normal-user reachability;
3. data/secret/tenant isolation design;
4. recovery/rollback/capacity/cost/legal analysis;
5. deterministic regression guards;
6. exact-head DRAFT CI GREEN;
7. full diff/review with zero blocking threads;
8. fresh READY exact-head CI GREEN;
9. squash merge;
10. exact-main post-merge Regression Shield GREEN.

Even after source acceptance, **provider apply remains blocked** until PROJECT OWNER explicitly approves the current recurring cost commitment. WP23 remains locked behind the full corrected WP22A Exit Gate.
