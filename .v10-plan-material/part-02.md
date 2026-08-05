кой commit и какие locks работают на Lenovo в любой момент.

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

- No-GPT integration test запуск