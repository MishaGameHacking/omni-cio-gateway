# Omni-CIO V10 — WP22A Service Selection Gate

> **Amendment 18 CURRENT-AUTHORITY OVERRIDE (2026-09-21): HISTORICAL / SUPERSEDED FOR CURRENT PROVIDER SELECTION.** The Cloud.ru/Cloudflare/Render provider-selection discussion below is retained only as accepted historical decision evidence. It does not authorize current or future V10 deployment. Current production-platform authority is Timeweb Cloud and current human-login authority is Telegram Login only.


Status: **HISTORICAL / SUPERSEDED BY AMENDMENT 18 FOR CURRENT PROVIDER SELECTION**  
Historical accepted WP22A status: **CLOUD.RU EVOLUTION SELECTED / STAGED FREE-FIRST / OWNER COST APPROVAL REQUIRED / NO PROVIDER APPLY AUTHORIZED**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**

## 1. Authority transition

The accepted public-hosted target requires a normal public Web service independent of OWNER home infrastructure and practically reachable from ordinary Russian networks.

Current decision authority:

- `V10_FREE_FIRST_COST_DISCIPLINE.md`;
- `V10_WP22A_MANAGED_CLOUD_ORIGIN_CONTRACT.json`;
- `V10_WP22A_MANAGED_CLOUD_ORIGIN_DECISION.md`.

Historical lifecycle marker retained for inherited regression provenance: `Production-origin provider selection is not yet made`.

That historical marker is now superseded for the current Phase-1 decision: **Cloud.ru Evolution is the selected production managed-cloud provider/boundary.**

**No provider mutation is authorized** by this source-only recommendation.

## 2. Required final outcome

The architecture must preserve:

- ordinary browser access from modern phones/desktops;
- reliable normal Russian USER reachability;
- public HTTPS hostname;
- public TLS/certificate lifecycle with reviewed issuance, renewal, runtime delivery and rollback;
- no VPN/native-client requirement for ordinary product use;
- managed-cloud production origin independent of OWNER home infrastructure;
- no OWNER home IP/Wi-Fi/router/LAN/Lenovo availability dependency;
- one source-controlled Web App/Core;
- Telegram/VK -> internal Omni-CIO account -> server-side session;
- API + database-enforced tenant isolation;
- tenant-scoped encrypted credentials/private state;
- backup/recovery/replacement-runtime capability;
- GitHub-controlled deployment/release provenance;
- measured capacity/abuse controls;
- privacy/personal-data/legal and broker-term gates;
- `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and protected V9 rollback.

A tunnel whose sole production origin is the PROJECT OWNER's home Lenovo/network is forbidden as the final public-product path.

## 3. Binding cost discipline

Use:

`already owned / open source / safe free tier / grant / bonus -> lowest-cost safe paid option -> scale only from measured need`

The current authorized recurring infrastructure target is **0 RUB/month**. Free first does not mean insecure first: any candidate that fails a hard security/legal/recovery/data-localization gate is rejected regardless of price.

Several free/cheap services may be combined where their responsibilities remain explicit and independently replaceable. Do not fragment identity/session authority, primary tenant database semantics or raw credential custody merely to save a small amount.

A required current-WP architecture decision is still made in source even when provider apply remains blocked.

## 4. Selected production boundary

**Provider: Cloud.ru Evolution.**

Selected Stage-2 minimum production security boundary after proof-of-product:

- one right-sized Evolution VM initially;
- public Evolution IP + security groups;
- Evolution DNS;
- Evolution Certificate Manager / Let's Encrypt;
- private Evolution VPC;
- Evolution Managed PostgreSQL Standard over private networking;
- Evolution Secret Management;
- Evolution Key Management where the application encryption/envelope boundary requires it;
- client-side encrypted portable recovery bundles in Evolution Object Storage;
- OWNER-controlled secondary encrypted recovery copy;
- source-controlled Terraform for accepted supported resources, reviewed Public API fallback only where exact provider support is not accepted.

The exact VM/DB SKU and Stage-2 monthly total are **not pre-bought or frozen**. They are revalidated immediately before apply from measured load and current tariffs. OWNER approval remains mandatory before any new recurring paid commitment.

## 5. Why Cloud.ru is selected

The provider closes the reviewed hard production boundaries in one Russia-hosted platform: public VM/VPC/security groups, private Managed PostgreSQL, managed Secret Management, managed KMS, Certificate Manager, DNS, Object Storage and Terraform/Public API surfaces.

Current first-party pricing also makes Secret Management, Key Management and Certificate Manager available without a separate service fee. Object Storage has an ongoing free quota. This reduces ancillary cost without creating a cross-provider credential bootstrap.

Timeweb Cloud remains a lower-cost raw-compute fallback, but the reviewed first-party Vault solution is a Kubernetes add-on whose production configuration requires explicit initialization/unseal and HA operations. Yandex Cloud remains a strong managed fallback, but its initial grant is temporary and Lockbox/KMS are metered.

Therefore Cloud.ru is selected for the **security/operations boundary**, not because its maximum-HA reference is cheapest.

## 6. Stage 0 — zero recurring proof-of-product

Already-owned GitHub + Lenovo may prove the product for engineering/OWNER acceptance, but Lenovo is never the final public production availability anchor.

Optional Cloud.ru free cloud preview is synthetic/non-private only until its exact gates pass. It cannot accept real public registrations/private tenant data/broker credentials by implication.

Target recurring OWNER out-of-pocket: **0 RUB/month**.

## 7. Stage 1 — Cloud.ru free/bonus hosted pilot

Prefer eligible Evolution free-tier/bonus resources only after an explicit fail-closed spend boundary is proven.

Current snapshot, revalidated immediately before use:

- Container Services: first 25 vCPU-hours and 50 GB RAM-hours per month free;
- Object Storage: 15 GB standard storage plus documented free operation/egress quotas;
- Evolution DNS: free request quota;
- eligible card-linked accounts may receive 4,000 bonus RUB;
- a new free VM must **not** be assumed available to a newly registered account after the documented 2026-06-30 cutoff;
- usage above free quotas can be billed, so `free tier` alone is not a spend control.

Stage 1 remains synthetic/non-private and is not automatically a production/SLA/legal claim.

## 8. Stage 2 — minimum safe paid Cloud.ru pilot

Only when Stages 0/1 cannot satisfy the real-user production gate.

Provider is already selected: **Cloud.ru Evolution**.

Choose the smallest current Cloud.ru VM + Managed PostgreSQL Standard topology that satisfies measured capacity, tenant security, recovery and availability requirements. Exact price/SKU is revalidated immediately before apply; OWNER must approve the recurring cap and delete/shutdown path.

A public PostgreSQL endpoint is forbidden.

## 9. Stage 3 — Cloud.ru HA scale-up

Scale only from measured SLA/load/failure-budget/user demand.

Current retained reference:

- two application VMs in different AZs;
- georedundant L4 NLB;
- private Managed PostgreSQL Business Cluster HA, Primary + 2 Standby across three AZs.

The existing ~24.5k RUB/month engineering estimate is **not the startup budget** and not an authorized purchase.

## 10. Public edge / Cloudflare disposition

The selected initial production edge is Cloud.ru public IP/security groups/DNS, with public TLS managed through the reviewed Cloud.ru certificate boundary.

Cloudflare remains rejected as the primary or sole normal Russian USER production edge under the current accepted reachability boundary. A later secondary role requires separate reachability/data/cost review.

Cloudflare/GitHub/provider account membership is never Omni-CIO product authentication.

## 11. Reusable security controls

Reuse Host allowlist, trusted proxy boundary, Secure/HttpOnly/SameSite server sessions, bounded lifetime/rotation/revoke, CSRF + Origin/Referer validation, deny-by-default CORS, rate limits, HSTS/CSP/nosniff/referrer/no-store as appropriate, direct-origin negatives, exact-head CI and rollback.

Free/cheap composition may add retries/cache/health checks/adapters, but cannot replace legal permission, localization, credential custody or durable recovery.

## 12. NLB automation conflict

Cloud.ru first-party documentation remains inconsistent around NLB Terraform management. NLB is not part of the initial one-VM Stage-2 topology.

Before Stage-3 NLB apply, pin the exact Terraform provider and prove schema/configuration plus a reviewed non-mutating plan. If that exact path is not accepted, use a reviewed Cloud.ru Public API fallback.

Documentation inconsistency is a blocker, not permission to guess.

## 13. Recovery boundary

Provider-native recovery is supplemented by portable V10 recovery:

- client-side encryption before portable backup upload;
- integrity/hash verification;
- corrupt-backup rejection;
- bounded retention;
- replacement-runtime restore;
- tenant-isolation verification after restore;
- OWNER-controlled secondary encrypted copy for provider/account failure portability.

The secondary copy does not make OWNER home infrastructure part of normal production availability.

## 14. Cost boundary and locks

`provider_apply_authorized=false`  
`PUBLIC_MULTI_USER_ENABLED=false`  
current recurring OWNER infrastructure authorization: **0 RUB/month**

No provider resource, provider credential, production DNS/public ingress or paid overage is authorized by this PR.

T-Invest public connector remains independently fail-closed. `app:app`, `trading_methods=false`, `REAL_TRADING_ENABLED=false` and protected V9 rollback remain unchanged. WP23 remains locked.

## 15. Exit from service-selection gate

Technical source acceptance requires:

1. current official provider/free-tier/cost review;
2. explicit production provider and edge/data/credential/recovery boundary;
3. staged free-first cost policy;
4. hard security/data/legal/recovery boundaries;
5. deterministic regression guards;
6. exact-head DRAFT CI GREEN;
7. full diff/review with zero blockers;
8. fresh READY exact-head CI GREEN;
9. squash merge;
10. exact-main post-merge Regression Shield GREEN.

Even after source acceptance, provider apply remains blocked until the stage-specific source-controlled apply boundary, exact current price/SKU revalidation and any required OWNER account/cost consent are accepted.
