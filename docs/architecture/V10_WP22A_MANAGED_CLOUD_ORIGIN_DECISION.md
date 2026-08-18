# Omni-CIO V10 — WP22A Managed-Cloud Origin Decision

Status: **STAGED FREE-FIRST RECOMMENDATION / OWNER COST APPROVAL REQUIRED BEFORE PAID PROVIDER APPLY**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**  
Decision date: **2026-08-18**  
Accepted base `main`: `ee45026b1287c7427dc5e05b2a04b7bdb974d11f`

## 1. Decision scope

This is the WP22A Phase-1 source-only hosting/service recommendation for the accepted public/free/multi-user target. It does **not** create cloud resources, purchase a plan, add provider credentials, publish DNS, enable `PUBLIC_MULTI_USER_ENABLED`, enable T-Invest public functionality, expand broker write authority, unlock WP23 or replace protected V9.

`provider_apply_authorized=false`

The OWNER-directed cost policy is:

`already owned / open source / safe free tier / grant / bonus -> lowest-cost safe paid option -> scale only from measured need`

The reusable rule is recorded in `V10_FREE_FIRST_COST_DISCIPLINE.md`. Project memory is not relied on for this decision.

## 2. Why the previous 24.5k RUB baseline is not the startup budget

The earlier draft correctly identified a strong Cloud.ru HA production topology, but it incorrectly allowed that topology to read like the initial deployment target.

Cloud.ru currently documents three-node multi-zone Business Cluster HA as the recommended PostgreSQL production topology. That remains useful **Stage-3 HA reference architecture**. It does not prove that Omni-CIO needs to buy it before the OWNER has experienced the product or before measured users/load/failure budgets justify it.

The current OWNER-authorized recurring infrastructure target is therefore **0 RUB/month**. No paid provider apply is authorized by this source decision.

## 3. Cost ladder

### Stage 0 — zero recurring proof-of-product

Use already-owned GitHub plus the accepted source-controlled Web/Core and Lenovo engineering/acceptance environment to prove end-to-end product behavior. Lenovo is not a public production origin.

An optional free cloud preview may be added later only from accepted source-controlled deployment. It is synthetic/non-private until its exact data/secret/legal boundary is accepted. It must not hold real tenant-private state, broker credentials or imply public T-Invest permission.

### Stage 1 — free/grant hosted pilot

Use current eligible free tiers/grants/bonuses with a hard spend cap and automatic paid overage disabled.

Current official-provider snapshot, to be revalidated immediately before use:

- Cloud.ru Evolution documents free-tier use for testing/small sites/apps; current Container Services free quota is 25 vCPU-hours and 50 GB RAM-hours monthly, and Object Storage has a free quota. Cloud.ru also advertises a 4,000 RUB bonus for eligible card-linked accounts.
- Yandex Cloud documents a new-customer initial grant of at least 4,000 RUB for eligible Russian residents, valid for 60 days.
- Timeweb Cloud documents hourly VPS billing, a 50 RUB minimum payment and an individually reviewed support bonus for testing VPS before payment.

Promotional capacity is not production/SLA/legal evidence.

### Stage 2 — minimum safe paid pilot

Only if free/grant stages cannot satisfy the required gate. The paid-pilot provider is intentionally **UNSELECTED** until fresh official price/security/capacity review immediately before apply.

Select the lowest-cost option that satisfies every hard requirement and size from measured load. OWNER recurring-cost approval remains mandatory.

### Stage 3 — HA production scale-up

Cloud.ru Evolution remains the strongest currently reviewed HA scale-up candidate:

```text
ordinary Internet browser
        |
        v
Cloud.ru Evolution DNS
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

This is a **future scale-up reference**, not an initial purchase commitment.

## 4. Hard boundaries that cheap/free services cannot weaken

Free or low-cost composition is allowed only if responsibilities are explicit and failure domains are bounded. We may use source-controlled code to close ordinary feature gaps such as retries, health checks, caching, validation, rate limiting and provider adapters.

We do **not** split identity/session authority, the primary tenant database or raw secret custody across unrelated free providers merely to reduce a small bill.

Code cannot compensate for missing:

- legal/broker permission;
- required personal-data localization;
- trustworthy tenant-scoped secret custody;
- durable backup/recovery;
- a required security primitive.

## 5. Russian USER edge

Cloudflare remains **rejected as the primary or sole normal Russian USER production edge** because current first-party Cloudflare guidance reports Russian-ISP throttling that can make Cloudflare-protected sites unreliable for Russian visitors.

A later secondary role requires separate reachability, data-localization, cost and failure-mode review. Cloudflare/GitHub/provider identity is never Omni-CIO product identity.

## 6. Container Apps boundary

Cloud.ru Container Apps is attractive for a **synthetic free preview** because it has a free monthly compute quota and scale-to-zero behavior.

It is not accepted here as the real-user primary runtime/data plane. The current accepted WP22A requirements include tenant-private PostgreSQL, tenant-scoped secret custody, recovery and legal/data boundaries. Those must be independently proven before any real user/private payload is placed there.

## 7. NLB Terraform documentation conflict — fail closed

Current Cloud.ru first-party documentation remains internally inconsistent: the NLB limitations material and the Terraform resource reference do not cleanly agree on Terraform management support.

Before any NLB provider apply, source-controlled tooling must pin the exact provider and prove schema/configuration plus a reviewed non-mutating plan/acceptance step. Terraform is preferred if that exact path passes; otherwise reviewed Public API is the fallback. No provider apply is authorized while this remains unresolved by exact toolchain evidence.

## 8. Database ladder

For Stage 0/1 synthetic preview, real tenant-private PostgreSQL is not authorized.

For a later paid pilot, database mode/topology is selected from actual security, availability and measured load requirements immediately before apply. A public PostgreSQL endpoint remains forbidden.

For Stage 3 HA, Cloud.ru Business Cluster HA (`Primary + 2 Standby`, three AZ) remains the reference because the provider documents it as the recommended production topology and it survives one availability-zone loss.

Provider backup never replaces V10 portable encrypted off-runtime recovery, integrity/hash verification, corrupt-backup rejection and restore rehearsal.

## 9. Candidate disposition

- **Cloud.ru Evolution — PREFERRED FREE PREVIEW + HA SCALE-UP CANDIDATE.** Russia-hosted platform, current free tier/bonus, later private managed PostgreSQL, Secret Management/KMS, DNS/NLB/certificates and Terraform/API capabilities.
- **Yandex Cloud — GRANT-BACKED SECURITY-STRONG ALTERNATIVE.** Useful initial grant plus mature managed database/secret/KMS stack; grant is temporary.
- **Timeweb Cloud — LOW-COST TEST/PILOT ALTERNATIVE.** Cheap hourly Russian VPS and support test bonuses; tenant secret/data boundary still needs exact review before real-user use.
- **Render — SYNTHETIC PREVIEW ONLY / NOT RUSSIA PRIVATE-DATA PLANE.** Protected V9 `app:app` remains untouched.
- **Cloudflare primary edge — REJECT PRIMARY/SOLE RUSSIAN USER PATH.**

No candidate is allowed to create a paid resource in this PR.

## 10. Cost reference

Current startup target: **0 RUB/month recurring owner out-of-pocket**.

For comparison only, the earlier Cloud.ru HA reference remains approximately:

- Business PostgreSQL 3-node Multi-AZ: ~21,297.69 RUB/month;
- two reference application VMs + disks: ~1,722.99 RUB/month;
- NLB two AZ / one unit each + public IP: ~1,305.89 RUB/month;
- public DNS: ~32.94 RUB/month;
- Certificate Manager: currently 0 RUB;
- total HA reference: ~24,508.83 RUB/month before excluded traffic/storage/monitoring/WAF/etc.

These figures are engineering snapshots, not a quote, purchase authorization or startup budget. All mutable prices/quotas must be revalidated immediately before use.

## 11. Safety / locks

Until the relevant later gates pass:

- `provider_apply_authorized=false`;
- `PUBLIC_MULTI_USER_ENABLED=false`;
- no provider resources or provider credentials are created by this PR;
- no production DNS/public ingress is activated;
- no real broker/Telegram/VK/provider secret is committed;
- T-Invest public connector remains fail-closed pending broker terms permission;
- `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false`;
- no transfer/withdrawal authority;
- WP23 remains locked;
- protected V9 rollback remains available.

## 12. Phase-1 exit condition

This recommendation becomes accepted source authority only after exact-head DRAFT CI GREEN, full diff/review, fresh READY exact-head GREEN, squash merge, exact-main verification and post-merge Regression Shield GREEN.

Source acceptance still does not authorize provider apply. Any later recurring commitment requires exact current pricing/free-quota validation, hard budget boundary, measured need, OWNER approval and a reviewed delete/shutdown path.
