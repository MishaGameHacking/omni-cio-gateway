D           |
| H        | Guardian / Watchtower Loop     | 8%      | NOT STARTED           |
| I        | Personal Real Execution        | 7%      | NOT STARTED           |
| J        | Hardening / Recovery / Release | 5%      | NOT STARTED           |

- Процент блока засчитывается только после Exit Gate, а не после появления файлов или UI.

- После каждого accepted merge обновляется `knowledge/V10_CURRENT_PROGRAM_STATUS.md`: completed WPs, текущий WP, blockers, next step, общий процент.

- Следующий WP нельзя начинать, если текущий Exit Gate имеет P0/P1 blocker.

- В одном PR не смешивать несвязанные WP. Integration PR допускается только в Block J или когда сам WP требует связать уже принятые interfaces.

# BLOCK A - Архитектура и защита V9 (5%)

## WP0 - V10 Program Lock и baseline freeze

**Цель:** Официально открыть отдельную программу V10, не превращая завершённый V9 master-plan в бесконечную очередь задач.

**Результаты / deliverables**

- Создать канонический V10 master-plan в GitHub и `V10_CURRENT_PROGRAM_STATUS.md`.

- Создать V10 system architecture, security boundaries, data flow, threat model и recovery contract.

- Обновить AGENTS.md: V9 COMPLETE; V10 - единственная разрешённая feature-program после owner approval.

- Зафиксировать точный V9 accepted commit/release, recovery assets и tests, которые нельзя регрессировать.

- Ввести ADR-процесс для архитектурных решений V10 (решение, причины, альтернативы, последствия, rollback).

**Обязательная проверка**

- Re-run V9 Regression Shield на точном baseline перед первым feature change.

- Проверить, что V10 docs не меняют production runtime и Actions.

- Проверить отсутствие секретов/приватных broker payloads в новых документах.

**Exit Gate**

- V9 восстанавливается по существующей документации.

- Есть один owner-approved roadmap V10 и один source of truth по текущему прогрессу.

- Нет незаявленного второго Gateway, второго execution stack или дублирующего проекта.

**Участие владельца:** Только утвердить программу V10 отдельной командой. До этого этап остаётся DRAFT.

# BLOCK B - GitHub, зависимости и CI/CD (10%)

## WP1 - Repository Architecture и boundaries

**Цель:** Подготовить репозиторий к многолетней разработке одной платформы без хаотичного размножения каталогов и legacy-слоёв.

**Результаты / deliverables**

- Определить финальные каталоги apps/api, apps/web, apps/telegram, omni_cio/core-модули, ai, infrastructure, docs, knowledge, tests.

- Добавить repository-boundary tests: public/read-only code не может импортировать real execution authority.

- Перед любым move/delete выполнять reference/import/CI/runtime audit и сохранять compatibility wrappers до доказанной миграции.

- Задокументировать canonical ownership каждого файла/каталога и запрет duplicate sources of truth.

**Обязательная проверка**

- Repository structure guard в CI.

- Import graph и circular dependency checks для критических packages.

- V9 compatibility tests после каждого structural PR.

**Exit Gate**

- Новый разработчик/AI по AGENTS + REPOSITORY_STRUCTURE понимает, где находится каждый компонент и что является authority.

- Нет двух competing реализаций одного финансового engine.

**Зависимости:** WP0

## WP2 - Toolchain и Dependency Baseline

**Цель:** Зафиксировать поддерживаемый стек и способ обновления зависимостей до начала массовой разработки.

**Результаты / deliverables**

- Python/FastAPI сохранить как основной backend, если compatibility audit не обнаружит блокер.

- Frontend baseline: React stable + TypeScript + Vite stable, без обязательного SSR/RSC на первом V10.

- Local persistence baseline: PostgreSQL supported stable branch; exact minor выбирается перед implementation gate.

- Зафиксировать Node.js LTS, Python minor, package managers и lock formats.

- Ввести dependency policy: direct constraints, generated locks, SBOM/manifest, license allow/deny list.

**Обязательная проверка**

- Clean install на Windows из пустой рабочей директории.

- Deterministic lock verification.

- Known CVE audit и license scan.

- Build backend + frontend на GitHub-hosted CI до подключения Lenovo runner.

**Exit Gate**

- Один документированный toolchain; reproducible clean build; нет unpinned critical dependency paths.

**Зависимости:** WP1

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><strong>Инженерная оговорка<br />
</strong>План ориентируется на текущие stable ветки, но точные версии должны быть повторно проверены непосредственно перед implementation. В августе 2026 official docs указывают React 19.2, поддерживаемый Vite 8.1 и PostgreSQL 18.4; эти номера не являются вечным hard-code программы.</th>
</tr>
</thead>
<tbody>
</tbody>
</table>

## WP3 - V10 Regression Shield

**Цель:** Сделать CI основным барьером против внесения скрытых дефектов до runtime.

**Результаты / deliverables**

- Сохранить V9 quality/security gates и добавить frontend TypeScript/lint/unit/E2E.

- Добавить DB migration tests, API schema/contract tests, authority tests, backup/restore tests, Telegram signature tests и AI schema tests.

- Добавить Playwright smoke/E2E для критических Web workflows.

- Разделить fast PR checks и full exact-head regression/security gate.

**Обязательная проверка**

- Compile, Ruff, format, mypy, pytest/coverage.

- Frontend build/type/lint/tests.

- Dependency audit, SAST, secret scan.

- Critical money-path replay/idempotency tests.

**Exit Gate**

- Ни один significant PR не может быть merged при красном mandatory gate.

- CI failure нельзя обходить отключением проверки.

**Зависимости:** WP2

## WP4 - Release, build provenance и deployment contract

**Цель:** Каждый установленный runtime должен однозначно соответствовать конкретному reviewed Git commit.

**Результаты / deliverables**

- Ввести V10 semantic release version, git SHA, build SHA256 manifest, dependency lock fingerprint, DB migration version.

- Создать signed/hashed release manifest и проверку перед локальным deployment.

- Запретить deploy произвольного unreviewed working tree на OWNER runtime.

- Сформировать changelog/release notes автоматически из accepted PR metadata где практично.

**Обязательная проверка**

- Попытка deploy с неправильным manifest/hash должна fail closed.

- Rollback на предыдущий accepted release должен быть воспроизводим.

**Exit Gate**

- Можно доказать, ка