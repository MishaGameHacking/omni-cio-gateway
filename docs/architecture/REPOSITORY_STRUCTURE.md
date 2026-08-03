# Структура репозитория Omni-CIO

Репозиторий организован вокруг одного продукта:

`Omni-CIO Custom GPT → Omni-CIO Gateway → T-Invest API`

Current production baseline: **v8.6.1**.  
Active roadmap: `docs/master-plan/OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md`.

## Каноническое дерево

```text
omni-cio-gateway/
├── app.py                         # production wrapper / app:app
├── app_v371.py                    # current compatibility dependency
├── app_v360.py                    # current compatibility dependency
├── main.py                        # current FastAPI/auth core dependency
├── portfolio_market.py
├── portfolio_analytics.py
├── cash_liquidity.py
├── purchase_capacity.py
├── purchase_capacity_integrity.py
├── operations_analytics.py
├── sdk_order_compat.py
├── broker_report_reconciliation/
├── omni_cio/
│   ├── contracts/                 # typed/versioned contracts
│   ├── adapters/                  # compatibility/read adapters
│   ├── quality/                   # quality/freshness validation
│   ├── market/                    # read-only market/macro sources
│   ├── analytics/                 # analytics modules
│   ├── risk/                      # risk/scenario layers
│   ├── decision/                  # decision/review layers
│   ├── observability/             # safe telemetry/evidence
│   ├── release/                   # release/final-review chain
│   ├── sandbox/                   # isolated T-Invest Sandbox execution
│   └── real_trading/              # narrow confirmed real BUY/SELL v1
│
├── gpt/
│   ├── SETUP_INDEX.md             # single setup/update/recovery entrypoint
│   ├── CONFIGURATION.md           # GPT Editor registry
│   ├── CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt
│   ├── CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt
│   ├── ACTIONS_CATALOG.md
│   ├── SECRETS_AND_RENDER.md
│   ├── MY_GPT_SETUP_RUNBOOK.md
│   ├── BOT_ONLY_FILE_MANIFEST.md
│   ├── PROJECT_INSTRUCTIONS.md
│   ├── NEW_CHAT_PROMPT.md
│   └── knowledge/                 # exactly 10 production upload files
│
├── knowledge/                     # engineering/domain project memory
├── docs/
│   ├── master-plan/               # locked v9 program + source specification
│   ├── architecture/              # active architecture/contracts
│   └── operations/                # deploy/release/acceptance runbooks
├── tests/                         # regression/contracts/security tests
├── scripts/                       # CI/security/recovery consistency checks
├── .github/                       # workflows/templates/governance
├── render.yaml                    # single production Render contract
├── requirements.in
├── requirements.txt
├── requirements-dev.in
├── requirements-dev.txt
├── pyproject.toml
├── .env.example
├── README.md
├── AGENTS.md
└── SECURITY.md
```

Future v9 packages add modules under the existing `omni_cio/` tree. Do not create a second product tree or duplicate Gateway.

## Runtime rule

Root wrapper files are current dependencies, not removable legacy.

`app.py` still uses `app_v371.py`, `app_v360.py` and `main.py`. Moving/removing them requires a separate compatibility refactor, import/OpenAPI/auth proof and full Regression Shield.

Stable Render entrypoint remains `app:app`.

## Broker contour isolation

Production architecture contains three deliberately isolated contours:

1. read-only via `TINVEST_TOKEN`;
2. optional Sandbox via `TINVEST_SANDBOX_TOKEN` and `omni_cio/sandbox/`;
3. optional confirmed real execution via `TINVEST_TRADING_TOKEN`, `omni_cio/real_trading/` and durable Upstash journal.

The presence of real execution modules does not permit transfers, margin, short, MARKET orders or autonomous recurring real-money execution.

## `gpt/`

`gpt/` stores the reproducible Custom GPT reference configuration.

Rules:

- one setup entrypoint: `gpt/SETUP_INDEX.md`;
- canonical production Instructions: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt`;
- full engineering reference: `gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_0.txt`;
- exactly 10 production Knowledge files;
- production endpoint: `https://omni-cio-gateway.onrender.com`;
- GitHub does not synchronize GPT Editor automatically.

The v9 program may change GPT configuration only at the relevant reviewed package; final v9 editor migration belongs to WP15.

## `knowledge/`

Engineering/domain memory remains only where it supports current runtime, safety, data quality or program continuity.

- `00_PROJECT_MASTER_CONTEXT.md` — long-lived project context;
- domain-specific files — market/operations/report/security/contracts;
- `16_CURRENT_PROGRAM_STATUS.md` — current accepted implementation/package status.

Production GPT Knowledge comes from `gpt/knowledge/`, not root `knowledge/`.

## `docs/master-plan/`

`OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md` is the active owner-approved/program-locked roadmap.

The source PDF/TXT master specification remains reference material and is not proof that future capability is implemented.

## `docs/architecture/`

Contains active contracts and ADRs. WP0 baseline/migration contract:

`docs/architecture/V9_BASELINE_AND_RECOVERY_CONTRACT.md`.

Do not create duplicate inventory/audit documents when an existing source of truth should be updated.

## `docs/operations/`

Contains procedures required for the current Gateway/GPT lifecycle, including deployment, real release, durable state and acceptance/recovery.

## `.github/`

Permanent Regression Shield and repository governance. One-off patch/bootstrap workflows must not remain in `main`.

## `tests/` and `scripts/`

Tests/scripts must prove current invariants, including:

- stable `app:app` and auth/OpenAPI;
- read-only/Sandbox/Real isolation;
- exact confirmation and idempotent execution safety;
- durable journal fail-closed behavior;
- monetary/data-quality logic;
- broker-report/operations/portfolio flows;
- current market/risk/release contracts;
- GPT recovery/version/Knowledge consistency;
- each v9 package-specific exit contract.

CI tests must not call live T-Invest or Render.

## Dependencies

- direct constraints: `requirements.in`, `requirements-dev.in`;
- generated hash-locked projections: `requirements.txt`, `requirements-dev.txt`;
- lock files are not edited manually;
- dependencies unrelated to current runtime or an approved v9 package must not be added.

## v9 development rule

Each package follows:

`branch → architecture/data/threat contract → deterministic code → fake/unit/integration tests → security → exact-head Regression Shield → review → squash merge → required shadow/Sandbox/minimal-real acceptance`.

The protected v8.6.1 baseline remains available until the new package is accepted.

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
