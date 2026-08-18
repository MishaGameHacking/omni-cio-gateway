# Omni-CIO V10 — WP22A Managed-Cloud Origin Decision

Status: **RECOMMENDED / OWNER COST APPROVAL REQUIRED BEFORE PROVIDER APPLY**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**  
Decision date: **2026-08-18**  
Accepted base `main`: `ee45026b1287c7427dc5e05b2a04b7bdb974d11f`

## 1. Decision scope

This document performs WP22A Phase 1 service/hosting architecture selection against the accepted public/free/multi-user target.

It is source-only architecture authority. It does **not** create cloud resources, buy a provider plan, add provider credentials, publish DNS, enable public multi-user mode, enable T-Invest public functionality, expand broker write authority, unlock WP23 or replace protected V9.

A new recurring paid provider commitment still requires PROJECT OWNER approval after exact current price and authority consequences are presented. Until that approval, the recommendation below is intentionally `RECOMMENDED_PENDING_OWNER_COST_APPROVAL`, not a live provider selection/apply authorization.

## 2. Binding product constraints

The selected architecture must preserve all accepted requirements:

- ordinary USER access from a normal Internet-connected browser/phone/desktop;
- reliable normal access for the intended Russian USER population;
- no native VPN/device client for ordinary USER access;
- no PROJECT OWNER home IP/Wi-Fi/router/LAN/Lenovo/home-power dependency for public availability;
- one existing source-controlled `apps/web` + `apps/api` product, not a second site or stack;
- Telegram/VK product authentication -> `OmniCIOUserAccount -> Tenant -> Session`;
- server-side tenant authority and database-enforced isolation;
- Russian personal-data/legal gate before production activation;
- tenant-scoped encrypted broker/private secret boundary;
- PostgreSQL durability, backup/restore and replacement-runtime recovery;
- GitHub-controlled release/IaC provenance;
- no public T-Invest connector until its separate broker-terms gate passes;
- `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and V9 rollback remain protected.

## 3. Personal-data localization constraint

For the intended Russian USER population, the primary product identity/session/tenant data plane must be located in Russia unless a later legal review identifies and accepts a statutory exception.

The current official text of Federal Law No. 152-FZ, Article 18 part 5, prohibits collection of Russian citizens' personal data using databases located outside the Russian Federation except for the listed statutory exceptions.

Engineering consequence for WP22A:

- the primary identity/session/tenant PostgreSQL database is Russia-region only;
- an overseas-only PaaS must not become the primary Russian personal-data data plane;
- any future cross-border processing remains separately legally reviewed and fail-closed;
- this architecture decision is not legal advice and does not replace the required production legal signoff.

Cloud.ru's current Evolution documentation states that all Evolution infrastructure is located in the Russian Federation and that the platform is attested for 152-FZ protection level UZ-1. This is a provider-infrastructure property, not a transfer of Omni-CIO's own operator/security/legal responsibilities to the provider.

Official sources:

- Federal Law No. 152-FZ, Article 18 part 5: `https://ips.pravo.gov.ru/api/ips/legislation/document`;
- Cloud.ru Evolution overview: `https://cloud.ru/docs/evolution/overview/index`;
- Cloud.ru Evolution compliance: `https://cloud.ru/docs/evolution/overview/topics/security__compliance`.

## 4. Critical edge correction: Cloudflare is not the primary Russian USER path

The first provider draft reused Cloudflare as the normal public edge. Current external verification found this to be incompatible with the product's Russian-user reachability requirement.

Cloudflare's own June 2025 incident analysis says Russian ISPs began systematically throttling traffic to sites protected by Cloudflare, in some cases limiting connections to approximately 16 KB. Cloudflare's support documentation updated in April 2026 still warns that Russian visitors may experience connection failures or unusable sites and that Cloudflare cannot restore that connectivity because the disruption is applied by Russian ISPs.

Therefore:

- Cloudflare **must not** be the primary or sole production edge for normal Russian USER traffic;
- Cloudflare Tunnel is removed from the recommended normal product path;
- Cloudflare may only be reconsidered later as an optional secondary/non-primary path after separate reachability, personal-data/cross-border, cost and failure-mode review;
- Cloudflare/GitHub/provider identity remains forbidden as product authentication regardless of transport role.

Official Cloudflare sources:

- Russia throttling analysis: `https://blog.cloudflare.com/russian-internet-users-are-unable-to-access-the-open-internet/`;
- support notice, updated 2026-04-23: `https://developers.cloudflare.com/support/troubleshooting/general-troubleshooting/service-disruption/`.

This correction is exactly why WP22A requires current service-selection evidence instead of carrying an old edge assumption forward by inertia.

## 5. Recommended production architecture

### 5.1 Cloud.ru Evolution — recommended pending cost approval

**Recommended topology:**

```text
ordinary Internet browser
        |
        v
Cloud.ru Evolution DNS
        |
        v
Cloud.ru Evolution L4 Network Load Balancer
public IP + health checks
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
        Cloud.ru Managed PostgreSQL
          Primary + Standby
                  |
          +-------+-------+
          |               |
          v               v
Secret Management   encrypted recovery
/ Key Management    / Object Storage
```

The runtime recommendation is **two active application VMs behind Evolution Load Balancer**, not one application VM. This bounds ordinary VM/process failure without requiring the PROJECT OWNER home node.

The application VMs remain in the same project/private subnet required for internal Managed PostgreSQL connectivity. Outbound Internet required for Telegram/VK authorization flows, controlled dependency/provider calls and operational updates uses a reviewed Evolution sNAT path; normal inbound product traffic enters through the public load balancer.

### 5.2 TLS and DNS

- authoritative public DNS: **Evolution DNS**;
- certificate lifecycle: **Evolution Certificate Manager + Let's Encrypt**;
- Certificate Manager is currently free in Evolution and supports automatic Let's Encrypt issuance/reissue for domains delegated and verified in Evolution DNS;
- its API/access roles allow retrieval of the certificate/private key, so runtime delivery must use a dedicated least-privilege service identity and never put certificate private keys into GitHub, CI output or artifacts;
- TLS terminates at Nginx on the runtime VMs because Evolution Load Balancer is an L4 service.

Certificate retrieval/distribution and zero-downtime renewal must be implemented and tested in a later source-controlled WP22A runtime phase before public activation.

Official sources:

- Evolution DNS public-zone Terraform resource: `https://cloud.ru/docs/terraform-evolution/ug/topics/reference/resources/cloudru_evolution_dns_public_zone`;
- Evolution DNS current tariff: `https://cloud.ru/documents/tariffs/evolution/evolution-dns`;
- Certificate Manager overview: `https://cloud.ru/docs/certificate-manager/ug/index`;
- Let's Encrypt issuance: `https://cloud.ru/docs/certificate-manager/ug/topics/guides_certificate_create`;
- Certificate Manager access roles: `https://cloud.ru/docs/certificate-manager/ug/topics/access`;
- Certificate Manager pricing: `https://cloud.ru/docs/certificate-manager/ug/topics/pricing`.

### 5.3 Load balancing and runtime failure boundary

Evolution Load Balancer supports:

- a public external IP;
- multiple VM targets;
- TCP or HTTP health checks;
- automatic removal of failed targets from traffic;
- Terraform provisioning.

Initial recommendation:

- two small application VMs in the reviewed private subnet;
- one public L4 NLB target group;
- HTTPS listener routed to Nginx on both VMs;
- an HTTP health endpoint that does not expose private product data and does not mint a session;
- VMs have no independent public application listener reachable outside the reviewed load-balancer path.

Official sources:

- NLB service description: `https://cloud.ru/documents/contracts/terms-of-service/evolution/load-balancer/description-load-balancer`;
- NLB Terraform resource: `https://cloud.ru/docs/terraform-evolution/ug/topics/reference/resources/cloudru_evolution_nlb_network_load_balancer`;
- NLB target group: `https://cloud.ru/docs/terraform-evolution/ug/topics/reference/resources/cloudru_evolution_nlb_target_group`;
- current NLB tariff: `https://cloud.ru/documents/tariffs/evolution/load-balancer`.

### 5.4 Managed PostgreSQL topology

The initial production recommendation is **Standard mode, two-node Primary/Standby**, not a single-node database.

Reasons:

- the accepted V10 target is a real public service, so one database node should not silently become the only durable-state availability boundary;
- Cloud.ru Standard supports small resource sizes and Primary/Standby two-node topology;
- Managed PostgreSQL is reachable only through an internal IP from Evolution VMs in the same project/subnet;
- the Standard topology remains single-AZ, so it is **not** equivalent to Business Multi-AZ and must not be described as zone-level high availability;
- later capacity/availability evidence may require migration through backup/restore to Business Multi-AZ.

Official sources:

- private Managed PostgreSQL connection rule: `https://cloud.ru/docs/paas-postgresql/ug/topics/guides__databases__connecting-to-database`;
- deployment modes: `https://cloud.ru/docs/paas-postgresql/ug/topics/concepts__deployment-mode`;
- Terraform Primary/Standby resource: `https://cloud.ru/docs/terraform-evolution/ug/topics/reference/resources/cloudru_evolution_postgresql_cluster`;
- Managed PostgreSQL current tariff: `https://cloud.ru/documents/tariffs/evolution/managed-postgresql`;
- backup policy: `https://cloud.ru/docs/paas-postgresql/ug/topics/guides__backups__backup-policy`.

### 5.5 Secret boundary

Tenant/runtime secrets remain in **Cloud.ru Secret Management**, optionally protected by a dedicated Key Management key; if no KMS key is selected, Cloud.ru documents encryption using its system key.

Broker READ/optional TRADE credentials remain tenant-owned application secrets. Product users never need Cloud.ru credentials. Frontend, Cortex, ordinary CI and unrelated tenants must not receive raw secret values.

Official sources:

- Secret Management overview: `https://cloud.ru/docs/scsm/ug/index`;
- create secret / KMS or system-key encryption: `https://cloud.ru/docs/scsm/ug/topics/guides__add-secret`;
- Secret Management pricing: `https://cloud.ru/docs/scsm/ug/topics/pricing`.

### 5.6 Container Apps remains rejected

Cloud.ru Container Apps is explicitly rejected as the primary runtime. Cloud.ru's own FAQ says Container Apps does not support Managed PostgreSQL connectivity and that connecting to an external database through an Internet-open port is not a safe scenario. The secure reviewed topology therefore uses VMs + private VPC + Managed PostgreSQL.

Official source: `https://cloud.ru/docs/container-apps-evolution/ug/topics/faq__database-connection`.

## 6. Edge abuse / DDoS / WAF boundary

Cloud.ru documents baseline infrastructure protection, including channel-capacity DDoS protection and perimeter segmentation. That is useful infrastructure defense but is **not** treated as a substitute for application-level security controls.

Initial source-controlled public path must additionally prove:

- Nginx connection/request limits;
- exact Host handling;
- HSTS/CSP/nosniff/referrer/no-store policy where appropriate;
- application login/session/API rate limits;
- CSRF + exact Origin/Referer checks;
- CORS deny-by-default;
- strict server-side session/tenant authorization;
- malformed/oversized request rejection;
- negative tests for direct backend/origin bypass and health endpoint disclosure.

A separate managed WAF/DDoS reverse-proxy product is **not included in the base cost recommendation**. Cloud.ru offers Qrator and StormWall services, but current WAF options add material cost and may require TLS certificate/private-key custody by the protection service. That is a separate cost, privacy and key-custody decision and must not be silently activated inside this provider-selection PR.

If load/abuse evidence later shows the native + application controls are insufficient, the WP22A capacity/security gate must compare and explicitly approve a managed WAF/DDoS service before public scale.

Official sources:

- Evolution infrastructure protection: `https://cloud.ru/docs/evolution/overview/topics/security__infrastructure-protection`;
- Cloud.ru Anti-DDoS/WAF architecture guidance: `https://cloud.ru/docs/architecture-center/topics/recommendations/recommendations__security__traffic_redirection`;
- Qrator current tariff: `https://cloud.ru/documents/tariffs/crs/qrator`;
- StormWall service description: `https://cloud.ru/documents/contracts/terms-of-service/crs/ddos-protection/description-ddos-protection`.

## 7. Candidate comparison

### 7.1 Cloud.ru Evolution — recommended pending cost approval

Why it currently ranks first:

1. Russian infrastructure + current 152-FZ UZ-1 platform attestation.
2. Private VM-to-Managed-PostgreSQL path.
3. Primary/Standby Managed PostgreSQL.
4. Evolution DNS, NLB and Certificate Manager form a Russia-reachable native publication path.
5. Secret Management + Key Management/system-key boundary.
6. Broad Terraform resource coverage for VPC, VMs, NLB, DNS, PostgreSQL and IAM.
7. Pay-as-you-go billing and cost-control tooling.

Known tradeoffs:

- VM OS/runtime patching remains our responsibility;
- Standard PostgreSQL Primary/Standby is single-AZ;
- a fully managed external WAF/DDoS service is not in the base budget;
- exact VM capacity must be validated by load testing before public activation.

### 7.2 Timeweb Cloud — lower-cost fallback

Timeweb remains a viable fallback because it offers Russian regions, Managed PostgreSQL, private networking, backups and Terraform/API automation. It does not rank first because the reviewed selection did not establish an equivalent general native Secret Management/KMS boundary for tenant broker credentials. If Cloud.ru cost approval is rejected, Timeweb is the first fallback and the broker-secret/public-connector gate remains fail-closed until an acceptable vault/key boundary is proven.

### 7.3 Yandex Cloud — strong security, higher-cost alternative

Yandex Cloud remains a technically strong Russia-region alternative with Managed PostgreSQL, Lockbox and KMS. It ranks below Cloud.ru for this initial free launch because the reviewed production-grade managed database path is materially more expensive.

### 7.4 Render — rejected as primary production data plane

Render remains useful historical V9 infrastructure, but it is not eligible as the final primary public V10 personal-data plane for the intended Russian USER population: current Render regions do not include Russia; free Web services spin down after 15 minutes idle; free Render Postgres expires after 30 days and Render says free instances should not be used for production applications.

Protected V9 `app:app` remains untouched.

### 7.5 Cloudflare primary edge — rejected

Cloudflare remains useful engineering knowledge and may later have a bounded secondary role, but its own 2025/2026 documentation establishes that it is not a reliable sole production path for Russian users. It is therefore rejected as the primary/sole product edge in this decision.

## 8. Current cost boundary

Current official Cloud.ru references provide a lower-bound engineering estimate.

Managed PostgreSQL at 720 hours:

- one `1 vCPU / 2 GB RAM / 20 GB SSD` node: about **1,896.03 RUB/month**;
- two-node Primary/Standby: about **3,792.05 RUB/month**.

Reference VM pricing:

- `1 vCPU / 2 GB RAM / 30% CPU`: about **636.85 RUB/month**;
- 20 GB boot disk: about **224.64 RUB/month**;
- two such runtime VMs with 20 GB boot disks: about **1,722.99 RUB/month**.

Network/publication reference:

- sNAT: about **149.33 RUB/month**;
- one NLB resource unit + NLB public IP: about **727.61 RUB/month**, before traffic charges;
- one public Evolution DNS zone for 30 days: about **32.94 RUB/month**, with the documented monthly request free quota still applying;
- Evolution Certificate Manager: **0 RUB** at the current published service price.

Reference minimum initial stack:

**about 6,424.92 RUB/month**.

This is **not a purchase quote and not a capacity guarantee**. It excludes:

- custom domain registration;
- extra Object Storage beyond any applicable free allowance;
- Internet/NLB traffic charges;
- monitoring products beyond source-controlled/basic metrics;
- managed external WAF/DDoS service;
- larger VM flavors or later scale;
- Business Multi-AZ PostgreSQL.

The exact selected VM flavor and complete provider cart must be revalidated immediately before purchase.

Before provider apply, PROJECT OWNER must receive and approve:

- exact VM flavor/count and monthly estimate;
- exact PostgreSQL topology and monthly estimate;
- NLB/public-IP/sNAT/DNS/storage/backup costs;
- custom-domain cost if a new domain is required;
- expected all-in initial monthly cap;
- whether the cost is recurring/pay-as-you-go and exactly how resources can be stopped/deleted to end billing.

No paid provider resource is authorized before that approval.

## 9. Recovery and exit strategy

The provider selection is valid only if later source work proves:

- PostgreSQL backup + integrity verification + corrupt-backup rejection;
- provider automatic backup policy plus a separately portable/off-runtime recovery copy where required;
- encrypted off-runtime backup/recovery;
- replacement VM/runtime reconstruction from GitHub plus private durable state;
- Secret Management/KMS rotation/recovery without putting secrets in GitHub;
- TLS certificate renewal/replacement without GitHub/private-key leakage;
- tenant isolation preserved after restore;
- rollback to the last accepted V10 release;
- protected V9 rollback remains available until responsible cutover;
- provider exit is possible using portable PostgreSQL backups, source-controlled runtime/IaC and non-provider-exclusive application contracts.

Cloud.ru's current Managed PostgreSQL backup policy supports scheduled backups and retention up to 30 days; native provider backup alone does not replace V10's independently recoverable durable-state and corrupt-backup requirements.

## 10. Phase-1 exit condition

This recommendation is not yet the final Phase-1 PASS because a recurring paid provider choice cannot be committed on behalf of PROJECT OWNER.

Phase 1 can proceed autonomously through source-controlled architecture, tests and CI. The first legitimate OWNER blocker is **cost/provider commitment approval** after exact pricing is revalidated. Only after that explicit approval may a later accepted-main provider-apply boundary create Cloud.ru resources.

Until then:

- `provider_apply_authorized=false`;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- no production DNS/public ingress is activated;
- no provider credential enters a PR;
- WP23 remains locked;
- broker write/Real execution remain disabled.
