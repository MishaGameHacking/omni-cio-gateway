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

## 4. Candidate comparison

### 4.1 Cloud.ru Evolution — recommended pending cost approval

**Recommended topology:**

`Internet -> Cloudflare edge/Tunnel -> Cloud.ru Evolution VM -> private VPC -> Cloud.ru Managed PostgreSQL`

with tenant/runtime secrets stored in **Cloud.ru Secret Management**, optionally protected by **Key Management**, and encrypted recovery material placed in reviewed **Evolution Object Storage** plus the V10 off-runtime recovery path.

Why it currently ranks first for Omni-CIO:

1. Cloud.ru publishes an official secure reference architecture in which the application runs on an Evolution VM and Managed PostgreSQL is reachable only over a private subnet/IP.
2. Managed PostgreSQL connects from an Evolution VM only over an internal IP in the same project/subnet, so the database does not need a public Internet port.
3. Managed PostgreSQL supports `Primary/Standby`; the Terraform resource exposes `primary_standby_mode=true` for a synchronized two-node topology.
4. Secret Management is project-scoped/versioned and can encrypt secrets using Key Management or a provider system key.
5. Secret Management is currently free in Evolution, reducing the pressure to weaken the secret boundary for cost reasons.
6. Cloud.ru publishes a Terraform provider and VM/VPC/security-group automation path, so infrastructure can remain source-controlled and reproducible.
7. Evolution infrastructure is in Russia and current provider documentation states 152-FZ UZ-1 attestation.
8. Evolution is pay-as-you-go and accepts bank-card top-up for individuals.
9. A Cloudflare Tunnel from the **managed-cloud VM**, unlike a Tunnel to the PROJECT OWNER home Lenovo, satisfies the no-home-origin requirement while allowing the application origin port to remain non-public.

#### Initial PostgreSQL topology

The initial production recommendation is **Standard mode, two-node Primary/Standby**, not a single-node database.

Reasons:

- the accepted V10 target is a real public service, so one database process/node should not silently become the only durable-state availability boundary;
- Cloud.ru Standard supports small resource sizes and up to two nodes;
- Primary/Standby preserves a bounded low-cost entry point while providing node redundancy;
- the Standard topology remains single-AZ, so it is **not** equivalent to Business Multi-AZ and must not be described as zone-level high availability;
- later capacity/availability evidence may require migration through backup/restore to Business Multi-AZ, which Cloud.ru explicitly supports as the path when changing deployment mode.

Important limitation: **Cloud.ru Container Apps is explicitly rejected as the primary runtime for this design.** Cloud.ru's own FAQ says Container Apps does not support Managed PostgreSQL connectivity and that connecting to an external database through an Internet-open port is not a safe scenario. Therefore the safe Cloud.ru design uses a VM + VPC + private Managed PostgreSQL, not Container Apps.

Current official sources:

- secure VM + private Managed PostgreSQL tutorial: `https://cloud.ru/docs/tutorials-evolution/list/topics/free-tier-vm__postgresql-connection`;
- private Managed PostgreSQL connection rule: `https://cloud.ru/docs/paas-postgresql/ug/topics/guides__databases__connecting-to-database`;
- Managed PostgreSQL deployment modes: `https://cloud.ru/docs/paas-postgresql/ug/topics/concepts__deployment-mode`;
- Managed PostgreSQL replication/topology: `https://cloud.ru/docs/paas-postgresql/ug/topics/concepts__replication`;
- Managed PostgreSQL Terraform resource: `https://cloud.ru/docs/terraform-evolution/ug/topics/reference/resources/cloudru_evolution_postgresql_cluster`;
- Managed PostgreSQL backup policy: `https://cloud.ru/docs/paas-postgresql/ug/topics/guides__backups__backup-policy`;
- Container Apps database limitation: `https://cloud.ru/docs/container-apps-evolution/ug/topics/faq__database-connection`;
- Secret Management: `https://cloud.ru/docs/scsm/ug/index`;
- Secret Management + Key Management: `https://cloud.ru/docs/scsm/ug/topics/guides__add-secret`;
- Secret Management pricing: `https://cloud.ru/docs/scsm/ug/topics/pricing`;
- Terraform VM deployment: `https://cloud.ru/docs/terraform-evolution/ug/topics/guides/vm_create_full`;
- Managed PostgreSQL current tariff: `https://cloud.ru/documents/tariffs/evolution/managed-postgresql`;
- VM pricing/reference calculation: `https://cloud.ru/docs/virtual-machines/ug/topics/pricing`;
- Evolution Compute network tariff: `https://cloud.ru/documents/tariffs/evolution/evolution-compute`;
- Evolution payment model: `https://cloud.ru/docs/evolution/overview/topics/pricing`;
- Evolution compliance: `https://cloud.ru/docs/evolution/overview/topics/security__compliance`.

### 4.2 Timeweb Cloud — lower-cost fallback

Timeweb remains a viable fallback because it offers Russian regions, Managed PostgreSQL, private networking, physical/logical backups, Terraform/API automation and infrastructure marketed for 152-FZ workloads.

It does not rank first for this WP22A public multi-tenant design because the review did not find an equivalent general-purpose managed Secret Management/KMS boundary for tenant broker credentials, while the accepted V10 contract explicitly requires a strong tenant-scoped encrypted secret boundary. Its object-storage credential model also requires additional least-privilege review for backup separation.

This is a tradeoff, not a claim that Timeweb is insecure. If PROJECT OWNER cost approval rejects the Cloud.ru cost envelope, Timeweb is the first fallback and the broker-secret/public-connector gate remains fail-closed until an acceptable vault/KMS design is proven.

Official sources:

- DBaaS overview/regions: `https://timeweb.cloud/docs/dbaas`;
- PostgreSQL cluster/private-IP configuration: `https://timeweb.cloud/docs/dbaas/dbaas-create`;
- API/Terraform tokens: `https://timeweb.cloud/docs/account-management/token`;
- 152-FZ infrastructure: `https://timeweb.cloud/solutions/152fz`.

### 4.3 Yandex Cloud — strong security, higher-cost alternative

Yandex Cloud provides a mature Russia-region Managed PostgreSQL platform plus Lockbox and KMS and explicitly lists 152-FZ among the standards protecting Managed PostgreSQL infrastructure. It is a technically strong alternative.

It ranks below Cloud.ru for this initial launch primarily because a production-grade managed PostgreSQL configuration is materially more expensive than the minimum Cloud.ru/Timeweb paths and the initial launch has no revenue requirement. It remains the preferred fallback if later reliability/security requirements justify the additional cost.

Official sources:

- Managed PostgreSQL: `https://yandex.cloud/ru/docs/managed-postgresql/`;
- Managed PostgreSQL pricing: `https://yandex.cloud/ru/docs/managed-postgresql/pricing`;
- Lockbox pricing/service: `https://yandex.cloud/ru/docs/lockbox/pricing`;
- KMS pricing/service: `https://yandex.cloud/ru/docs/kms/pricing`.

### 4.4 Render — rejected as primary production data plane

Render remains useful historical V9 infrastructure, but it is not eligible as the final primary public V10 personal-data plane for the intended Russian USER population:

- current Render regions are Oregon, Ohio, Virginia, Frankfurt and Singapore; there is no Russia region;
- the free Web service spins down after 15 minutes without inbound traffic;
- free Render Postgres expires after 30 days;
- Render itself says free instances should not be used for production applications.

Protected V9 `app:app` remains untouched; this rejection applies only to the new public V10 primary data plane.

Official sources:

- regions: `https://render.com/docs/regions`;
- free-instance limitations: `https://render.com/docs/free`.

## 5. Recommended production boundary

Pending PROJECT OWNER cost approval, the recommended final WP22A provider boundary is:

```text
ordinary Internet browser
        |
        v
Cloudflare DNS / TLS / WAF / DDoS
        |
        v
Cloudflare Tunnel
(outbound from managed-cloud origin)
        |
        v
Cloud.ru Evolution VM
Omni-CIO Web/API runtime
        |
        +----> Cloud.ru Secret Management / Key Management
        |
        `----> private VPC/subnet
                  |
                  v
       Cloud.ru Managed PostgreSQL
          Primary + Standby
                  |
                  v
          encrypted backup/recovery path
```

Cloudflare is an edge and origin-protection component only. Cloudflare/GitHub/provider membership **must never mint an Omni-CIO USER session**. Normal product authentication remains Telegram/VK mapped to the internal Omni-CIO account.

The public VM application port must not be independently reachable as an untrusted origin path when Cloudflare Tunnel is active. Administrative access, if required, is a separate least-privilege engineering path and never a product-login bypass.

The VM can use outbound-only Internet through a reviewed sNAT path for Cloudflare Tunnel/provider operations. No inbound public application port is required by the recommended product path.

## 6. Current cost boundary

Cloud.ru Managed PostgreSQL currently publishes pay-as-you-go rates including VAT:

- 1 vCPU: `1.49145 RUB/hour`;
- 1 GB RAM: `0.4026 RUB/hour`;
- network SSD: `0.016836 RUB/GB-hour`.

Reference arithmetic at 720 hours:

- one `1 vCPU / 2 GB RAM / 20 GB SSD` PostgreSQL node: about **1,896.03 RUB/month**;
- two-node Primary/Standby PostgreSQL reference: about **3,792.05 RUB/month**.

The current VM pricing documentation includes a `1 vCPU / 2 GB RAM / 30% guaranteed CPU` example at `0.88452 RUB/hour`, and a boot-disk example at `0.0156 RUB/GB-hour`. The current Evolution Compute tariff lists sNAT at `0.2074 RUB/hour` including VAT.

Using those **reference** values only, a minimum arithmetic stack of:

- two small PostgreSQL nodes;
- one reference `1 vCPU / 2 GB` VM;
- 20 GB boot disk;
- one sNAT gateway;

is about **4,802.88 RUB/month**.

This is a lower-bound engineering estimate, **not a purchase quote and not a capacity guarantee**. It excludes a custom domain, additional Object Storage beyond any applicable free allocation, traffic, monitoring products, future scale, Business Multi-AZ, and any larger VM flavor required by load testing. The exact selected VM flavor and the complete provider cart must be revalidated immediately before purchase.

Before provider apply, PROJECT OWNER must receive and approve:

- exact selected VM flavor and monthly estimate;
- exact PostgreSQL topology and monthly estimate;
- sNAT/network/storage/backup costs;
- custom-domain cost if a new domain is required;
- expected all-in initial monthly range;
- whether the cost is recurring/pay-as-you-go and how to stop it.

No paid provider resource is authorized before that approval.

## 7. Recovery and exit strategy

The provider selection is valid only if later source work proves:

- PostgreSQL backup + integrity verification + corrupt-backup rejection;
- provider automatic backup policy plus a separately portable/off-runtime recovery copy where required;
- encrypted off-runtime backup/recovery;
- replacement VM/runtime reconstruction from GitHub plus private durable state;
- Secret Management/KMS rotation/recovery without putting secrets in GitHub;
- tenant isolation preserved after restore;
- rollback to the last accepted V10 release;
- protected V9 rollback remains available until responsible cutover;
- provider exit is possible using portable PostgreSQL backups, source-controlled runtime/IaC and non-provider-exclusive application contracts.

Cloud.ru's current Managed PostgreSQL backup policy supports scheduled backups and retention up to 30 days; native provider backup alone does not replace the V10 requirement for independently recoverable durable state and corrupt-backup validation.

## 8. Phase-1 exit condition

This recommendation is not yet the final Phase-1 PASS because a recurring paid provider choice cannot be committed on behalf of PROJECT OWNER.

Phase 1 can proceed autonomously through source-controlled architecture, tests and CI. The first legitimate OWNER blocker is **cost/provider commitment approval** after exact pricing is revalidated. Only after that explicit approval may a later accepted-main provider-apply boundary create Cloud.ru resources.

Until then:

- `provider_apply_authorized=false`;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- no production DNS/public ingress is activated;
- no provider credential enters a PR;
- WP23 remains locked;
- broker write/Real execution remain disabled.
