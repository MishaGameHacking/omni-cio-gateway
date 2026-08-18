# Omni-CIO V10 — Free-First / Minimum-Budget Service Cost Discipline

Status: **OWNER-DIRECTED / SOURCE ACCEPTANCE PENDING PR #333**  
Scope: V10 external services, cloud/runtime choices and paid infrastructure decisions.  
Owning current package: **WP22A**, with the rule intended to remain reusable for later V10 service-selection gates.

## 1. Binding cost order

For every external service or infrastructure capability, use this decision order:

`already owned / open source / safe free tier / grant / bonus -> lowest-cost safe paid option -> scale only from measured need`

The objective is not "free at any cost". The objective is **minimum owner out-of-pocket cost while preserving correctness, security, legal/broker constraints, recovery and portability**.

## 2. Binding rules

1. **Free first.** If a good free/open-source/already-owned option satisfies the actual hard requirements, prefer it.
2. **Cheapest safe paid fallback.** If no safe free option satisfies the gate, choose the lowest-cost option that does.
3. **Measure before HA spend.** Do not buy HA/capacity for hypothetical future traffic before measured load, failure budget or user demand justifies it.
4. **Experience the product first.** A new material recurring provider commitment is not authorized before the OWNER can experience a meaningful proof-of-product unless a hard legal/security prerequisite makes that impossible.
5. **Multi-provider composition is allowed, not a goal.** Several free/cheap services may be combined when their responsibilities are explicit, bounded and independently replaceable.
6. **Bound failure domains.** A free provider failure must not silently corrupt canonical state, expand money authority or destroy recovery.
7. **Do not fragment the security core for marginal savings.** Identity/session authority, primary tenant database semantics and raw secret custody are not scattered across unrelated providers merely to save a small amount.
8. **Code can close non-critical feature gaps.** Source-controlled validation, retries, caching, rate limits, health checks, integrity verification and fallback adapters may compensate for ordinary service limitations.
9. **Code cannot manufacture hard controls.** Software glue cannot replace missing legal/broker permission, required data localization, trustworthy secret custody, durable recovery or an unavailable security primitive.
10. **Free/trial/grant is not production evidence.** Promotional capacity does not imply SLA, long-term availability, legal suitability or production acceptance.
11. **No accidental overage.** Free/grant pilots require a hard spend cap or equivalent fail-closed budget control before provider apply; automatic paid overage is forbidden by default.
12. **Portability remains mandatory.** GitHub stays engineering source of truth; provider-specific adapters/IaC must not turn a free service into irreversible lock-in.
13. **Mutable facts are revalidated.** Free quotas, grants, tariffs, regions, API/IaC support and service limitations are checked against current official documentation immediately before use or purchase.

## 3. WP22A cost ladder

### Stage 0 — zero recurring proof-of-product

Target OWNER out-of-pocket recurring cost: **0 RUB/month**.

Use already-owned GitHub + accepted Lenovo engineering/acceptance capability to prove the product behavior. Lenovo is **not** public production. An optional cloud free-tier preview may be added only through source-controlled deployment and only with synthetic/non-private data until its security/legal boundary is accepted.

No real public user registration, real tenant-private payload, broker credential or public T-Invest connector is authorized merely because a free preview exists.

### Stage 1 — free/grant hosted pilot

Target OWNER out-of-pocket recurring cost: **0 RUB/month**.

Prefer current eligible free tiers, grants and provider bonuses. A hard spend cap / no-overage boundary is mandatory. This stage is for validation and measured capacity evidence; it is not automatically a production claim.

### Stage 2 — minimum safe paid pilot

Only if Stages 0/1 cannot safely satisfy the owning gate.

Provider and topology remain **unselected until a fresh official comparison immediately before apply**. Select the lowest-cost option that meets all hard requirements, size it from measured load and obtain explicit OWNER approval of the recurring cap and delete/shutdown path.

### Stage 3 — HA production scale-up

Scale to a high-availability topology only when measured SLA/load/failure-budget/user demand requires it. The current Cloud.ru multi-AZ reference is retained as a strong HA design, **not as the initial spend commitment**.

## 4. Permanent safety

This cost discipline never weakens:

- `app:app`;
- `trading_methods=false`;
- `REAL_TRADING_ENABLED=false`;
- tenant isolation;
- secret exclusion from GitHub/CI/artifacts;
- T-Invest public connector fail-closed pending broker permission;
- protected V9 rollback;
- exact-head GREEN / squash merge / post-merge Regression Shield discipline.

A cheaper service that cannot satisfy a hard gate is **not** the better option for Omni-CIO.
