# Omni-CIO V10 — WP22A Managed-Cloud Origin Decision

Status: **CLOUD.RU EVOLUTION SELECTED AS PRODUCTION BOUNDARY / FREE-FIRST / OWNER COST APPROVAL REQUIRED BEFORE ANY PAID APPLY**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**  
Decision date: **2026-08-18**  
Accepted base `main`: `ee45026b1287c7427dc5e05b2a04b7bdb974d11f`

## 1. Decision scope

This is the WP22A Phase-1 source-only service/hosting architecture decision for the accepted public/free/multi-user target.

**Selected managed-cloud production origin/provider boundary: Cloud.ru Evolution.**

This decision does **not** create cloud resources, purchase a plan, add provider credentials, publish DNS, enable `PUBLIC_MULTI_USER_ENABLED`, enable T-Invest public functionality, expand broker write authority, unlock WP23 or replace protected V9.

`provider_apply_authorized=false`

The OWNER-directed cost policy is:

`already owned / open source / safe free tier / grant / bonus -> lowest-cost safe paid option -> scale only from measured need`

The reusable rule is recorded in `V10_FREE_FIRST_COST_DISCIPLINE.md`. Project memory is not relied on for this decision.

## 2. Why provider selection and 0 RUB apply are compatible

WP22A Phase 1 requires an actual managed-cloud origin and edge/data/credential boundary. Leaving the future provider `UNSELECTED` would defer the architecture decision instead of satisfying it.

At the same time, selecting a provider in source does not authorize buying resources. The current OWNER-authorized recurring infrastructure target remains **0 RUB/month** until proof-of-product and the later privileged provider-apply gate.

Therefore:

- Cloud.ru Evolution is the selected production provider/boundary;
- the exact paid VM/Managed PostgreSQL SKU is revalidated immediately before Stage-2 apply;
- no paid resource is created by this PR;
- any material recurring cost still requires explicit OWNER approval;
- HA capacity is not purchased before measured need.

## 3. Why Cloud.ru Evolution is selected over the cheaper raw-compute alternatives

The cheapest VPS line item is not the whole security boundary.

Cloud.ru currently provides in one Russia-hosted platform the hard capabilities required by the accepted WP22A contract:

- VPC, public IP and security groups for a normal browser-facing managed-cloud origin;
- Managed PostgreSQL reachable through the private Evolution network rather than a public database endpoint;
- Secret Management as a managed service with no service fee;
- Key Management as a managed service with no service fee;
- Certificate Manager as a managed service with no service fee and support for Let's Encrypt certificates;
- Evolution DNS;
- Object Storage with an ongoing free tier for portable encrypted recovery bundles;
- Terraform/Public API automation surfaces;
- a later multi-AZ VM/NLB/Managed PostgreSQL HA scale-up path.

Timeweb Cloud remains a useful lower-cost compute fallback. However, the reviewed first-party path for Vault is a Kubernetes add-on whose production mode requires explicit initialization/unseal and HA operations. Using cheap Timeweb compute while moving credential custody to another provider would also create a cross-provider bootstrap/recovery dependency merely to save part of a small pilot bill. That is not the better overall V10 boundary at this stage.

Yandex Cloud remains a strong managed fallback, but its initial grant expires and its Lockbox/KMS services are metered. It is not selected while Cloud.ru closes the same reviewed hard boundaries with lower ancillary service cost.

This is an engineering selection, not a legal certification or a promise that Cloud.ru will always remain cheapest. Mutable prices, service states and legal constraints are revalidated before apply.

## 4. Cost ladder

### Stage 0 — zero recurring proof-of-product

Use already-owned GitHub plus the accepted source-controlled Web/Core and Lenovo engineering/acceptance environment to prove end-to-end product behavior. Lenovo is not a public production origin.

Optional Cloud.ru Container Apps free-tier preview may be added later only from accepted source-controlled deployment. It is synthetic/non-private until its exact security/legal/budget boundary is accepted. It must not hold real tenant-private state, broker credentials or imply public T-Invest permission.

Target OWNER out-of-pocket recurring cost: **0 RUB/month**.

### Stage 1 — Cloud.ru free/bonus hosted pilot

Use eligible Cloud.ru Evolution free-tier/bonus resources only after a fail-closed spend boundary has been proven.

Current official-provider snapshot, to be revalidated immediately before use:

- Container Services free quota: 25 vCPU-hours and 50 GB RAM-hours monthly;
- Object Storage standard free quota: 15 GB plus documented request/egress quotas;
- Evolution DNS includes a free request quota;
- eligible card-linked accounts may receive 4,000 bonus RUB;
- creation of a new free VM is not assumed for a newly registered account because current first-party documentation says new free-VM creation is unavailable to users registered after 2026-06-30;
- usage above a free quota can become billable, so free tier is not a substitute for an explicit no-overage control.

This stage is validation capacity, not a production/SLA claim. Real tenant-private database state remains forbidden here until Stage 2.

Target OWNER out-of-pocket recurring cost: **0 RUB/month**.

### Stage 2 — minimum safe Cloud.ru paid pilot

Only if Stages 0/1 cannot satisfy the real-user production gate.

Selected provider: **Cloud.ru Evolution**.

Initial boundary:

```text
ordinary Internet browser
        |
        v
OWNER domain -> Evolution DNS
        |
        v
Evolution public IP
security groups: 80/443 only as required
        |
        v
one right-sized Evolution VM
Nginx/Caddy or accepted equivalent
        |
        +-----------------------------+
        |                             |
        v                             v
private Evolution VPC          SCMS + KMS
        |                       tenant-scoped
        v                       credential boundary
Managed PostgreSQL Standard
private network only
        |
        v
portable encrypted backups
Evolution Object Storage
+ OWNER-controlled secondary copy
```

TLS/certificate lifecycle is through Evolution Certificate Manager / Let's Encrypt or an equivalent reviewed Cloud.ru-native path.

The exact paid VM/DB SKU and total monthly cost are intentionally **not frozen months in advance**. They are selected immediately before apply from measured Stage-0/1 load and the then-current official tariff, using the smallest Cloud.ru topology that satisfies hard requirements.

OWNER recurring-cost approval remains mandatory before apply.

### Stage 3 — HA production scale-up

Cloud.ru Evolution remains the selected provider. The current HA reference is:

```text
ordinary Internet browser
        |
        v
Evolution DNS
        |
        v
Evolution L4 NLB
2 AZ / 1 resource unit per AZ
        |
        +-------------------+
        |                   |
        v                   v
Evolution VM A         Evolution VM B
AZ-A                   AZ-B
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
```

The existing engineering estimate of about 24.5k RUB/month is retained only as a future reference. It is **not** the startup budget or an authorized purchase.

## 5. Public edge and Russian USER reachability

The selected initial production edge is the Cloud.ru Evolution public IP/security-group/DNS path. It does not depend on OWNER home public IP, Wi-Fi/router/LAN, home Internet/power or Lenovo.

Cloudflare remains **rejected as the primary or sole normal Russian USER production edge** under the current accepted reachability boundary because current first-party Cloudflare guidance reports Russian-ISP throttling that can make Cloudflare-protected sites unreliable for Russian visitors.

A later Cloudflare secondary role requires separate reachability, data-localization, cost and failure-mode review. Cloudflare/GitHub/provider identity is never Omni-CIO product identity.

## 6. Database boundary

Real tenant-private production state uses **Cloud.ru Evolution Managed PostgreSQL on the private Evolution network**. A public PostgreSQL endpoint is forbidden.

Stage 2 begins with the smallest Standard topology that passes capacity/recovery requirements. Stage 3 may move to Business Cluster HA only after measured need.

Provider backup never replaces V10 portable encrypted recovery, integrity/hash verification, corrupt-backup rejection and restore rehearsal.

## 7. Tenant credential/key boundary

Real tenant broker/provider credentials use **Evolution Secret Management**, with **Evolution KMS** for the accepted application encryption/envelope boundary where required.

Rules remain:

- tenant-scoped ownership;
- least-privilege service identity;
- raw credential never returned after Web submission;
- no browser Web Storage;
- no GitHub/CI/log/artifact material;
- no shared global broker credential;
- rotation/revoke/recovery is mandatory;
- provider engineering identity cannot mint an Omni-CIO product session.

## 8. Backup/recovery boundary

Primary portable recovery target is client-side encrypted Cloud.ru Evolution Object Storage using bounded retention and integrity hashes.

Because same-provider recovery alone is not sufficient for every provider/account failure mode, an OWNER-controlled secondary encrypted copy is required as an additional portability boundary. Its existence does not make OWNER home infrastructure a production availability dependency.

Before public activation prove replacement-runtime reconstruction without requiring the original Lenovo runtime, database restore, tenant-isolation preservation, corrupt-backup rejection and credential/key recovery.

## 9. Free tier / no-overage boundary

Cloud.ru documents that usage above free quotas can be billed in RUB or bonuses. Therefore Stage 1 is not allowed to rely on a label saying “free tier” alone.

Before any free-tier apply, the implementation must prove a fail-closed spend boundary or equivalent operational control that prevents an unintended OWNER cash charge. If the provider cannot provide an acceptable hard cap for the selected resource, Stage 1 must use only a bounded disposable preview that is destroyed before quota exhaustion or skip that resource entirely.

No automatic upgrade or paid overage is authorized.

## 10. Automation boundary

Terraform is preferred for Cloud.ru resources where the exact pinned provider supports the required resource and passes a reviewed non-mutating acceptance/plan.

Cloud.ru first-party NLB documentation remains inconsistent around Terraform management. NLB is not needed for the initial single-VM Stage 2. Before Stage-3 NLB apply, pin the exact provider and prove schema/configuration plus non-mutating plan; otherwise use a reviewed Public API path.

Privileged provider mutation may only occur from the later reviewed accepted-main operations boundary. This PR contains no provider credential and performs no apply.

## 11. Candidate disposition

- **Cloud.ru Evolution — SELECTED production origin/provider and preferred free-preview path.** It closes the reviewed Russian-region runtime/network/database/credential/key/TLS/backup/automation boundaries in one provider and retains an HA scale-up path.
- **Yandex Cloud — STRONG MANAGED FALLBACK.** Russia region, Managed PostgreSQL, Lockbox, KMS, Terraform and an initial grant; not selected because the grant is temporary and ancillary managed security services are metered.
- **Timeweb Cloud — LOW-COST COMPUTE FALLBACK.** Cheap hourly Russian VPS and test bonus are useful, but its reviewed production Vault path is Kubernetes/self-managed and a cross-provider credential split would add operational/recovery complexity.
- **Render — SYNTHETIC PREVIEW ONLY / NOT RUSSIA PRIVATE-DATA PLANE.** Protected V9 `app:app` remains untouched.
- **Cloudflare primary edge — REJECT PRIMARY/SOLE RUSSIAN USER PATH.**

## 12. Personal-data/legal boundary

Primary identity/session/tenant/private state remains within the selected Russia-hosted production boundary unless a later legal review explicitly permits otherwise.

Provider claims do not replace Omni-CIO operator obligations. Production legal signoff remains required. Cross-border processing remains fail-closed pending separate review.

## 13. Broker/public-service separation

Production-origin selection does not imply T-Invest public connector permission.

The public Web/account platform can proceed while T-Invest-backed public production remains fail-closed pending contractually valid permission or another accepted compliant design.

No broker-write, transfer/withdrawal or Real execution authority is added here.

## 14. Safety / locks

Until the relevant later gates pass:

- `provider_apply_authorized=false`;
- current authorized recurring infrastructure budget = **0 RUB/month**;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- no provider resources or provider credentials are created by this PR;
- no production DNS/public ingress is activated;
- no real broker/Telegram/VK/provider credential is committed;
- T-Invest public connector remains fail-closed pending broker terms permission;
- `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false`;
- no transfer/withdrawal authority;
- WP23 remains locked;
- protected V9 rollback remains available.

## 15. Phase-1 exit condition

This decision becomes accepted source authority only after exact-head DRAFT CI GREEN, full diff/review, fresh READY exact-head GREEN, squash merge, exact-main verification and post-merge Regression Shield GREEN.

Source acceptance still does not authorize provider apply. Stage-1 provider preview requires a proven no-overage boundary. Any Stage-2 recurring commitment requires exact current pricing/SKU validation, measured need, OWNER approval and a reviewed delete/shutdown path.
