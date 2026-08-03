# 00 — OMNI-CIO PROJECT MASTER CONTEXT

Дата актуализации: 2026-08-03

Этот файл хранит короткую долговременную память **одного проекта**: личного Custom GPT Omni-CIO и его Gateway для T-Invest.

## 1. Поддерживаемый продукт

Единственный пользовательский интерфейс:

`Omni-CIO API | Управляющий и аналитик v8.6.1`

Current production GPT behavior: **v8.6.1 Compact**.

```text
Custom GPT → Omni-CIO Gateway (`app:app`, Render Free)
                    │
                    ├→ TINVEST_TOKEN → production read-only
                    ├→ TINVEST_SANDBOX_TOKEN → optional T-Invest Sandbox
                    ├→ TINVEST_TRADING_TOKEN → confirmed narrow real LIMIT BUY/SELL
                    └→ Upstash Redis Free → durable real-execution journal
```

GitHub хранит backend-код и эталон GPT configuration. Render запускает Gateway. GPT Editor хранит фактически применённые Instructions/Knowledge/Bearer configuration и не синхронизируется с GitHub автоматически.

## 2. Production baseline — v8.6.1 COMPLETE

- Canonical GPT Editor Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`.
- Full v8.6 reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`.
- UI name: `Omni-CIO API | Управляющий и аналитик v8.6.1`.
- Recommended model: Thinking 5.6.
- Timezone: Europe/Moscow / MSK.
- Production endpoint: `https://omni-cio-gateway.onrender.com`.
- Render plan: Free.
- Entrypoint: `app:app`.
- Production Knowledge: exactly 10 canonical files.
- `REAL_TRADING_ENABLED=false` remains master rollback.

Owner Phase 3 + kill-switch drill completed on 2026-08-03.

Owner Phase 4 also completed on 2026-08-03:

- one controlled real SBER LIMIT BUY submitted exactly once;
- broker reconciled to `EXECUTION_REPORT_STATUS_FILL`;
- 1/1 lot executed at 280.55 RUB;
- commission reconciled at 0.84 RUB;
- portfolio reconciled to SBER 1 share / 1 lot;
- operations reconciled purchase + commission;
- exact confirmation replay created no second submit.

**v8.6.1 real BUY/SELL v1 Definition of Done is 100% complete.**

Exact current status: `knowledge/16_CURRENT_PROGRAM_STATUS.md`.

## 3. Active owner-approved program — v9 Portfolio Autopilot

Canonical program:

`docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`

Supporting engineering research:

`docs/architecture/V9_RESEARCH_AND_ENGINEERING_PRINCIPLES.md`

Tracker:

GitHub issue #175 — `EPIC: Omni-CIO v9 Portfolio Autopilot / Capital Management Engine`.

Program goal:

- ordinary human language as the primary portfolio interface;
- autonomous read-only data collection, universe discovery, screening and research;
- versioned Investment Policy Statement;
- structured credit/rating/default analysis;
- fund look-through/X-Ray;
- deterministic candidate funnel, risk engine, strategy selector and optimizer;
- immutable portfolio plans with before/after risk/cash/costs;
- read-only Watchtower monitoring;
- minimal owner intervention for routine development and analysis;
- explicit owner authorization retained for high-impact real-money writes.

Until the v9 Definition of Done is complete, this is the mandatory roadmap priority except critical production/security/API/dependency maintenance.

Current development starts at **WP0 — Baseline freeze and recovery correctness**.

## 4. v9 target architecture

```text
Human language
→ Natural Language CIO Router / Task Orchestrator
→ Portfolio State + IPS
→ Market Universe + deterministic Candidate Funnel
→ Research/Evidence + Credit + Fund X-Ray
→ Risk + Strategy + Optimizer
→ Immutable Portfolio Plan + Final Review
→ protected confirmed execution boundary
→ reconciliation + journal + Watchtower
```

Critical financial calculations, constraints and execution gates belong in deterministic Gateway code. The LLM interprets intent, synthesizes research and explains results; it does not bypass server policy.

## 5. Broker capability contours

### Production read-only

- health / connection;
- portfolio/enriched positions;
- instrument search;
- instrument/portfolio market snapshots;
- portfolio analytics;
- cash/liquidity diagnostics;
- purchase-capacity preview;
- operations history/analytics/reconciliation;
- broker-report reconciliation;
- final decision review.

### Sandbox

Uses only `TINVEST_SANDBOX_TOKEN`; virtual account/funding/portfolio and confirmed virtual BUY/SELL remain isolated with `real_money=false`.

### Real execution v1

Conditional Actions:

- `getRealTradingStatus`;
- `prepareRealTrade`;
- `executeRealTrade`;
- `getRealOrderState`.

Current real v1 remains narrow:

- BUY/SELL only;
- supported cash share/ETF;
- RUB;
- LIMIT/CURRENCY/DAY;
- own-funds BUY / own-position SELL;
- fresh trusted market;
- hard caps;
- immutable proposal;
- exact owner confirmation in a separate turn;
- UUID idempotency;
- no automatic retry after possible submit;
- broker reconciliation required.

v9 planning text does not automatically authorize broader mutations.

## 6. Absolute safety boundary

Always preserve unless separately threat-modeled, implemented, tested and owner-accepted:

- `TINVEST_TOKEN` remains read-only;
- separate non-transfer trading credential;
- masked account IDs;
- own-funds BUY / own-position SELL;
- no margin/short by default;
- stale/incomplete/contradictory critical data fail closed;
- exact decimal money logic;
- submit is not fill without broker proof;
- ambiguous writes are not automatically retried;
- durable journal + idempotency + kill switch remain required;
- no withdrawal/transfer authority as a portfolio-management convenience.

## 7. Durable real-execution state

Production backend:

```text
REAL_TRADING_JOURNAL_BACKEND=upstash
UPSTASH_REDIS_REST_URL=<Render Environment>
UPSTASH_REDIS_REST_TOKEN=<Render secret>
```

Properties accepted in v8.6.1:

- survives Render sleep/deploy/restart;
- HMAC-authenticated metadata/proposals/day counters;
- atomic Redis Lua compare-and-swap;
- no fallback to memory on durable-storage failure;
- no broker/Gateway/Upstash secrets stored in proposal data.

## 8. GPT behavior baseline and v9 direction

Current v8.6.1 `УПРАВЛЯЙ ПОРТФЕЛЕМ` starts:

`getPortfolioSnapshot → getCashLiquiditySnapshot → getPortfolioAnalytics → analysis`

This is analysis, not trade authorization.

v9 will make user interaction substantially simpler: ordinary Russian phrases map to typed workflows internally. The user should not need Action names, UIDs or API syntax for normal portfolio management.

## 9. Market / sizing rules

- last price != guaranteed execution price;
- fresh executable market required for real proposal;
- stale/partial critical market data blocks execution;
- `withdraw_limits` != buying budget;
- technical affordability != personal strategy sizing;
- capital scaling and server execution caps are separate control planes;
- margin capacity does not authorize sizing under current policy.

## 10. Secrets

Render only:

- `TINVEST_TOKEN`;
- `TINVEST_SANDBOX_TOKEN`;
- `TINVEST_TRADING_TOKEN`;
- `GATEWAY_API_KEY`;
- `UPSTASH_REDIS_REST_URL`;
- `UPSTASH_REDIS_REST_TOKEN`.

Never commit values or expose them in GPT responses, issues, PRs or Knowledge.

## 11. Runtime dependency warning

Current `app.py` still depends on `app_v371.py`, `app_v360.py` and wrapper/core files. Do not delete them as legacy without compatibility refactor and full Regression Shield.

## 12. Canonical files

- `README.md` — production overview.
- `AGENTS.md` — mandatory engineering + active program-lock rules.
- `SECURITY.md` — security boundary.
- `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md` — active Release-2 roadmap.
- `docs/architecture/V9_RESEARCH_AND_ENGINEERING_PRINCIPLES.md` — research/design lessons.
- `knowledge/16_CURRENT_PROGRAM_STATUS.md` — current WP/status.
- `gpt/SETUP_INDEX.md` — current production setup/recovery entry.
- `gpt/CONFIGURATION.md` — GPT UI/config registry.
- `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt` — current production Instructions.
- `gpt/knowledge/` — current production Knowledge.
- `gpt/ACTIONS_CATALOG.md` — Action catalog.
- `docs/operations/REAL_TRADING_RELEASE_RUNBOOK.md` — real release procedure/evidence.

## 13. Git workflow

Significant changes:

`branch → PR → exact-head Regression Shield/security → review → squash merge → external acceptance when needed`

Do not bypass CI for broker-write, policy, orchestration, optimization, research-safety or durable-state code.

## 14. Current readiness

Production v8.6.1:

- read-only: accepted;
- Sandbox: accepted;
- real BUY/SELL v1: accepted and complete.

Development:

- v9 Portfolio Autopilot is the active program;
- WP0 is the current work package;
- no unfinished v9 behavior may be claimed as production-ready or silently applied to GPT Editor.
