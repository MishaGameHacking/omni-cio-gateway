# Omni-CIO V10 — WP22A Managed-Cloud Origin Decision

Status: **RECOMMENDED / OWNER COST APPROVAL REQUIRED BEFORE PROVIDER APPLY**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**  
Decision date: **2026-08-18**  
Accepted base `main`: `ee45026b1287c7427dc5e05b2a04b7bdb974d11f`

## 1. Decision scope

This is the WP22A Phase-1 source-only hosting/service recommendation for the accepted public/free/multi-user target. It does **not** create cloud resources, purchase a plan, add provider credentials, publish DNS, enable `PUBLIC_MULTI_USER_ENABLED`, enable T-Invest public functionality, expand broker write authority, unlock WP23 or replace protected V9.

`provider_apply_authorized=false`

A recurring provider commitment requires explicit PROJECT OWNER approval after exact current pricing, capacity/flavor availability and shutdown/delete consequences are presented.

## 2. Binding product constraints

Preserve ordinary Internet browser access, practical Russian USER reachability, no native VPN/client requirement, no OWNER home/Lenovo availability dependency, one source-controlled Web/Core, Telegram/VK product authentication mapped to internal accounts, server-side sessions, structural tenant isolation, Russia-primary personal-data handling pending legal signoff, tenant-scoped encrypted secrets/private state, recovery/rollback and `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false`.

## 3. Personal-data localization boundary

For the intended Russian USER population, primary identity/session/tenant data stays in a Russia-region data plane unless a later legal review accepts a statutory exception. Cloud.ru Evolution states its infrastructure is in Russia and describes 152-FZ UZ-1 compliance. Provider claims do not replace Omni-CIO operator/security/privacy/legal obligations; production legal signoff remains mandatory and cross-border processing stays fail-closed pending review.

## 4. Primary edge decision

Cloudflare is **not** the primary or sole production edge for normal Russian USER traffic. Current Cloudflare first-party incident/support guidance reports systematic Russian-ISP throttling that can make Cloudflare-protected sites unavailable or unusable for Russian visitors. This conflicts with the accepted ordinary-Russian-user browser requirement.

Therefore Cloudflare Tunnel/proxied traffic is removed from the normal production path. Any future secondary Cloudflare role requires a separate reachability, cross-border/personal-data, cost and failure-mode review. Cloudflare/GitHub/provider identity is never Omni-CIO product identity.

## 5. Recommended production topology

Pending OWNER cost approval:

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

The application VMs must be placed in different availability zones. The NLB uses two selected zones with one resource unit in each, giving two total resource units in the initial reference topology. The database uses the provider-recommended production topology: Business Cluster HA with three nodes spread across three zones.

## 6. Runtime, DNS, TLS and load balancing

Cloud.ru documents three VM availability zones and recommends placing application VMs in different zones to increase application fault tolerance. Evolution DNS is the public DNS boundary. Certificate lifecycle uses Evolution Certificate Manager + Let's Encrypt; TLS terminates at Nginx on the application VMs because the NLB is L4. Certificate/private-key delivery requires least privilege and must never leak into GitHub, CI logs or artifacts.

Cloud.ru's NLB quickstart creates a georedundant balancer across availability zones. Resource-unit count and cross-zone placement determine NLB performance/fault tolerance. The initial Omni-CIO reference therefore uses **2 AZ x 1 resource unit/AZ = 2 total units** with health checks.

### NLB Terraform documentation conflict

Current Cloud.ru first-party docs conflict:

- NLB service limitations say management is through console/Public API and Terraform is unsupported;
- the current Terraform for Evolution reference exposes first-class NLB and target-group resources.

No source is silently ignored. Before provider apply, source-controlled tooling must pin the exact Cloud.ru Terraform provider and prove the NLB schema/configuration with deterministic validation plus a reviewed non-mutating plan/acceptance step. Terraform is preferred if that exact path passes; otherwise reviewed Public API is the fallback. **Provider apply remains blocked until this is resolved by exact toolchain evidence.**

## 7. Managed PostgreSQL

Initial production database recommendation: **Business Cluster HA, three nodes (`Primary + 2 Standby`), Multi-AZ across three availability zones, private connectivity only**.

Cloud.ru currently documents:

- Standard for testing/small applications;
- Business for commercial/high-load services, inside isolated client-VPC infrastructure with a higher-security boundary;
- Business lower resource bounds of 4 vCPU, 8 GB RAM and 40 GB disk per node, while warning not every theoretical flavor combination is necessarily currently available;
- three-node multi-zone Cluster HA as the **recommended production topology**, using synchronous quorum replication and continuing operation after one availability zone fails.

Accordingly, neither Standard nor two-node Primary/Standby is the initial public-production database baseline. A public PostgreSQL endpoint is forbidden.

Provider automatic backups do not replace V10 portable/off-runtime encrypted recovery, hash/integrity verification, corrupt-backup rejection and restore rehearsal.

## 8. Secret boundary

Runtime and tenant broker secrets use Cloud.ru Secret Management protected by Key Management or a separately reviewed provider system-key boundary.

Canonical ownership remains:

`USER -> Tenant -> BrokerConnection -> READ / TRADE_OPTIONAL -> verified broker account`

Frontend, Cortex, ordinary CI and unrelated tenants cannot receive raw broker credentials.

## 9. Container Apps rejection

Cloud.ru Container Apps remains rejected as primary runtime because current provider documentation does not support the required private Managed PostgreSQL integration and warns against the Internet-open external-database workaround. The reviewed path remains VMs + private VPC/subnets + Managed PostgreSQL.

## 10. Abuse, DDoS and WAF boundary

Cloud.ru baseline infrastructure protection plus source-controlled Nginx/application controls form the initial base. Before public activation prove request/connection limits, Host allowlist, HSTS/CSP/nosniff/referrer/no-store as applicable, server-side rate limits, CSRF + exact Origin/Referer validation, deny-by-default CORS, session/tenant authorization, malformed/oversized request rejection, direct-origin bypass denial and non-sensitive health behavior.

Managed external WAF/DDoS is not silently added because it changes recurring cost and TLS key custody; it requires a separate explicit WP22A capacity/security decision if evidence demands it.

## 11. Candidate disposition

- **Cloud.ru Evolution — RECOMMENDED_PENDING_OWNER_COST_APPROVAL.** Russia placement, cross-AZ VM/NLB topology, Business Cluster HA Multi-AZ PostgreSQL, client-VPC isolation, DNS/certificate services, Secret Management/KMS and source-controlled Terraform/API automation.
- **Timeweb Cloud — FALLBACK_LOWER_COST.** Useful Russian/private-network/Managed-PostgreSQL/Terraform/API properties, but this review did not establish an equivalent general native Secret Management/KMS boundary for tenant broker credentials.
- **Yandex Cloud — SECURITY_STRONGER_HIGHER_COST_ALTERNATIVE.** Strong Russia-region Managed PostgreSQL + Lockbox/KMS path.
- **Render — REJECT_PRIMARY_PRODUCTION_DATA_PLANE.** Not selected for the Russian-user primary personal-data plane; protected V9 `app:app` is unchanged.
- **Cloudflare primary edge — REJECT_PRIMARY_OR_SOLE_RUSSIAN_USER_PRODUCTION_EDGE.** Russian-user reachability conflict.

## 12. Current cost boundary

Using current Cloud.ru tariff unit prices and documented Business lower resource bounds only as a reference floor at 720 hours:

- one reference Business PostgreSQL node (`4 vCPU / 8 GB / 40 GB`): **~7,099.23 RUB/month**;
- three-node Business Cluster HA Multi-AZ: **~21,297.69 RUB/month**;
- two reference application VMs + 20 GB boot disks: **~1,722.99 RUB/month**;
- sNAT: **~149.33 RUB/month**;
- NLB `2 AZ x 1 resource unit/AZ` + public IP: **~1,305.89 RUB/month**, before traffic;
- one Evolution DNS zone: **~32.94 RUB/month**;
- Certificate Manager: **0 RUB** currently.

Reference initial stack: **~24,508.83 RUB/month**.

This is an engineering lower-bound estimate, not a quote or capacity guarantee. Exact selectable database/VM flavors, zones, NLB shape and the full provider cart must be revalidated immediately before purchase. Excluded are domain registration, extra Object Storage, Internet/NLB traffic, additional monitoring, managed external WAF/DDoS, larger flavors required by load testing and later scale.

## 13. Provider automation boundary

Terraform is used for Evolution resources proven by the exact pinned provider/toolchain. NLB remains fail-closed until the documentation conflict is resolved by exact pinned-provider validation. GitHub source remains engineering authority; no long-lived provider credential belongs in source/PR logs/artifacts. Provider apply is allowed only from a separately reviewed accepted-main operations boundary after OWNER recurring-cost approval.

## 14. Recovery and exit

Before public activation prove scheduled PostgreSQL backup plus portable off-runtime copy, integrity/hash verification, corrupt-backup rejection, replacement-runtime reconstruction, Secret Management/KMS rotation/recovery, certificate renewal/replacement without key leakage, tenant isolation after restore, rollback to last accepted release, protected V9 rollback and provider exit using portable PostgreSQL data plus source-controlled runtime/automation contracts.

## 15. Phase-1 exit condition

This recommendation becomes accepted source authority only after exact-head DRAFT CI GREEN, full diff/review, fresh READY exact-head GREEN, squash merge, exact-main verification and post-merge Regression Shield GREEN.

Even after source acceptance, provider apply remains blocked until explicit OWNER recurring-cost approval and exact NLB automation-path validation.

Until then:

- `provider_apply_authorized=false`;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- no provider resources created;
- no production DNS/public ingress activated;
- no provider credential accepted into PR source/logs/artifacts;
- WP23 remains locked;
- broker write/Real execution remain disabled.
