# Omni-CIO V10 — WP22A Managed-Cloud Origin Decision

Status: **RECOMMENDED / OWNER COST APPROVAL REQUIRED BEFORE PROVIDER APPLY**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**  
Decision date: **2026-08-18**  
Accepted base `main`: `ee45026b1287c7427dc5e05b2a04b7bdb974d11f`

## 1. Decision scope

This is the WP22A Phase 1 source-only service/hosting architecture recommendation for the accepted public/free/multi-user target.

It does **not** create cloud resources, purchase a plan, add provider credentials, publish DNS, enable `PUBLIC_MULTI_USER_ENABLED`, enable T-Invest public functionality, expand broker write authority, unlock WP23 or replace protected V9.

`provider_apply_authorized=false`

A recurring paid provider commitment requires explicit PROJECT OWNER approval after exact current pricing, shutdown/delete consequences and authority are presented.

## 2. Binding product constraints

The architecture must preserve:

- ordinary Internet browser access from modern phones/desktops;
- practical reachability for the intended Russian USER population;
- no native VPN/client requirement for ordinary product use;
- no PROJECT OWNER home IP/Wi-Fi/router/LAN/Lenovo/home-power dependency;
- one source-controlled `apps/web` + `apps/api` product;
- Telegram/VK -> internal Omni-CIO account -> server-side session;
- database- and API-enforced tenant isolation;
- Russia-primary personal-data boundary pending production legal signoff;
- tenant-scoped encrypted broker/private secrets;
- PostgreSQL recovery and replacement-runtime recovery;
- source-controlled provider automation and release provenance;
- public T-Invest connector fail-closed pending its separate terms gate;
- `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and protected V9 rollback.

## 3. Personal-data localization boundary

For the intended Russian USER population, the primary identity/session/tenant data plane is Russia-region only unless a later legal review accepts a statutory exception.

The current text of Federal Law No. 152-FZ Article 18 part 5 is treated as a production localization gate. Cloud.ru Evolution states that its infrastructure is located in the Russian Federation and that the platform is attested for 152-FZ UZ-1.

Provider attestation does not replace Omni-CIO operator/security/privacy/legal obligations. Production legal signoff remains mandatory; cross-border processing remains fail-closed until separately reviewed.

Primary sources:

- `https://ips.pravo.gov.ru/` — Federal Law No. 152-FZ;
- `https://cloud.ru/docs/evolution/overview/index`;
- `https://cloud.ru/docs/evolution/overview/topics/security__compliance`.

## 4. Critical edge correction: Cloudflare is not the primary Russian USER path

Cloudflare is **not** recommended as the primary or sole production edge for normal Russian USER traffic.

Cloudflare's own 2025 incident analysis and support guidance updated on 2026-04-23 report systematic Russian-ISP throttling of Cloudflare-protected traffic and warn that Russian visitors may see connection failures or unusable sites. That conflicts with the accepted V10 ordinary-user reachability requirement.

Therefore Cloudflare **must not** be the primary or sole production edge. Cloudflare Tunnel is removed from the normal product path. Any later secondary Cloudflare role requires separate reachability, cross-border/personal-data, cost and failure-mode review. Cloudflare/GitHub/provider identity remains forbidden as Omni-CIO product identity.

Primary sources:

- `https://blog.cloudflare.com/russian-internet-users-are-unable-to-access-the-open-internet/`;
- `https://developers.cloudflare.com/support/troubleshooting/general-troubleshooting/service-disruption/`.

## 5. Recommended production topology

Pending OWNER cost approval:

```text
ordinary Internet browser
        |
        v
Cloud.ru Evolution DNS
        |
        v
Evolution L4 Network Load Balancer
public IP + health checks
recommended initial: 2 resource units
(provider minimum: 1)
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
       Business / Multi-AZ
        Primary + Standby
                  |
          +-------+-------+
          |               |
          v               v
 Secret Management   encrypted recovery
 / Key Management    / Object Storage
```

Normal inbound product traffic goes only through the reviewed public load-balancer path. The application VMs do not need independent public application listeners. Outbound Internet for Telegram/VK/provider calls and controlled updates uses a reviewed sNAT path.

## 6. Runtime, DNS, TLS and load balancing

Initial runtime recommendation: **two application VMs**, active/active behind Evolution L4 NLB.

Public DNS: Evolution DNS.

Certificate lifecycle: Evolution Certificate Manager + Let's Encrypt. TLS terminates at Nginx on the runtime VMs because the NLB is L4. Certificate/private-key delivery must use a dedicated least-privilege runtime identity; private key material must never enter GitHub, PR CI, logs or artifacts.

The current Cloud.ru Load Balancer documentation is authoritative for service behavior:

- provider minimum: **1 resource unit**;
- resource-unit count is a manual performance/fault-tolerance setting;
- this V10 recommendation deliberately starts with **2 resource units**;
- public IP supported;
- target health checks supported.

Cloud.ru's current official documentation is **internally inconsistent about Terraform management of NLB**:

- the Load Balancer limitations page says management is available through the Evolution console and Public API and says Terraform is not supported;
- the current Terraform for Evolution reference simultaneously exposes first-class `cloudru_evolution_nlb_network_load_balancer` and `cloudru_evolution_nlb_target_group` resources, including public address, rules and health-check schema.

Because both are current first-party sources, this Phase-1 decision must not pretend either statement silently wins. The production apply path therefore fails closed until a later source-controlled toolchain step pins the exact Cloud.ru Terraform provider version and proves the NLB resource path with deterministic provider-schema/config validation and a reviewed non-mutating provider plan/acceptance step. If that exact pinned provider path is proven supported, Terraform is preferred for NLB; if it is not, the reviewed Cloud.ru Public API is the fallback. **No NLB provider apply is authorized while this documentation conflict is unresolved by exact toolchain evidence.**

Primary sources:

- NLB limitations/current management: `https://cloud.ru/docs/nlb/ug/topics/overview__limitations`;
- NLB resource units: `https://cloud.ru/docs/nlb/ug/topics/concepts__service-essence-resource-unit`;
- NLB pricing: `https://cloud.ru/docs/nlb/ug/topics/pricing`;
- Terraform NLB resource: `https://cloud.ru/docs/terraform-evolution/ug/topics/reference/resources/cloudru_evolution_nlb_network_load_balancer`;
- Terraform NLB target group: `https://cloud.ru/docs/terraform-evolution/ug/topics/reference/resources/cloudru_evolution_nlb_target_group`;
- Certificate Manager: `https://cloud.ru/docs/certificate-manager/ug/index`;
- Let's Encrypt: `https://cloud.ru/docs/certificate-manager/ug/topics/tutorials__letsencrypt`;
- Evolution DNS: `https://cloud.ru/docs/dns/ug/index`.

## 7. Managed PostgreSQL

Initial database recommendation: **Business, two-node Primary/Standby, Multi-AZ, private connectivity only**.

Cloud.ru's current Managed PostgreSQL documentation distinguishes the deployment modes materially:

- **Standard** is positioned for testing and small applications and is single-AZ;
- **Business** is positioned for commercial/high-load services, places the cluster in isolated infrastructure inside the client's VPC and documents a higher-security boundary;
- Business Primary/Standby may place the two nodes in different availability zones, in which case the cluster can withstand one availability-zone failure;
- the documented Business selectable bounds begin at **4 vCPU, 8 GB RAM and 40 GB disk per node**. The docs also warn that not every possible flavor combination is necessarily available at any given time.

For a public multi-user Omni-CIO service holding tenant identity/session/private-state data, Standard is therefore **not** the initial production recommendation. The lower-cost Standard option remains suitable for non-production testing only where the owning implementation explicitly allows it.

The application and database use the same reviewed private network boundary. A public PostgreSQL endpoint is forbidden.

Provider automatic backup is useful but does not replace V10 portable/off-runtime recovery, integrity/hash verification, corrupt-backup rejection and restore rehearsal.

Primary sources:

- deployment modes and resource bounds: `https://cloud.ru/docs/paas-postgresql/ug/topics/concepts__deployment-mode`;
- Primary/Standby and Multi-AZ behavior: `https://cloud.ru/docs/paas-postgresql/ug/topics/concepts__replication`;
- quickstart mode guidance: `https://cloud.ru/docs/paas-postgresql/ug/topics/quickstart`;
- current tariffs: `https://cloud.ru/documents/tariffs/evolution/managed-postgresql`;
- pricing rules: `https://cloud.ru/docs/paas-postgresql/ug/topics/pricing`.

## 8. Secret boundary

Runtime and tenant broker secrets use Cloud.ru Secret Management, protected by Key Management or a separately reviewed provider system-key boundary.

Canonical broker ownership remains:

`USER -> Tenant -> BrokerConnection -> READ / TRADE_OPTIONAL -> verified broker account`

Frontend, Cortex, ordinary CI and unrelated tenants cannot read raw broker credentials. Product users never need Cloud.ru credentials.

## 9. Container Apps rejection

Cloud.ru Container Apps is not the selected runtime. Current Cloud.ru documentation states Container Apps does not support Managed PostgreSQL connectivity and warns that connecting to an external database over an Internet-open port is unsafe. The reviewed path is therefore VMs + private VPC + Managed PostgreSQL.

## 10. Abuse, DDoS and WAF boundary

Cloud.ru baseline infrastructure protection plus source-controlled Nginx/application controls form the initial base architecture.

Before public activation the implementation must prove at minimum:

- Nginx connection/request limits;
- Host allowlist behavior;
- HSTS/CSP/nosniff/referrer/no-store where applicable;
- server-side login/session/API rate limits;
- CSRF + exact Origin/Referer checks;
- CORS deny-by-default;
- server-side session/tenant authorization;
- malformed/oversized request rejection;
- direct backend/origin bypass denial;
- health endpoint does not expose private state or mint a session.

Managed Qrator/StormWall WAF/DDoS is **not silently included** because it materially changes recurring cost and TLS key custody. It remains a separate WP22A capacity/security decision if evidence requires it.

## 11. Candidate disposition

### Cloud.ru Evolution

**RECOMMENDED_PENDING_OWNER_COST_APPROVAL.** Best reviewed combination of Russia placement, private Managed PostgreSQL Business Multi-AZ, client-VPC isolation, native DNS/NLB/Certificate Manager, Secret Management/KMS and source-controlled Terraform/API automation. NLB automation remains explicitly fail-closed until the conflicting first-party Terraform documentation is resolved by exact pinned-provider evidence.

### Timeweb Cloud

**FALLBACK_LOWER_COST.** Russian regions, Managed PostgreSQL, private networking and Terraform/API support are attractive, but this review did not establish an equivalent general native Secret Management/KMS boundary for tenant broker credentials.

### Yandex Cloud

**SECURITY_STRONGER_HIGHER_COST_ALTERNATIVE.** Strong Russian Managed PostgreSQL + Lockbox + KMS path; retained if later availability/security requirements justify higher cost.

### Render

**REJECT_PRIMARY_PRODUCTION_DATA_PLANE** for public V10 Russian-user personal data. Current regions do not include Russia and free Web/Postgres limitations are not production-suitable. Protected V9 `app:app` is unchanged.

### Cloudflare primary edge

**REJECT_PRIMARY_OR_SOLE_RUSSIAN_USER_PRODUCTION_EDGE** based on Cloudflare's own current Russian-user disruption guidance.

## 12. Current cost boundary

Current official Cloud.ru tariffs provide a lower-bound engineering estimate, not a quote or capacity guarantee.

At 720 hours, using the documented Business minimum resource bounds as a **reference floor**:

- one `4 vCPU / 8 GB / 40 GB` Business PostgreSQL node: about **7,099.23 RUB/month**;
- Business Primary/Standby Multi-AZ, two such nodes: about **14,198.46 RUB/month**;
- two reference `1 vCPU / 2 GB / 30% CPU` application VMs with 20 GB boot disks: about **1,722.99 RUB/month**;
- sNAT: about **149.33 RUB/month**;
- **recommended two NLB resource units** + public IP: about **1,305.89 RUB/month**, before traffic charges;
- one public Evolution DNS zone for 30 days: about **32.94 RUB/month**;
- Evolution Certificate Manager: currently **0 RUB**.

Reference initial stack: about **17,409.60 RUB/month**.

The PostgreSQL estimate uses current tariff unit prices and the documented Business lower bounds; it is **not proof that an exact `4 vCPU / 8 GB / 40 GB` flavor is currently selectable**. Exact database flavor, VM flavor, zones and the complete provider cart must be revalidated immediately before purchase.

The NLB amount intentionally prices the two-unit V10 redundancy recommendation; Cloud.ru currently permits a one-unit configuration, but that cheaper single-unit option is not the initial Omni-CIO recommendation.

Excluded:

- domain registration;
- extra Object Storage;
- Internet/NLB traffic;
- monitoring beyond base/source-controlled evidence;
- managed external WAF/DDoS;
- larger VM/database flavors required by load testing;
- later scale.

OWNER must be shown the exact recurring cap and the exact resource-delete/shutdown path before provider apply.

## 13. Provider automation boundary

Current automation target:

- Terraform for Evolution resources verified by the exact pinned provider/toolchain;
- for NLB specifically, do **not** hard-code Terraform-only or Public-API-only while Cloud.ru's official service and Terraform references disagree;
- before provider apply, pin the exact Terraform provider version and prove the NLB resource schema/config with deterministic validation plus a reviewed non-mutating provider plan/acceptance step;
- use Terraform for NLB if that exact acceptance passes; otherwise use the reviewed Cloud.ru Public API fallback;
- GitHub source remains engineering source of truth for either path;
- no long-lived provider credential in source, PR logs or artifacts;
- provider apply only from an explicitly reviewed accepted-main operational boundary after OWNER recurring-cost approval.

Documentation inconsistency is treated as a deployment blocker, not permission to guess. No convenience claim such as "Terraform supports everything" or "Terraform supports nothing for NLB" may override exact pinned-toolchain evidence.

## 14. Recovery and exit

Before public activation prove:

- scheduled PostgreSQL backup plus portable/off-runtime copy;
- integrity/hash verification and corrupt-backup rejection;
- replacement-VM reconstruction from GitHub + private durable state;
- Secret Management/KMS rotation/recovery;
- certificate renewal/replacement without private-key leakage;
- tenant isolation after restore;
- rollback to last accepted release;
- protected V9 rollback until responsible cutover;
- provider exit using portable PostgreSQL data and source-controlled runtime/automation contracts.

## 15. Phase-1 exit condition

This recommendation can become accepted source authority only after exact-head DRAFT CI GREEN, full diff/review, fresh READY exact-head GREEN, squash merge, exact-main verification and post-merge Regression Shield GREEN.

Even after source acceptance, provider apply remains blocked until explicit OWNER recurring-cost approval **and** exact NLB automation-path validation resolve the current Cloud.ru documentation conflict.

Until then:

- `provider_apply_authorized=false`;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- no provider resources created;
- no production DNS/public ingress activated;
- no provider credential accepted into PR source/logs/artifacts;
- WP23 remains locked;
- broker write/Real execution remain disabled.
