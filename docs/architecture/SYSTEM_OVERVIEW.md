# Архитектура Omni-CIO

Status: **Amendment 20 / PR #584 branch-local convergence authority**  
Current checkpoint: **V9C-B / DETERMINISTIC_SOURCE_RELOCATION**  
Accepted-main progress and deployment state: `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`

## 1. One product / one forward runtime

Omni-CIO has one forward V10 product line. The repository no longer treats V9, Render, Cloudflare, Neon, Cloud.ru or VK ID as competing future platforms.

The selected forward application composition is:

```text
ChatGPT
   ↓ engineering / analysis
GitHub
   ↓ source / review / CI / exact-SHA provenance
Timeweb App Platform
   ↓ apps.api.hosted_runtime:create_app
Omni-CIO V10 Web + API
   ↓ verified identity
Telegram Login only
   ↓ server-side account/session
OmniCIOUserAccount -> Tenant
   ↓ tenant-scoped persistence
Timeweb PostgreSQL 18 after TW-D cutover
```

This diagram is the target/source authority. TW-B does not itself deploy Timeweb, perform the production PostgreSQL cutover, mutate DNS/TLS or activate public users.

## 2. Current source composition

The Timeweb-targeted container is built by the repository-root `Dockerfile`.

Its backend entrypoint is `apps.api.hosted_runtime:create_app`.

The Docker runtime exposes port `8080`. Process liveness uses `/livez`; database readiness remains a separate `/healthz` concern. Runtime variables and secrets are provided outside the image.

The canonical Web source remains `apps/web/`; the Docker build produces its static assets and copies them into the final Python runtime image.

## 3. Canonical financial/domain ownership after V9C-B

V9C-B relocates the remaining deterministic V9 root implementations without changing their reviewed financial semantics:

| Capability | Canonical V10 source |
|---|---|
| Portfolio market snapshot | `omni_cio/portfolio/market_source_v1.py` |
| Portfolio structure analytics | `omni_cio/analytics/portfolio_source_v1.py` |
| Cash/liquidity diagnostics | `omni_cio/analytics/cash_liquidity_v1.py` |
| Operations analytics | `omni_cio/analytics/operations_source_v1.py` |
| Purchase capacity | `omni_cio/pretrade/purchase_capacity_v1.py` |
| Purchase-capacity integrity | `omni_cio/pretrade/purchase_capacity_integrity_v1.py` |
| Sale capacity | `omni_cio/pretrade/sale_capacity_v1.py` |
| Sale-capacity normalization | `omni_cio/pretrade/sale_capacity_normalization_v1.py` |
| T-Invest read-only request compatibility | `omni_cio/adapters/tinvest_order_compat_v1.py` |
| Broker-report reconciliation | `omni_cio/reconciliation/` |

The migration preference remains `REUSE_AS_IS > WRAP_ADAPTER > EXTRACT_TO_CORE > REWRITE_REQUIRED > RETIRE`.

Relocation does not grant broker-write authority and does not change money formulas.

## 4. Temporary V9 compatibility boundary

The following root files still exist only because V9C-C has not completed: `app.py`, `app_v360.py`, `app_v371.py`, and `main.py`.

They are migration/recovery inputs, not permanent parallel architecture. V9C-C must move every still-supported runtime/API behavior into the Timeweb V10 composition, prove parity, prove zero current consumers and preserve recovery before retiring them.

Historical Render deployment/configuration and V9 GPT/provider artifacts are handled by the later V9C-D/V9C-E retirement gates. Git history is the immutable historical archive.

## 5. Identity, tenant and session boundary

Ordinary browser access is `Telegram USER OIDC Login -> verified identity -> internal user -> isolated Tenant -> server-side Session`.

Telegram is login identity only. Bot chat, `/start`, Bot API identity or possession of a bot token cannot select a tenant or mint a product session.

Tenant authority is derived server-side. Browser payloads, query parameters and frontend filtering are never tenant security boundaries. PostgreSQL RLS/FORCE-RLS and cross-tenant negative tests remain mandatory.

## 6. Data and persistence boundary

Timeweb PostgreSQL 18 is the selected relational target. Production DB cutover belongs to TW-D and remains fail-closed until migration, backup/restore, least-privilege, schema/RLS and cross-tenant evidence pass.

Container-local filesystem state is not authoritative persistence. Durable product state must remain in the reviewed external persistence boundary.

## 7. Broker and money authority

Broker READ and broker WRITE remain separate capabilities. Protected invariants during V9C-A through V9C-F: broker write OFF; `trading_methods=false`; `REAL_TRADING_ENABLED=false`; no transfer/withdrawal, margin/leverage or uncovered-short authority; no shared/global USER broker credential; raw credentials never enter GitHub, CI artifacts, browser storage or logs.

A GitHub merge, Timeweb deployment, Telegram login or AI output never grants broker submit authority.

## 8. CI and release provenance

GitHub is source/review/CI/provenance authority. Every material checkpoint follows the exact-head rule: `fresh base -> focused implementation -> focused preflight -> exact-head CI -> only success is GREEN`.

Any content-changing commit invalidates earlier final check evidence. The forward release chain after its owning gates is `accepted main SHA -> GitHub checks -> immutable Timeweb candidate -> production verification`.

## 9. V9-to-V10 convergence sequence in PR #584

1. V9C-A — authority and inventory — `CERTIFIED_GREEN`.
2. V9C-B — deterministic source relocation — current.
3. V9C-C — runtime entrypoint convergence.
4. V9C-D — GPT and retired-provider working-tree retirement.
5. V9C-E — CI/recovery convergence.
6. V9C-F — whole-tree legacy absence proof.

A later functional checkpoint does not begin until the current published checkpoint is `CERTIFIED_GREEN`.

## 10. Current non-goals

TW-B / V9C-B does not deploy/promote Timeweb production, cut over production PostgreSQL, change DNS/TLS, activate public Telegram login, start WEB-VISUAL/WP23+, or enable broker writes/Real-money execution.

PR #584 must not merge to `main` without a new explicit OWNER instruction.
