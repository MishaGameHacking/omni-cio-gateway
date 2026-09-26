# Структура репозитория Omni-CIO

Статус: **V10 current physical-tree model / Amendment 20 V9C-B branch-local migration state**  
Forward V10 source runtime: **Timeweb-targeted `apps.api.hosted_runtime:create_app`**  
Compatibility/recovery migration input until V9C-C: **V9 `app:app`**  
Active feature program: **Omni-CIO V10**  
Dynamic progress/current WP: `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`

## 1. Главный принцип

Репозиторий организован вокруг **одного продукта и одного финансового Core**.

V10 не создаёт второй независимый бот/сайт/Gateway. Amendment 20 определяет V9 как migration source: полезная логика переносится в canonical V10 packages, а один forward application runtime собирается через `apps.api.hosted_runtime:create_app` для Timeweb. V9 wrappers сохраняются только до своего V9C-C parity/zero-consumer/recovery gate.

Инженерный source of truth — private GitHub repository. Ни ChatGPT-аккаунт, ни Lenovo, ни hosting dashboard, ни IDE не являются владельцем проекта.

## 2. Current accepted physical tree

Текущая branch-local V9C-B структура содержит временные V9 runtime wrappers и уже relocated deterministic V10 sources. Упрощённое дерево:

```text
omni-cio-gateway/
├── app.py                         # V9C-C migration/recovery input
├── app_v371.py                    # V9C-C compatibility input
├── app_v360.py                    # V9C-C compatibility input
├── main.py                        # V9C-C Gateway/auth migration input
│
├── omni_cio/                      # ONE deterministic financial Core/domain packages
│   ├── portfolio/                 # relocated market/portfolio source
│   ├── analytics/                 # relocated portfolio/cash/operations analytics
│   ├── pretrade/                  # relocated purchase/sale capacity logic
│   ├── adapters/                  # relocated T-Invest SDK compatibility adapter
│   └── reconciliation/            # relocated broker-report reconciliation
│
├── apps/                          # accepted/active V10 adapter roots
│   ├── api/                       # accepted V10 API/application adapter
│   └── web/                       # accepted single V10 Web App
│   # apps/telegram/ is later lifecycle-gated and is not created merely by architecture
│
├── infrastructure/
│   └── windows/                   # accepted Personal-Node/Windows provisioning/runtime support
│   # additional infrastructure subroots appear only through owning accepted WPs
│
├── gpt/                           # current applied GPT configuration/recovery + migration source
├── knowledge/                     # repository-safe engineering/domain memory
├── docs/
│   ├── master-plan/
│   ├── architecture/
│   ├── operations/
│   ├── legal/
│   └── presentation/
├── tests/
├── scripts/
├── .github/
├── render.yaml                    # V9/provider retirement input; not forward V10 deployment authority
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

`ai/` remains a later lifecycle-gated V10 root and is not present/authorized merely because the target ownership model reserves it.

`app.py`, `app_v360.py`, `app_v371.py` and `main.py` remain present only because V9C-C has not yet completed runtime parity/zero-consumer/recovery proof. Their versioned names are not themselves deletion evidence, but Amendment 20 explicitly classifies them as migration inputs rather than permanent architecture.

The V9 `app:app` entrypoint remains a compatibility/recovery boundary until V9C-C; the forward Timeweb source entrypoint is `apps.api.hosted_runtime:create_app`.

## 3. Canonical V10 ownership model

The ownership model remains:

```text
omni-cio-gateway/
│
├── apps/                          # presentation / transport adapters only
│   ├── api/                       # ACCEPTED/ACTIVE
│   ├── web/                       # ACCEPTED/ACTIVE
│   └── telegram/                  # LATER WP — lifecycle-gated
│
├── omni_cio/                      # ONE deterministic financial Core
│   ├── contracts/
│   ├── adapters/
│   ├── quality/
│   ├── analytics/
│   ├── portfolio/
│   ├── reconciliation/
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
├── ai/                            # LATER Block G — policy/provider/RAG/evals/orchestrator
│
├── infrastructure/                # replaceable Personal-Node/deployment/recovery infrastructure
│   └── windows/                   # ACCEPTED/ACTIVE current physical subroot
│
├── gpt/                           # retained migration/recovery source until parity gate
├── knowledge/                     # repository-safe engineering memory
├── docs/
├── tests/
├── scripts/
└── .github/
```

### Important lifecycle rule

The ownership locations were reserved by WP1, but **authorization is per owning WP**. Since later work has now been accepted, `apps/api/`, `apps/web/` and `infrastructure/windows/` are no longer described as wholly future/reserved; they are accepted/active V10 adapter/infrastructure roots.

`apps/telegram/` and `ai/` remain later lifecycle-gated until `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md` authorizes their owning packages. A directory name or partial file presence never authorizes a WP by itself.

## 4. Why `omni_cio/` remains the Core root

V10 does **not** perform a cosmetic wholesale move from existing `omni_cio/<domain>` packages into a new `omni_cio/core/` wrapper merely to make the tree look newer.

The existing reviewed domain packages already are the financial Core. Moving hundreds of imports without a functional/security reason would create migration risk without product value.

Therefore:

- `omni_cio/` is the canonical deterministic Core root;
- domain packages remain at their stable paths until an evidence-backed package needs a specific move;
- transport/UI/AI code stays outside the financial Core in adapter roots;
- compatibility wrappers remain until explicit retirement evidence exists.

## 5. Ownership matrix

| Repository area | Authority / purpose | May own financial business logic? | May own broker-write secret? |
|---|---|---:|---:|
| `omni_cio/` | deterministic Core | yes | only isolated execution service as later approved |
| `omni_cio/real_trading/` | low-level Personal Real authority | narrow execution only | yes, runtime-only access |
| `omni_cio/plan_execution/` | immutable staged execution lifecycle | narrow plan execution | no raw secret storage |
| `apps/api/` | accepted V10 API/application adapter | no duplicate calculations | no |
| `apps/web/` | accepted single Web UI | no | no |
| `apps/telegram/` | later alerts/entry adapter | no | Telegram token only at runtime, not broker token |
| `ai/` | later AI/RAG/orchestration/evals | no canonical money calculations | no |
| `infrastructure/` | bootstrap/deploy/backup/health definitions | no | no committed secrets |
| `gpt/` | current GPT migration/recovery source | no new Core logic | no |
| `knowledge/` | repository-safe project/domain memory | no runtime authority | no |
| `docs/` | architecture/program/runbooks | no runtime authority | no |
| `.github/` | review/CI/control-plane automation | no | no broker secrets |

`CODEOWNERS` covers these areas. CODEOWNERS is reviewer/ownership metadata, not a substitute for runtime authorization.

## 6. Single-authority rules

The repository must keep exactly one canonical implementation of each critical authority.

Examples:

- one deterministic Core root: `omni_cio/`;
- one direct Real package: `omni_cio/real_trading/`;
- one safe plan-execution lifecycle: `omni_cio/plan_execution/`;
- one Sandbox package: `omni_cio/sandbox/`;
- one canonical Web application: `apps/web/`;
- one V10 API/application adapter root: `apps/api/`;
- one future Telegram adapter: `apps/telegram/` when its owning WP is accepted;
- one future AI orchestration stack: `ai/` when its owning WP is accepted;
- one V10 progress authority: `knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

Forbidden competing top-level roots include ad-hoc `frontend/`, `website/`, `telegram_bot/`, `backend/`, `server/`, `omni_cio_v10/` or a second top-level `execution/` stack.

## 7. Import / authority boundaries

### Core

Core packages may depend on shared contracts and reviewed lower-level services, but critical package cycles are forbidden by the V10 repository-boundary guard.

### Web / API / Telegram / AI

- presentation/AI adapters must not import `omni_cio.real_trading` directly;
- API/Web/Telegram/AI must not duplicate deterministic financial calculations or own low-level broker execution authority;
- AI never receives direct broker-write credentials;
- accepted API exposure calls reviewed Core/service interfaces rather than reimplementing sizing/risk/approval logic;
- any later approval/execution facade remains explicitly reviewed and fails closed; direct broker client access from UI/AI remains forbidden.

## 8. Machine-checked repository guards

Permanent V10 structural boundary checker:

`scripts/check_v10_repository_boundaries.py`

It checks at minimum:

- canonical V10 authority files exist;
- protected V9 compatibility paths remain present;
- no competing top-level V10 application/runtime tree appears;
- Real and plan-execution authority roots are unique;
- Web/Telegram/AI adapters cannot import low-level Real authority directly;
- critical Core package dependency graph contains no circular package dependency;
- explicit CODEOWNERS coverage exists for V10 roots.

Documentation/current-vs-historical consistency is additionally guarded by:

`scripts/check_v10_documentation_consistency.py`

Both guards run through accepted governance/CI paths and must not be weakened to land a change.

## 9. Move/delete protocol

Before moving/deleting any existing runtime or recovery path:

1. search imports/references;
2. inspect tests and fixture paths;
3. inspect CI/scripts;
4. inspect V9 Render/current GPT/recovery docs and accepted V10 consumers;
5. determine the owning V10 WP;
6. document replacement/migration path;
7. preserve compatibility wrapper where needed;
8. add deterministic regression guard;
9. run cheap/focused preflight and full-diff review;
10. pass all applicable exact-head gates;
11. squash merge only after review blockers are zero;
12. pass required post-merge verification.

A versioned filename is not evidence of obsolescence.

## 10. Account independence / developer portability

A new authorized developer must be able to:

`clone repository -> read AGENTS/Program Lock/current status/architecture -> install from locked dependencies -> run checks -> create focused branch -> PR -> CI -> reviewed deploy`

without access to the original ChatGPT account.

No authoritative Web/AI/Telegram application setting may exist only inside a personal account dashboard when it can be represented as repository-controlled schema/configuration.

Hosting/domain replacement is a deployment/configuration change, not creation of a new website/project.

Secret values remain a separate runtime provisioning process and are never implied by GitHub developer access.

## 11. Current V9 compatibility ownership

Amendment 20 makes the compatibility boundary explicitly temporary:

- deterministic root engines have moved to canonical `omni_cio/` ownership in V9C-B;
- `app.py`, `app_v360.py`, `app_v371.py` and `main.py` remain only until V9C-C proves replacement, zero current consumers and recovery;
- `render.yaml`, retired-provider artifacts and V9-specific GPT working-tree assets remain migration inputs until their V9C-D/V9C-E gates;
- existing GPT v9.0.0 and historical provider evidence remain provenance/recovery inputs, not forward V10 provider authority;
- V9 broker execution invariants remain binding throughout migration.

No compatibility artifact may be removed merely by name; no compatibility artifact may remain indefinitely after its owning zero-consumer/recovery gate passes.

## 12. Development/test reproducibility boundary

The repository owns:

- dependency source/locks;
- CI workflows;
- safe example configuration;
- architecture/runbooks;
- bootstrap/deployment definitions.

A developer workstation may cache dependencies/tools, but that cache is never source of truth.

WP2 selected and accepted the V10 toolchain baseline in `V10_TOOLCHAIN_BASELINE.md` + `.json`. Later changes require focused dependency/toolchain review, reproducible locks and rollback evidence.

## 13. Current delivery-state rule

This architecture document does **not** maintain a second progress table. Exact accepted progress/current-next WP is read only from:

`knowledge/17_V10_CURRENT_PROGRAM_STATUS.md`.

Historical WP1 language in old PRs/records remains evidence of how this ownership model was introduced, not current program state.

## 14. Cleanup/documentation rule

Do not create duplicate setup/configuration/inventory/current-status documents when this file or another canonical source can be updated. Historical audit records may remain when needed for traceability, but they cannot compete with current authority.

Documentation lifecycle and precedence are defined by `docs/DOCUMENTATION_AUTHORITY_AND_LIFECYCLE.md`.