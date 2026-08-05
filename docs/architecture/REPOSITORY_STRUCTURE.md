# Структура репозитория Omni-CIO

Статус: **V10 WP1 — repository architecture authority**  
Current production/recovery runtime: **Omni-CIO v9.0.0**  
Active feature program: **Omni-CIO V10**

## 1. Главный принцип

Репозиторий организован вокруг **одного продукта и одного финансового Core**.

V10 не создаёт второй независимый бот/сайт/Gateway. Текущий V9 runtime сохраняется как compatibility/recovery layer, а новые Web, Telegram, AI и infrastructure-компоненты подключаются к одному Core по мере прохождения своих Work Packages.

Инженерный source of truth — private GitHub repository. Ни ChatGPT-аккаунт, ни Lenovo, ни hosting dashboard, ни IDE не являются владельцем проекта.

## 2. Current accepted physical tree

Пока соответствующий V10 Work Package не провёл безопасную миграцию, текущая физическая структура V9 остаётся рабочей:

```text
omni-cio-gateway/
├── app.py                         # production wrapper / app:app
├── app_v371.py                    # current compatibility dependency
├── app_v360.py                    # current compatibility dependency
├── main.py                        # current FastAPI/auth/Gateway dependency
├── portfolio_market.py
├── portfolio_analytics.py
├── cash_liquidity.py
├── purchase_capacity.py
├── purchase_capacity_integrity.py
├── operations_analytics.py
├── sdk_order_compat.py
├── broker_report_reconciliation/
├── omni_cio/                      # deterministic financial Core/domain packages
├── gpt/                           # current applied GPT configuration/recovery
├── knowledge/                     # engineering/domain project memory
├── docs/
│   ├── master-plan/
│   ├── architecture/
│   └── operations/
├── tests/
├── scripts/
├── .github/
├── render.yaml                    # current V9 production deployment contract
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

Root wrappers are **not legacy merely because they have versioned names**. `app.py` still depends on current compatibility paths; moving/removing them requires the responsible later V10 migration package and full regression proof.

Stable V9 entrypoint remains `app:app` until explicitly retired by an accepted V10 deployment migration.

## 3. Canonical V10 target ownership

V10 reserves the following top-level ownership model:

```text
omni-cio-gateway/
│
├── apps/                          # presentation / transport adapters only
│   ├── api/                       # V10 API application adapter
│   ├── web/                       # V10 Web application
│   └── telegram/                  # V10 Telegram adapter
│
├── omni_cio/                      # ONE deterministic financial Core
│   ├── contracts/
│   ├── adapters/
│   ├── quality/
│   ├── analytics/
│   ├── market/
│   ├── router/
│   ├── policy/
│   ├── universe/
│   ├── candidates/
│   ├── research/
│   ├── credit/
│   ├── funds/
│   ├── risk/
│   ├── decision/
│   ├── strategy/
│   ├── optimizer/
│   ├── plans/
│   ├── plan_execution/
│   ├── watchtower/
│   ├── decision_journal/
│   ├── observability/
│   ├── release/
│   ├── sandbox/
│   └── real_trading/
│
├── ai/                            # V10 AI policy/provider/RAG/evals/orchestrator
│   ├── providers/                 # created by Block G when authorized
│   ├── prompts/
│   ├── schemas/
│   ├── rag/
│   └── evals/
│
├── infrastructure/                # replaceable runtime/deployment infrastructure
│   ├── windows/                   # Lenovo/bootstrap/services
│   ├── deployment/
│   ├── backup/
│   └── health/
│
├── gpt/                           # retained migration/recovery source until parity gate
├── knowledge/                     # repository-safe engineering memory
├── docs/
├── tests/
├── scripts/
└── .github/
```

### Important

`apps/`, `ai/` and `infrastructure/` are **reserved roots**, not permission to implement them early. They are created only by the Work Package that owns their runtime responsibility. WP1 defines their location and boundaries; it does not create the Web, Telegram, AI or Lenovo runtime.

## 4. Why `omni_cio/` remains the Core root

V10 does **not** perform a cosmetic wholesale move from existing `omni_cio/<domain>` packages into a new `omni_cio/core/` wrapper merely to make the tree look newer.

The existing reviewed domain packages already are the financial Core. Moving hundreds of imports before there is a functional need would create migration risk without product value.

Therefore:

- `omni_cio/` is the canonical deterministic Core root;
- domain packages remain at their existing stable paths until an evidence-backed package needs a specific move;
- future transport/UI/AI code stays outside the financial Core in its reserved adapter roots;
- compatibility wrappers remain until explicit retirement evidence exists.

## 5. Ownership matrix

| Repository area | Authority / purpose | May own financial business logic? | May own broker-write secret? |
|---|---|---:|---:|
| `omni_cio/` | deterministic Core | yes | only isolated execution service as later approved |
| `omni_cio/real_trading/` | low-level Personal Real authority | narrow execution only | yes, runtime-only access |
| `omni_cio/plan_execution/` | immutable staged execution lifecycle | narrow plan execution | no raw secret storage |
| `apps/api/` | V10 API adapter | no duplicate calculations | no |
| `apps/web/` | Web UI | no | no |
| `apps/telegram/` | alerts/entry adapter | no | Telegram token only at runtime, not broker token |
| `ai/` | AI/RAG/orchestration/evals | no canonical money calculations | no |
| `infrastructure/` | bootstrap/deploy/backup/health definitions | no | no committed secrets |
| `gpt/` | current GPT migration/recovery source | no new Core logic | no |
| `knowledge/` | repository-safe project/domain memory | no runtime authority | no |
| `docs/` | architecture/program/runbooks | no runtime authority | no |
| `.github/` | review/CI/control-plane automation | no | no broker secrets |

`CODEOWNERS` explicitly covers these areas. CODEOWNERS is reviewer/ownership metadata, not a substitute for runtime authorization.

## 6. Single-authority rules

The repository must keep exactly one canonical implementation of each critical authority.

Examples:

- one deterministic Core root: `omni_cio/`;
- one direct Real package: `omni_cio/real_trading/`;
- one safe plan-execution lifecycle: `omni_cio/plan_execution/`;
- one Sandbox package: `omni_cio/sandbox/`;
- one canonical Web application: future `apps/web/`;
- one Telegram adapter: future `apps/telegram/`;
- one AI orchestration stack: future `ai/`;
- one V10 progress authority: `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

Forbidden competing top-level roots include ad-hoc `frontend/`, `website/`, `telegram_bot/`, `backend/`, `server/`, `omni_cio_v10/` or a second top-level `execution/` stack.

## 7. Import / authority boundaries

### Core

Core packages may depend on shared contracts and reviewed lower-level services, but critical package cycles are forbidden by the V10 repository-boundary guard.

### Web / Telegram / AI

- presentation/AI adapters must not import `omni_cio.real_trading` directly;
- AI, Web and Telegram must not own the plan-execution authority;
- AI never receives direct broker-write credentials;
- future API exposure must call reviewed Core/service interfaces rather than reimplementing sizing/risk/approval logic;
- a later explicit API work package may expose a reviewed approval/execution facade, but direct broker client access from UI/AI remains forbidden.

## 8. Machine-checked repository guard

Permanent V10 structural boundary checker:

`scripts/check_v10_repository_boundaries.py`

It checks at minimum:

- canonical V10 authority files exist;
- protected V9 compatibility paths remain present;
- no competing top-level V10 application/runtime tree appears;
- Real and plan-execution authority roots are unique;
- future Web/Telegram/AI adapters cannot import low-level Real authority directly;
- critical Core package dependency graph contains no circular package dependency;
- explicit CODEOWNERS coverage exists for V10 roots.

Regression Shield runs this checker on every significant PR.

## 9. Move/delete protocol

Before moving/deleting any existing runtime or recovery path:

1. search imports/references;
2. inspect tests and fixture paths;
3. inspect CI/scripts;
4. inspect Render/current GPT/recovery docs;
5. determine the owning V10 WP;
6. document replacement/migration path;
7. preserve compatibility wrapper where needed;
8. add deterministic regression guard;
9. pass exact-head Regression Shield/security;
10. squash merge only after review blockers are zero.

A versioned filename is not evidence of obsolescence.

## 10. Account independence / developer portability

A new authorized developer must be able to:

`clone repository -> read AGENTS/Program Lock/current status/architecture -> install from locked dependencies -> run checks -> create focused branch -> PR -> CI -> reviewed deploy`

without access to the original ChatGPT account.

No authoritative Web/AI/Telegram application setting may exist only inside a personal account dashboard when it can be represented as repository-controlled schema/configuration.

Hosting/domain replacement is a deployment/configuration change, not creation of a new website/project.

Secret values remain a separate runtime provisioning process and are never implied by GitHub developer access.

## 11. Current V9 compatibility ownership

Until later V10 migration packages explicitly replace them:

- current Render production service remains V9;
- `app:app` remains stable;
- root wrappers remain dependencies;
- existing GPT v9.0.0 remains applied;
- `gpt/` remains a protected migration/recovery source;
- V9 broker execution invariants remain binding.

WP1 changes repository **structure authority and guardrails**, not production runtime behavior.

## 12. Development/test reproducibility boundary

The repository owns:

- dependency source/locks;
- CI workflows;
- safe example configuration;
- architecture/runbooks;
- future bootstrap/deployment definitions.

A developer workstation may cache dependencies/tools, but that cache is never source of truth.

Exact toolchain versions and the clean Windows setup path are finalized by WP2 and later Block C; WP1 only fixes where those artifacts belong.

## 13. Current delivery sequence

At accepted WP0 main:

- Block A = COMPLETE (5%);
- WP1 = current/next authorized package;
- WP2–WP4 remain blocked until their predecessors pass;
- Lenovo configuration remains Block C;
- Web/Telegram/AI runtime is still not authorized.

## 14. Cleanup rule

Do not create duplicate setup/configuration/inventory documents when this file or another canonical source can be updated. Historical audit records may remain when needed for traceability, but they cannot compete with current authority.
