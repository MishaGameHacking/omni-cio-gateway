esearch bursts, DB backup concurrent load.

**Exit Gate**

- Нет memory leak/thermal crash/resource starvation в acceptance window.

**Зависимости:** WP47

## WP49 - Disaster Recovery Rehearsal

**Цель:** Восстановить V10 как будто старый Lenovo/SSD потерян.

**Результаты / deliverables**

- Fresh/clean environment -> GitHub bootstrap -> DB restore -> local secrets restore -> health -> shadow verification.

- Runbook не зависит от памяти чата или устных инструкций.

**Обязательная проверка**

- Практический restore rehearsal с checklist/evidence.

**Exit Gate**

- Restore time и действия известны; V10 возвращается в read-only safe state до разрешения Real.

**Зависимости:** WP48

**Участие владельца:** Помочь только с физическим/удалённым доступом к тестовой машине/backup при rehearsal.

## WP50 - V10.0.0 Final Release и protected rollback

**Цель:** Закрыть программу только после доказанного production readiness.

**Результаты / deliverables**

- Все WP complete; zero open blockers; zero unresolved review threads.

- Final exact-head Regression Shield/security/restore/soak green.

- Owner acceptance Web + Telegram + Guardian + Real safety boundaries.

- Создать V10 protected release/rollback; обновить README/AGENTS/current status.

- V9 остаётся архивным protected recovery/reference, пока owner явно не изменит retention policy.

**Обязательная проверка**

- Final release manifest/hash verification; clean deploy from release.

**Exit Gate**

- `knowledge/V10_CURRENT_PROGRAM_STATUS.md` = 100% COMPLETE; дальнейший feature work требует новой программы/maintenance scope.

**Зависимости:** WP49

**Участие владельца:** Финальная owner acceptance. Реальная сделка не должна делаться только ради красивой галочки; если нет естественного безопасного сценария, execution acceptance проводится через Sandbox/fake + ранее доказанный Real primitive до отдельного owner решения.

# 14. Сквозная стратегия тестирования

12. Unit: детерминированные финансовые функции, parsers, validators, state transitions.

13. Contract: API DTO, DB schema, broker adapters, AI schema, Telegram auth.

14. Integration: Core+DB, Core+T-Invest read, Watchtower+Research, Telegram+Web deep-link.

15. Golden regression: V9 fixtures должны защищать от изменения финансового смысла при extraction/refactor.

16. E2E: Web critical paths и Guardian incident lifecycle.

17. Property/fuzz: decimals, identity mapping, malformed source data, replay/idempotency.

18. Security: ASVS/AISVS requirements, SAST, dependency, secrets, negative authorization.

19. Failure injection: network/DB/reboot/timeout/duplicate/possible-submit.

20. Shadow evaluation: real portfolio decisions without writes.

21. Production acceptance: только после всех более дешёвых уровней тестирования.

# 15. Работа с ошибками и инцидентами разработки

| **Класс**           | **Пример**                                   | **Правило**                                                 | **Переход дальше** |
|---------------------|----------------------------------------------|-------------------------------------------------------------|--------------------|
| P0 Money/Security   | возможен второй submit, утечка trading token | Немедленная остановка relevant program/runtime; kill switch | Запрещён           |
| P1 Data correctness | неверная валюта/доля/identity/freshness      | Исправить в текущем WP + permanent regression               | Запрещён           |
| P2 Functional       | не работает страница/alert/job               | Исправить до Exit Gate, если относится к gate               | Только после gate  |
| P3 UI/minor         | косметика без влияния на смысл               | Можно backlog при документированном решении                 | Допустим           |

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><strong>Запрещённая практика<br />
</strong>Фразы "иногда создаёт второй ордер", "данные иногда не совпадают", "потом починим после запуска" несовместимы с Real-money Definition of Done. P0/P1 дефект должен блокировать дальнейшую разработку соответствующего контура.</th>
</tr>
</thead>
<tbody>
</tbody>
</table>

# 16. Правила моей будущей работы через GitHub

22. Перед каждым сеансом прочитать AGENTS.md, README.md, PROJECT_MASTER_CONTEXT, V10_CURRENT_PROGRAM_STATUS, этот master-plan, relevant architecture/runbook, open PR/issues и latest Actions.

23. Выбрать ровно один текущий WP из `V10_CURRENT_PROGRAM_STATUS.md`. Не начинать соседний WP ради удобства.

24. Создать focused branch; сформулировать acceptance criteria до написания кода.

25. Добавлять tests одновременно с кодом. Если дефект найден - по возможности сначала regression test.

26. Не делать прямых changes в main; branch -> PR -> exact-head gate -> zero unresolved threads -> squash merge.

27. После merge обновить V10_CURRENT_PROGRAM_STATUS отдельным контролируемым изменением или в том же PR, если status отражает реально завершённый gate.

28. Новая идея во время работы попадает в `V10_BACKLOG.md`, а не реализуется поверх текущего WP без amendment.

29. Любой новый внешний dependency/source сначала проходит official-doc/security/license/maintenance review.

30. Никакой tool/model/service не получает больше authority, чем нужно его узкой функции.

31. Не считать действие выполненным только потому, что код написан: нужна evidence цепочка tests/CI/runtime acceptance.

# 17. Что намеренно НЕ входит в V10

- Массовая регистрация пользователей и public multi-tenant production.

- Платные подписки/СБП/эквайринг и billing.

- Публичное использование чужих T-Invest API token.

- Public real execution или доверительное управление.

- Мобильные native приложения App Store/Google Play.

- Обучение LLM с нуля и постоянный дорогой GPU cloud без доказанной необходимости.

- Поддержка множества брокеров.

- Маржинальная торговля, short, withdrawal/transfer authority.

- Полная автономная торговля без one-plan/one-owner-approval boundary.

# 18. Минимальное участие владельца

32. Утвердить V10 master-plan и дать команду начать программу.

33. Через удалённый рабочий стол помочь с первоначальным bootstrap/UAC и фактическим hardware audit.

34. Создать Telegram Bot через BotFather и локально сохранить token, когда Telegram block будет готов.

35. Локально ввести read-only T-Invest token на WP15.

36. После Shadow acceptance и отдел