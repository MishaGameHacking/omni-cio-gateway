# Структура репозитория Omni-CIO

Репозиторий организован вокруг одного продукта:

`Omni-CIO Custom GPT → Omni-CIO Gateway → T-Invest API`

Applied production GPT: **v9.0.0**, owner-accepted in place on 2026-08-05.  
Protected rollback: **v8.6.1**.  
Completed canonical program: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`.  
Current mode: **controlled maintenance**.

## Каноническое дерево

```text
omni-cio-gateway/
├── app.py                         # production wrapper / app:app
├── app_v371.py                    # current compatibility dependency
├── app_v360.py                    # current compatibility dependency
├── main.py                        # current FastAPI/auth/read-only core dependency
├── portfolio_market.py
├── portfolio_analytics.py
├── cash_liquidity.py
├── purchase_capacity.py
├── purchase_capacity_integrity.py
├── operations_analytics.py
├── sdk_order_compat.py
├── broker_report_reconciliation/  # Gateway extension hook / broker reports
├── omni_cio/
│   ├── contracts/                 # typed/versioned contracts
│   ├── adapters/                  # compatibility/read adapters
│   ├── quality/                   # quality/freshness validation
│   ├── market/                    # read-only market/macro sources
│   ├── analytics/                 # analytics modules
│   ├── router/                    # natural-language CIO routing
│   ├── policy/                    # IPS/readiness
│   ├── universe/                  # investable universe
│   ├── candidates/                # deterministic funnel
│   ├── research/                  # evidence/research
│   ├── credit/                    # credit/rating/default
│   ├── funds/                     # Fund X-Ray
│   ├── risk/                      # portfolio risk
│   ├── strategy/                  # meta-strategy
│   ├── optimizer/                 # capital scaling/optimizer
│   ├── plans/                     # immutable plans
│   ├── plan_execution/            # safe staged plan execution
│   ├── decision_journal/          # append-only decision/evaluation journal
│   ├── watchtower/                # read-only monitoring
│   ├── observability/             # safe telemetry/evidence
│   ├── release/                   # release/live-authority checks
│   ├── sandbox/                   # isolated virtual T-Invest Sandbox execution
│   └── real_trading/              # exact-owner-confirmed Real BUY/SELL
│
├── gpt/
│   ├── SETUP_INDEX.md             # single setup/update/recovery entrypoint
│   ├── CONFIGURATION.md           # applied GPT registry
│   ├── CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt
│   ├── KNOWLEDGE_MANIFEST_V9_0_0.md
│   ├── CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt  # protected rollback
│   ├── ACTIONS_CATALOG.md
│   ├── SECRETS_AND_RENDER.md
│   ├── MY_GPT_SETUP_RUNBOOK.md
│   ├── BOT_ONLY_FILE_MANIFEST.md
│   ├── PROJECT_INSTRUCTIONS.md
│   ├── NEW_CHAT_PROMPT.md
│   └── knowledge/                 # exactly 10 applied Knowledge files
│
├── knowledge/                     # engineering/domain project memory
├── docs/
│   ├── master-plan/               # completed locked v9 program + source spec
│   ├── architecture/              # active architecture/contracts
│   └── operations/                # deploy/release/acceptance/maintenance runbooks
├── tests/                         # regression/contracts/security tests
├── scripts/                       # CI/security/recovery consistency checks
├── .github/                       # workflows/templates/governance/Dependabot
├── render.yaml                    # single production Render contract
├── requirements.in                # runtime direct constraints
├── requirements.txt               # generated hash-locked runtime set
├── requirements-dev.in            # CI/test/security direct constraints
├── requirements-dev.txt           # generated hash-locked dev set
├── pyproject.toml
├── .env.example
├── README.md
├── AGENTS.md
└── SECURITY.md
```

One-time bootstrap payloads and generated CI projection files are not part of the canonical tree and must not be committed after their task is complete.

## Runtime rule

Root wrapper files are current dependencies, not removable legacy.

`app.py` still uses `app_v371.py`, `app_v360.py` and `main.py`. Moving/removing them requires a separate compatibility refactor, import/OpenAPI/auth proof and full Regression Shield.

Stable Render entrypoint remains `app:app`.

## Broker contour isolation

Production architecture contains three deliberately isolated contours:

1. read-only via `TINVEST_TOKEN`;
2. optional Sandbox via `TINVEST_SANDBOX_TOKEN` and `omni_cio/sandbox/`;
3. optional exact-owner-confirmed real execution via `TINVEST_TRADING_TOKEN`, `omni_cio/real_trading/` and durable state.

The production read-only credential is never a fallback for Real execution. The reviewed Real contour does not permit transfers, margin, shorts, MARKET/BESTPRICE, stop/replace/async or autonomous recurring real-money execution.

## `gpt/`

`gpt/` stores the reproducible configuration and recovery assets for the **existing** applied v9 GPT.

Rules:

- one setup entrypoint: `gpt/SETUP_INDEX.md`;
- applied Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V9_0_0_COMPACT.txt`;
- exact Knowledge registry: `gpt/KNOWLEDGE_MANIFEST_V9_0_0.md`;
- protected rollback Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- exactly 10 applied Knowledge files;
- production endpoint: `https://omni-cio-gateway.onrender.com`;
- GitHub does not synchronize GPT Editor automatically.

Owner acceptance of the existing GPT is recorded in completed issue #216 and epic #176.

## `knowledge/`

Engineering/domain memory remains only where it supports current runtime, safety, data quality or maintenance continuity.

- `00_PROJECT_MASTER_CONTEXT.md` — long-lived project context;
- domain-specific files — market/operations/report/security/contracts;
- `16_CURRENT_PROGRAM_STATUS.md` — current applied/repository state.

Production GPT Knowledge comes from `gpt/knowledge/`, not root `knowledge/`.

## `docs/master-plan/`

`OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md` is the completed owner-approved/program-locked v9 specification and audit trail. It remains recovery/history authority for what was approved; current code/tests/status determine the active implementation state.

## `docs/architecture/`

Contains active contracts and ADRs. Protected baseline/migration contract:

`docs/architecture/V9_BASELINE_AND_RECOVERY_CONTRACT.md`.

Do not create duplicate inventory/audit documents when an existing source of truth should be updated.

## `docs/operations/`

Contains procedures required for the current Gateway/GPT lifecycle, including deployment, Real release, durable state, Watchtower, live authority acceptance, dependency maintenance and recovery.

## `.github/`

Permanent Regression Shield and repository governance. One-off patch/bootstrap workflows must not remain in `main`. Dependabot is a proposal generator; no dependency update is authorized until current-main exact-head CI/security succeeds.

## `tests/` and `scripts/`

Tests/scripts must prove current invariants, including:

- stable `app:app` and auth/OpenAPI;
- baseline read-only/Sandbox/Real isolation;
- exact confirmation and idempotent execution safety;
- durable journal fail-closed behavior;
- monetary/data-quality logic;
- broker-report/operations/portfolio flows;
- current market/risk/release contracts;
- GPT v9 recovery/version/Knowledge consistency;
- live deployed OpenAPI authority without protected mutation calls;
- post-v9 repository hygiene.

Regression CI must not call live T-Invest or protected Render Actions. The separate live-authority workflow performs public `/health` and `/openapi.json` GET checks only.

## Dependencies

Canonical sources remain at repository root because Render and CI consume them there:

- `requirements.in` — runtime direct constraints;
- `requirements.txt` — generated/hash-locked runtime dependency set;
- `requirements-dev.in` — CI/test/security direct constraints;
- `requirements-dev.txt` — generated/hash-locked development dependency set.

Lock files are generated from `.in` sources and verified by Regression Shield. Generated Windows projection files are CI artifacts and are not committed. Known-incompatible toolchain versions are held narrowly in Dependabot policy rather than weakening lock verification.

## Maintenance rule

Every maintenance package follows:

`branch → focused change → deterministic tests/guards → exact-head Regression Shield/security → zero unresolved review threads → squash merge`.

If a change alters GPT Editor state or the reviewed Action contract, owner Preview/Update acceptance on the **same** GPT is additionally required.

## Cleanup rule

Before deleting or moving any existing file:

1. check imports;
2. check tests/CI/scripts;
3. check Render/GPT configuration;
4. check docs/knowledge references;
5. prove the replacement path;
6. use a separate branch/PR;
7. run full Regression Shield.

A filename containing `legacy`, `old`, `archive` or a version number is not evidence that it is safe to delete.
