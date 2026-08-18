# Omni-CIO V10 — WP22A Service Selection Gate

Status: **STAGED FREE-FIRST / OWNER COST APPROVAL REQUIRED / NO PROVIDER APPLY AUTHORIZED**  
Owning package: **WP22A — External Web Access / Product Authentication Security Gate**

## 1. Authority transition

The accepted public-hosted target requires a normal public Web service independent of OWNER home infrastructure and practically reachable from ordinary Russian networks.

Current decision authority:

- `V10_FREE_FIRST_COST_DISCIPLINE.md`;
- `V10_WP22A_MANAGED_CLOUD_ORIGIN_CONTRACT.json`;
- `V10_WP22A_MANAGED_CLOUD_ORIGIN_DECISION.md`.

Historical lifecycle marker retained for inherited regression provenance: `Production-origin provider selection is not yet made`.

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
- tenant-scoped encrypted secrets/private state;
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

Multiple free/cheap services may be composed only with explicit source-controlled interfaces and bounded failure domains. Do not fragment identity/session authority, primary tenant database semantics or raw secret custody merely for marginal savings.

## 4. Staged selection

### Stage 0 — zero recurring proof-of-product

Already-owned GitHub + Lenovo may prove the product for engineering/OWNER acceptance, but Lenovo is never the final public production availability anchor.

Optional free cloud preview is synthetic/non-private only until its exact gates pass. It cannot accept real public registrations/private tenant data/broker credentials by implication.

### Stage 1 — free/grant hosted pilot

Prefer current eligible provider free tiers, grants and bonuses with automatic paid overage disabled and a hard spend boundary.

Current snapshot, revalidated immediately before use:

- Cloud.ru Evolution: free-tier services and small-app testing capacity; current Container Services free quota includes 25 vCPU-hours and 50 GB RAM-hours monthly; eligible card-linked users may receive a 4,000 RUB bonus.
- Yandex Cloud: new eligible Russian customers receive an initial grant of at least 4,000 RUB, valid 60 days.
- Timeweb Cloud: hourly VPS billing, 50 RUB minimum payment and individually reviewed support bonuses for VPS testing.

These are promotional/testing mechanisms, not production/SLA evidence.

### Stage 2 — minimum safe paid pilot

Only after free/grant paths are proven insufficient for a hard gate. Provider/topology remains **UNSELECTED** until a fresh official comparison immediately before apply.

Choose the lowest-cost option satisfying all hard requirements and size it from measured load. OWNER approval of recurring cap and delete/shutdown path is mandatory.

### Stage 3 — HA production scale-up

Cloud.ru Evolution remains the strongest currently reviewed HA scale-up reference:

- two application VMs in different AZs;
- georedundant L4 NLB using two AZs;
- private Managed PostgreSQL Business Cluster HA, three nodes across three AZs;
- Secret Management/KMS and portable V10 recovery.

Its ~24.5k RUB/month reference is **not the startup budget**. Scale to it only from measured SLA/load/failure-budget/user demand.

## 5. Provider disposition

- **Cloud.ru Evolution — preferred free-preview and HA scale-up candidate.**
- **Yandex Cloud — grant-backed security-strong alternative.**
- **Timeweb Cloud — low-cost test/pilot alternative.**
- **Render — synthetic preview only; not accepted as Russia-primary private-data plane.**
- **Cloudflare primary edge — rejected as primary/sole Russian USER path** because current first-party guidance reports Russian-ISP throttling.

A later paid-pilot provider is deliberately not selected until the Stage-2 revalidation.

## 6. Reusable security controls

Reuse Host allowlist, trusted proxy boundary, Secure/HttpOnly/SameSite server sessions, bounded lifetime/rotation/revoke, CSRF + Origin/Referer validation, deny-by-default CORS, rate limits, HSTS/CSP/nosniff/referrer/no-store as appropriate, direct-origin negatives, exact-head CI and rollback.

Free/cheap composition may add retries/cache/health checks/adapters, but cannot replace legal permission, localization, secret custody or durable recovery.

## 7. NLB automation conflict

Cloud.ru first-party documentation remains inconsistent around NLB Terraform management. Before provider apply, pin the exact provider and prove the NLB schema/configuration plus a reviewed non-mutating provider plan/acceptance step. If accepted, use Terraform; otherwise use the reviewed Public API fallback.

Documentation inconsistency is a blocker, not permission to guess.

## 8. Cost boundary and locks

`provider_apply_authorized=false`  
`PUBLIC_MULTI_USER_ENABLED=false`

No provider resource, provider credential, production DNS/public ingress or paid overage is authorized by this PR.

The current 0-RUB target is a budget policy, not permission to weaken data/security/legal/broker gates. T-Invest public connector remains independently fail-closed.

## 9. Exit from service-selection gate

Technical source acceptance requires:

1. current official provider/free-tier/cost review;
2. explicit staged free-first policy;
3. hard security/data/legal/recovery boundaries;
4. deterministic regression guards;
5. exact-head DRAFT CI GREEN;
6. full diff/review with zero blockers;
7. fresh READY exact-head CI GREEN;
8. squash merge;
9. exact-main post-merge Regression Shield GREEN.

Even after source acceptance, provider apply remains blocked until the exact stage-specific apply boundary and any required OWNER cost/account consent are accepted. WP23 remains locked behind the full corrected WP22A Exit Gate.
