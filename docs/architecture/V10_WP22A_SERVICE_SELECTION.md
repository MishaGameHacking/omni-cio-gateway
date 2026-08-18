# Omni-CIO V10 — WP22A Service Selection Gate

Status: **MANAGED-CLOUD ORIGIN RECOMMENDED / OWNER COST APPROVAL REQUIRED / NO PROVIDER APPLY AUTHORIZED**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**

## 1. Authority transition

The earlier Phase-A design optimized browser-only PROJECT OWNER access to the Lenovo Personal Node through Cloudflare Access + Tunnel. It remains historical/pre-production evidence only. The accepted public-hosted target requires a normal public Web service independent of OWNER home infrastructure and practically reachable from ordinary Russian networks.

Current machine/human decision authority is:

- `V10_WP22A_MANAGED_CLOUD_ORIGIN_CONTRACT.json`;
- `V10_WP22A_MANAGED_CLOUD_ORIGIN_DECISION.md`.

Historical lifecycle marker for regression provenance only: `Production-origin provider selection is not yet made`. That statement described the reopened gate before the current recommendation and is superseded as current authority.

No provider mutation is authorized by this recommendation.

## 2. Required final outcome

The architecture must preserve:

- ordinary browser access from modern phones/desktops;
- reliable normal Russian USER reachability;
- public HTTPS with reviewed certificate lifecycle;
- no VPN/native-client requirement for ordinary product use;
- no OWNER home IP/Wi-Fi/router/LAN/Lenovo availability dependency;
- one source-controlled Web App/Core;
- Telegram/VK -> internal Omni-CIO account -> server-side session;
- API + database-enforced tenant isolation;
- tenant-scoped encrypted secrets/private state;
- backup/recovery/replacement-runtime capability;
- GitHub-controlled deployment/release provenance;
- measured capacity/abuse controls;
- privacy/personal-data/legal and broker-term gates;
- `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and protected V9 rollback.

## 3. Recommended production boundary

Pending OWNER recurring-cost approval:

```text
ordinary Internet browser
        |
        v
Cloud.ru Evolution DNS
        |
        v
Evolution L4 NLB
2 AZ / 1 resource unit per AZ
public IP + health checks
        |
        +-------------------+
        |                   |
        v                   v
Evolution VM A         Evolution VM B
AZ-A / Nginx TLS       AZ-B / Nginx TLS
        |                   |
        +---------+---------+
                  |
                  v
       private VPC/subnets
                  |
                  v
       Managed PostgreSQL
 Business Cluster HA / Multi-AZ
  Primary + 2 Standby / 3 AZ
                  |
          +-------+-------+
          |               |
          v               v
 Secret Management   encrypted recovery
 / Key Management    / Object Storage
```

Binding properties:

- provider/runtime: Cloud.ru Evolution, Russia;
- runtime: two application VMs, **one per different availability zone**;
- NLB: **two selected availability zones, one resource unit in each**; two total units are the current V10 georedundant reference configuration;
- DNS: Evolution DNS;
- TLS: Evolution Certificate Manager + Let's Encrypt; Nginx terminates TLS on runtime VMs behind L4 NLB;
- database: private Managed PostgreSQL **Business Cluster HA**, three nodes (`Primary + 2 Standby`) in **three different availability zones**;
- Standard and two-node Primary/Standby are not the initial public-production database baseline;
- public PostgreSQL endpoint: forbidden;
- secrets: Secret Management + Key Management or separately reviewed system-key boundary;
- outbound: reviewed sNAT;
- provider automation: exact pinned Terraform provider where proven, Public API fallback where exact Terraform support is not accepted;
- public T-Invest connector: independently fail-closed.

Cloud.ru documents Standard for testing/small applications and Business for commercial/high-load services with stronger client-VPC isolation. Its current Managed PostgreSQL reliability guide explicitly recommends the **three-node multi-zone Cluster HA** topology for production; it retains quorum after one zone fails. Cloud.ru also exposes three VM availability zones and recommends placing application VMs in different zones for higher availability. The NLB quickstart builds a georedundant balancer across availability zones, and resource-unit placement across zones determines fault tolerance.

Cloud.ru currently permits one NLB resource unit in each selected zone. The V10 reference therefore uses **2 AZ x 1 unit/AZ = 2 total resource units**, rather than two units in one zone.

## 4. NLB automation documentation conflict — fail closed

Current first-party Cloud.ru docs conflict:

- the NLB limitations page says management is via Evolution console/Public API and Terraform is unsupported;
- the current Terraform for Evolution reference exposes `cloudru_evolution_nlb_network_load_balancer` and `cloudru_evolution_nlb_target_group` resources.

Before provider apply, source-controlled tooling must pin the exact Cloud.ru Terraform provider and prove the NLB schema/config through deterministic validation plus a reviewed non-mutating provider plan/acceptance step. If that exact path passes, Terraform is preferred; otherwise reviewed Public API is the fallback. Documentation inconsistency is a blocker, not permission to guess.

Cloud.ru Container Apps remains rejected as the primary runtime because current provider documentation does not support the required private Managed PostgreSQL path without an unsafe Internet-open database workaround.

## 5. Cloudflare primary edge rejected for normal Russian USER traffic

Cloudflare remains historical engineering knowledge but must not be the primary or sole Russian-user production edge. Current Cloudflare first-party incident/support guidance reports systematic Russian-ISP throttling that can make Cloudflare-protected sites unavailable or unusable to Russian visitors.

Therefore Cloudflare Tunnel/proxied HTTP is removed from the normal public-product path. Any later secondary role requires separate reachability, cross-border/personal-data, cost and failure-mode review. Cloudflare/GitHub/provider identity remains forbidden as product identity.

## 6. Reusable Phase-A controls

Reuse where semantically valid:

- Host allowlist;
- explicit trusted proxy/protocol boundary;
- Secure/HttpOnly/SameSite server-side session cookies;
- bounded session lifetime, rotation, logout/revoke;
- CSRF + exact Origin/Referer validation;
- CORS deny-by-default;
- bounded login/mutation rate limits;
- HSTS/CSP/nosniff/restrictive referrer/no-store where applicable;
- direct-origin/API negative tests;
- fail-closed rollback;
- provider secrets excluded from PR CI;
- exact-head CI + post-merge Regression Shield.

Old final-product assumptions are not reusable: Cloudflare membership as product identity, exact OWNER fingerprint session bootstrap, Lenovo loopback as production origin, OWNER-only product access, or permanent public-multi-user disablement.

### 6.1 Historical Phase-A TLS markers — regression provenance only

The accepted dormant Phase-A source used these Cloudflare-specific markers:

- `Universal SSL`;
- `active Cloudflare full-DNS zone`;
- `first-level subdomain`;
- `Cloudflare owns edge-certificate issuance, renewal and deployment`;
- `X-Forwarded-Proto`.

They are historical regression markers, not current production requirements.

## 7. DDoS/WAF and abuse boundary

Cloud.ru baseline infrastructure protection plus source-controlled Nginx/application controls are the initial base. Before public activation prove connection/request limits, Host, security headers, CSRF, Origin/Referer, CORS, session/tenant authorization, malformed/oversized request rejection and direct-origin bypass denial.

Managed Qrator/StormWall WAF/DDoS is not silently included because it changes recurring cost and TLS private-key custody; if load/abuse evidence requires it, that is a separate explicit WP22A cost/security decision.

## 8. Candidate disposition

- **Cloud.ru Evolution — RECOMMENDED_PENDING_OWNER_COST_APPROVAL.** Best reviewed combination of Russian placement, cross-AZ VMs/NLB, Business Cluster HA Multi-AZ PostgreSQL, Secret Management/KMS, DNS/certificate services and source-controlled Terraform/API automation.
- **Timeweb Cloud — FALLBACK_LOWER_COST.** Russian regions/private networking/Managed PostgreSQL/API/Terraform are useful, but this review did not establish an equivalent general native Secret Management/KMS boundary for tenant broker credentials.
- **Yandex Cloud — SECURITY_STRONGER_HIGHER_COST_ALTERNATIVE.** Strong Russian Managed PostgreSQL + Lockbox/KMS alternative.
- **Render — REJECT_PRIMARY_PRODUCTION_DATA_PLANE.** Not suitable as the new Russian-user primary personal-data plane; protected V9 `app:app` remains untouched.
- **Cloudflare primary edge — REJECT_PRIMARY_OR_SOLE_RUSSIAN_USER_PRODUCTION_EDGE.** Russian-user reachability conflict.

## 9. Cost boundary

Current Cloud.ru tariffs give a lower-bound engineering estimate, not a purchase quote. At 720 hours, using the documented Business resource lower bounds only as a reference floor:

- one reference Business PostgreSQL node (`4 vCPU / 8 GB / 40 GB`): about **7,099.23 RUB/month**;
- three-node Business Cluster HA Multi-AZ: about **21,297.69 RUB/month**;
- two reference application VMs with 20 GB boot disks: about **1,722.99 RUB/month**;
- sNAT: about **149.33 RUB/month**;
- NLB **2 AZ x 1 resource unit/AZ** + public IP: about **1,305.89 RUB/month**, before traffic;
- one public Evolution DNS zone for 30 days: about **32.94 RUB/month**;
- Evolution Certificate Manager: currently free.

Reference initial stack: about **24,508.83 RUB/month**.

The database figure does not prove an exact `4 vCPU / 8 GB / 40 GB` flavor is currently selectable; Cloud.ru states that not every possible flavor combination is necessarily available. Exact database/VM flavors, availability zones, NLB shape and the complete cart must be revalidated before purchase.

Excluded: domain registration, extra Object Storage, traffic, monitoring beyond base evidence, managed external WAF/DDoS, larger flavors required by load testing and later scale.

A new recurring paid commitment requires explicit OWNER approval after the exact cap and shutdown/delete path are presented.

Until that approval and exact NLB automation validation:

- `provider_apply_authorized=false`;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- no live provider resource is created;
- no provider credential is accepted into a PR;
- no production DNS/public ingress is activated.

## 10. Broker/public-service separation

Production-origin selection does not imply T-Invest public connector permission. Public Web/account work can proceed while broker-backed public production remains fail-closed pending contractually valid permission/compliant design.

## 11. Exit from service-selection gate

Technical source acceptance requires:

1. current official provider/reachability review;
2. explicit production-origin/edge choice satisfying no-home and ordinary-user reachability;
3. data/secret/tenant isolation design;
4. recovery/rollback/capacity/cost/legal analysis;
5. deterministic regression guards;
6. exact-head DRAFT CI GREEN;
7. full diff/review with zero blocking threads;
8. fresh READY exact-head CI GREEN;
9. squash merge;
10. exact-main post-merge Regression Shield GREEN.

Even after source acceptance, provider apply remains blocked until PROJECT OWNER explicitly approves the current recurring-cost commitment and exact pinned-toolchain evidence accepts the NLB automation path. WP23 remains locked behind the full corrected WP22A Exit Gate.
