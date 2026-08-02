# Структура репозитория Omni-CIO

Репозиторий организован вокруг одного продукта: Custom GPT Omni-CIO и его read-only Gateway.

## Каноническое дерево

```text
omni-cio-gateway/
├── app.py                         # production Gateway wrapper / app:app
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
│   ├── market/                    # read-only market/macro/rating sources
│   ├── analytics/                 # analytics modules
│   ├── risk/                      # risk/scenario layers
│   ├── decision/                  # decision layers
│   ├── observability/             # safe telemetry/evidence
│   └── release/                   # read-only release/final-review chain
│
├── gpt/
│   ├── SETUP_INDEX.md             # single setup/update/recovery entrypoint
│   ├── CONFIGURATION.md           # GPT Editor registry
│   ├── CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt
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
│   ├── master-plan/               # original Omni-CIO specification
│   ├── architecture/              # active architecture/contracts
│   └── operations/                # deploy/release/acceptance runbooks
├── tests/                         # regression/contracts/security tests
├── scripts/                       # CI/security/repository checks
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

## Runtime rule

Корневые wrapper files не являются мусором, пока их импортирует current runtime.

`app.py` в текущей release chain использует `app_v371.py`, `app_v360.py` и `main.py`. Удалять/перемещать их можно только отдельным compatibility refactor после изменения imports, OpenAPI/auth behavior and full Regression Shield.

## `gpt/`

`gpt/` хранит воспроизводимую конфигурацию Custom GPT.

Правила:

- один setup entrypoint: `SETUP_INDEX.md`;
- один production Instructions file: `CUSTOM_GPT_INSTRUCTIONS_V8_4_1.txt`;
- ровно 10 production Knowledge files;
- production endpoint only: `https://omni-cio-gateway.onrender.com`;
- GitHub не синхронизирует GPT Editor автоматически.

## `knowledge/`

Engineering/domain memory остаётся только там, где она помогает поддерживать current runtime, safety, data quality или roadmap state.

- `00_` — durable project context;
- domain-specific files — market/operations/report/security/contracts;
- `16_` — current accepted status.

Production GPT Knowledge берётся **не из root `knowledge/`**, а из `gpt/knowledge/`.

## `docs/master-plan/`

Master plan сохраняется, потому что напрямую описывает развитие Omni-CIO. Это historical/source specification, а не доказательство текущей реализации.

## `docs/architecture/`

Здесь остаются contracts/ADRs, связанные с существующим Gateway and analytical layers. Датированные duplicate inventories/audits не являются обязательной частью структуры.

## `docs/operations/`

Хранят только procedures, необходимые для текущего Gateway/GPT lifecycle: deployment, release, live read-only acceptance, CI runner/recovery where applicable.

## `.github/`

Постоянный Regression Shield и repository governance. One-off patch/bootstrap workflows не остаются в `main`.

## `tests/`

Тесты должны доказывать реальные current invariants, а не поддерживать удалённые historical integrations.

Критически проверять:

- GET-only Action surface;
- `app:app`;
- `trading_methods=false`;
- no broker write methods;
- auth/OpenAPI;
- monetary/data-quality logic;
- broker-report/operations/portfolio flows;
- current market/risk/release contracts.

## Dependencies

- direct constraints: `requirements.in`, `requirements-dev.in`;
- generated hash-locked projections: `requirements.txt`, `requirements-dev.txt`;
- locks не редактируются вручную;
- dependencies unrelated to current runtime must not be added.

## Cleanup rule

Перед удалением любого файла:

1. проверить imports;
2. проверить tests;
3. проверить CI/scripts;
4. проверить Render/GPT configuration;
5. проверить docs/knowledge references;
6. удалить только в отдельной branch/PR;
7. выполнить full Regression Shield.

Название `legacy`, `old`, `archive` или версия в filename само по себе не доказывает, что файл безопасно удалить.
