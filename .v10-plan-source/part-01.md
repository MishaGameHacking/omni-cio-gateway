supported stable branch; exact minor выбирается перед implementation gate.

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

- Можно доказать, какой commit и какие locks работают на Lenovo в любой момент.

**Зависимости:** WP3

# BLOCK C - Lenovo Omni-CIO Node (15%)

## WP5 - Hardware/OS Audit и эксплуатационный профиль

**Цель:** Получить фактическую, а не предполагаемую картину постоянного 24/7 узла.

**Результаты / deliverables**

- Зафиксировать CPU, RAM 16/32 GB, точную GPU (GTX 1660 Ti или RTX 2060), VRAM, SSD/free disk, Windows build, NVIDIA driver.

- Проверить wired network, reboot behaviour, power settings, battery conservation, idle/load temperatures.

- Определить допустимые thermal/resource thresholds и alerts.

**Обязательная проверка**

- 30-60 минут контролируемой CPU/GPU нагрузки без перегрева/thermal shutdown.

- Reboot test, network reconnect test, disk health check.

**Exit Gate**

- Создан OWNER_NODE_PROFILE без серийных номеров/персональных данных; аппаратные лимиты известны.

**Участие владельца:** Один раз выполнить диагностические команды/дать скриншоты через удалённый рабочий стол при необходимости.

## WP6 - OS identities и privilege separation

**Цель:** Не допустить, чтобы GitHub workflow автоматически обладал теми же правами, что real-money runtime.

**Результаты / deliverables**

- Разделить owner-admin, GitHub runner identity и Omni-CIO runtime identity.

- Минимизировать filesystem/registry/service permissions каждой роли.

- Runner не получает read access к trading secret store.

- Execution service получает только необходимые broker/network permissions.

**Обязательная проверка**

- Negative permission tests: runner не читает trading secret; Web process не может менять runner config; AI process не может вызвать broker write напрямую.

**Exit Gate**

- Компрометация обычного CI job не означает автоматический доступ к real-money secret.

**Зависимости:** WP5

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><strong>Инженерная оговорка<br />
</strong>GitHub официально рекомендует self-hosted runners использовать с private repositories; runner исполняет workflow непосредственно на машине, поэтому privilege isolation является P0 boundary.</th>
</tr>
</thead>
<tbody>
</tbody>
</table>

## WP7 - One-Time Bootstrap

**Цель:** Свести ручную первоначальную настройку Lenovo к небольшому числу проверяемых действий владельца.

**Результаты / deliverables**

- Создать versioned `bootstrap-v10.ps1` и dry-run/preflight режим.

- Проверять/устанавливать runtime prerequisites, service users, directories, DB, runner, logs и service definitions.

- Bootstrap должен быть повторяемым/idempotent: повторный запуск не ломает установленную систему.

- Секреты не передавать arguments/console history; bootstrap только создаёт безопасные места для их последующего ввода.

**Обязательная проверка**

- Test на чистой/виртуальной Windows-среде где возможно.

- Повторный bootstrap поверх установленного node.

- Rollback/cleanup procedure.

**Exit Gate**

- Владелец не редактирует десятки конфигурационных файлов вручную.

**Зависимости:** WP6

**Участие владельца:** Запустить bootstrap от нужной роли и подтвердить системные UAC действия, которые невозможно выполнить через GitHub.

## WP8 - Local Secret Store и rotation

**Цель:** Хранить broker/Telegram secrets вне GitHub и вне доступности обычных workflows.

**Результаты / deliverables**

- Разработать локальный Windows secret store на DPAPI/credential-protected подходе или выбранном local vault.

- Разделить read broker, trading broker, Telegram, local encryption keys и будущие external source credentials.

- Ввести secret version/rotation metadata без записи значений.

- Logs/errors всегда redacted.

**Обязательная проверка**

- Secret scan filesystem/Git history.

- Rotation rehearsal read token и Telegram token.

- Unauthorized process access test.

**Exit Gate**

- Нет plain-text secret в repo, logs, crash dumps или Web UI; runtime может получить только нужный ему секрет.

**Зависимости:** WP7

**Участие владельца:** Один раз локально ввести секреты, когда соответствующий контур будет готов.

## WP9 - Autostart, supervision и self-healing

**Цель:** После Windows Update/reboot система должна самостоятельно вернуться в рабочее безопасное состояние.

**Результаты / deliverables**

- Запуск DB, Core API, Web, Telegram, Watchtower, AI worker и health supervisor как контролируемых services/tasks.

- Dependency-aware startup order и health readiness.

- Crash restart policy с backoff и max attempts; запрет бесконечного restart storm.

- Отдельный degraded mode: AI/Telegram могут быть down, но Core/read-only state остаётся безопасным.

**Обязательная проверка**

- Kill каждого процесса и наблюдение восстановления.

- Полный reboot test без ручного открытия терминалов.

- Service dependency failure test.

**Exit Gate**

- После reboot OWNER получает HEALTHY/DEGRADED status без ручного запуска приложений.

**Зависимости:** WP8

## WP10 - Backup, restore и off-device recovery

**Цель:** Не потерять решения, планы и audit trail при отказе SSD/Windows.

**Результаты / deliverables**

- Автоматические DB backups с retention и integrity hashes.

- Шифрованная off-device копия: отдельный диск/NAS/другое owner-controlled хранилище.

- Backup приватных non-secret конфигураций и model/RAG metadata.

- Runbook полного восстановления на новый Windows node.

**Обязательная проверка**

- Автоматический restore test из выбранного backup.

- Corrupt backup detection.

- Проверка, что secrets не попали в нешифрованный backup.

**Exit Gate**

- Restore доказан практикой, а не только написан в документе.

**Зависимости:** WP9

**Участие владельца:** Предоставить одно off-device место хранения или внешний диск, если его нет.

# BLOCK D - V10 Core и данные (15%)

## WP11 - V9 Core Extraction

**Цель:** Отделить финансовые engines от обязательного Custom GPT presentation layer, сохранив проверенное поведение V9.

**Результаты / deliverables**

- Инвентаризировать все WP1-WP14 engines и их реальные зависимости от app/GPT wrappers.

- Создать стабильные Python service interfaces/DTO для Core.

- Сохранить legacy compatibility до завершения параллельных regression comparisons.

- Убрать UI/GPT assumptions из внутренних engines, не меняя финансовые формулы без отдельного proof.

**Обязательная проверка**

- Golden V9 fixtures: одинаковый input даёт эквивалентный output до/после extraction.

- No-GPT integration test запускает portfolio->risk->optimizer->plan.

**Exit Gate**

- Core может работать без Custom GPT и без OpenAI.

- V9 rollback остаётся рабочим.

**Зависимости:** Blocks A-C

## WP12 - Canonical Domain Model и tenant-ready IDs

**Цель:** Создать единую внутреннюю модель данных, пригодную для OWNER сейчас и возможного multi-tenant будущего без включения public режима.

**Результаты / deliverables**

- Определить Tenant/User/BrokerAccount/PortfolioSnapshot/Position/Instrument/Policy/Evidence/Incident/Decision/Plan/Execution/Journal models.

- Каждый private record связывается с tenant_id/portfolio_id/policy_id.

- В V10 runtime разрешён только OWNER tenant; попытка создать public tenant fail closed.

- Identity instruments связывать по broker UID/ISIN/FIGI/class code, а ticker/name использовать только как secondary labels.

**Обязательная проверка**

- Schema validation, uniqueness/identity coll