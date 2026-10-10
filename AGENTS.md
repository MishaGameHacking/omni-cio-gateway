# OMNICIO — Development Law

Статус: CANONICAL / REQUIRED  
Область действия: весь текущий и будущий код репозитория  
Назначение: единый закон разработки без дублирующих процессных инструкций

## 1. Главный принцип

Этот файл — единственная каноническая инструкция разработчика проекта.

Продуктовое основание редакции: прямое поручение владельца от 10.10.2026 перевести OMNICIO с web/PWA/Telegram-концепций на нативное Android-приложение с local-first персональным контуром и публикацией в RuStore. Канонический scope первого этапа — `docs/ui-plan.md` (UI-01–UI-06), второго — `docs/system-plan.md` (SYS-01–SYS-12). Этап 1 завершает Android UX на fixtures/local state; этап 2 подключает local secure storage, прямой read-only T-Invest, общий Timeweb intelligence, risk/scenario engines, AI Gateway и при подтверждённом спросе RuStore subscriptions. README.md различает целевую Android-архитектуру и фактическое legacy web/backend состояние. Старые web/Telegram продуктовые планы больше не определяют разработку; Git history остаётся архивом. Проверенные компоненты безопасности, общих источников и выпуска сохраняются только там, где имеют current consumer.

Его можно изменять в будущем, но только осознанно. Не создавать рядом дополнительные файлы с дублирующими правилами разработки, такие как DEVELOPMENT_GUIDE.md, CODING_RULES.md, ENGINEERING_LAW.md и их аналоги.

Если правило разработки уже есть здесь — обновить это правило здесь, а не создавать второй источник истины.

Приоритет разработки:

1. корректность;
2. безопасность;
3. доказуемость;
4. восстановление;
5. простота;
6. скорость;
7. минимальный объём кода и файлов.

Green CI необходим, но сам по себе не означает, что задача завершена.

## 2. Целевая платформа

Поддерживаемая целевая архитектура:

- **Android / Kotlin / Jetpack Compose** — единственный основной пользовательский клиент нового продукта;
- **RuStore** — целевой канал Android-публикации;
- **GitHub** — код, PR, CI, review и release provenance;
- **Timeweb Cloud** — общий backend/API, разрешённые рыночные источники, AI Gateway, PostgreSQL для общей аналитики и технические secrets;
- **T-Invest API** — прямой read-only доступ пользователя с Android-устройства к его собственному счёту.

### 2.1. Local-first authority

В базовом Android режиме:

- аккаунт OMNICIO, email, пароль и social login не являются обязательными;
- приложение генерирует локальный random profile/installation id;
- T-Invest token хранится только на устройстве и защищается Android Keystore;
- персональные позиции, баланс, операции, цели и локальные сценарии хранятся в защищённой local DB;
- Timeweb не получает broker token/portfolio в базовом local-first потоке;
- server-side browser/user identity не является authority для local portfolio.

Нельзя передавать T-Invest token через наш backend «для удобства», если задача решается прямым on-device API без нового явно принятого решения.

### 2.2. T-Invest

- Production принимает только read-only/account-scoped credential для аналитики.
- Full-access/transfer credential приложению не требуется.
- Приложение не отправляет торговые поручения, стоп-заявки или переводы.
- Пользовательский T-Invest API используется только для собственного счёта пользователя.
- T-Invest API не используется Timeweb как общий публичный источник и не ретранслируется всем пользователям.
- История операций, позиции и order state считаются разными источниками фактов; задержка одного не подменяется другим.
- Unknown access/unknown data fail closed для зависимого расчёта.

### 2.3. Общий Timeweb intelligence

Timeweb обрабатывает только общий слой:

- разрешённые публичные/лицензированные источники;
- отчётность;
- корпоративные события;
- общие payouts/market/macro facts;
- issuer/instrument profiles;
- AI extraction/summary;
- provenance/freshness.

Один общий документ анализируется один раз и переиспользуется всеми устройствами.
GPT не получает broker token, баланс, полный портфель или локальные user secrets.

### 2.4. Android data security

- Sensitive local DB нельзя оставлять plain.
- Database encryption key создаётся на устройстве и защищается Android Keystore.
- Broker token не хранить в plain Room/SharedPreferences/DataStore.
- Логи, crash reports, screenshots и fixtures не содержат token/portfolio secrets.
- Android backup policy проверяется явно; sensitive DB/token не должны неожиданно уходить в cloud backup.
- Wipe/revoke удаляет локальные secrets и dependent jobs.
- Room/local schema migrations имеют отдельные migration tests.

### 2.5. Android background

Android не является 24/7 сервером.

- WorkManager используется для persistent/deferrable sync.
- Exact periodic execution по минутам не обещается.
- Timeweb круглосуточно обрабатывает общий market intelligence.
- Android догоняет delta по cursor при open/sync/background opportunity.
- Optional fast alerts могут использовать RuStore Push.
- Push payload не содержит balance, holdings или broker token.
- Если fast-alert подписка хранит instrument/topic IDs на сервере, это отдельная optional server-side data purpose.

### 2.6. Analytics-first / regulated gate

Базовый production без инвестиционного советника может реализовывать фактическую аналитику, общие исследования, локальные concentration/stress/scenario calculations и сравнение вариантов, выбранных самим пользователем, если фактический результат не образует ИИР.

Автоматически выбранные системой для конкретного пользователя BUY/SELL/HOLD, конкретные количества и замены находятся за regulated gate.

- Полный optimizer можно разрабатывать на synthetic/research data.
- Ordinary release build не открывает персональный auto-trade output.
- Local preference, developer menu, hidden tap или browser flag не могут открыть gate.
- Future regulated activation требует отдельного PR, правового evidence, security review и release acceptance.
- То, что расчёт выполняется на телефоне или GPT, не является основанием считать персональную рекомендацию нерегулируемой.

### 2.7. Персональные данные

Цель — минимизация серверной обработки, а не фиктивное утверждение, что ПДн отсутствуют.

Если базовый local-first поток действительно не передаёт на Timeweb портфель/token/идентификаторы пользователя, это фиксируется архитектурно и тестами.
Если отдельная функция обрабатывает server-side push token, purchase/entitlement ID, support data, analytics identifiers или иные относимые сведения, её цели/категории и применимые обязанности проверяются по фактической схеме.

Нативное приложение само по себе не освобождает от 152-ФЗ.
Не добавлять серверную identity только для того, чтобы воспроизвести старую web-модель.

### 2.8. RuStore

- Package/applicationId и release signature фиксируются до первой публикации.
- Release key не хранится в Git/логе.
- Приложение не является простой WebView-обёрткой.
- Модерации доступен demo/test path без production secrets.
- Описание не заявляет недоступные функции.
- Собиравшиеся данные и payment SDK декларируются фактически.
- Android/RuStore требования проверяются по актуальной документации перед каждым релизом.
- Для in-app subscriptions использовать актуальный RuStore Pay SDK; deprecated BillingClient не вводить.

### 2.9. Платформа и scope

Не добавлять Telegram Mini App, iOS, Google Play, Cloudflare, Neon, Render, Cloud.ru или другую основную платформу без нового явного решения OWNER.

Legacy web/PWA:

- не развивается как новый личный кабинет;
- может временно обслуживать API/legal/status/release metadata;
- удаляется только после появления проверенного Android replacement;
- legacy данные/аккаунты не удаляются молча.

Нельзя оставлять старый исполняемый код «на всякий случай», если current consumer исчез: Git history является архивом.

### 2.10. Android build authority и артефакты

После появления Android module:

- использовать только Gradle Wrapper репозитория для CI/release commands;
- Android Studio является рекомендуемой IDE, но локальная IDE не является единственным доказательством собираемости;
- каждый material Android PR обязан собирать debug APK в CI;
- APK artifact маркируется exact commit SHA/version и хранится как CI artifact, а не коммитится в Git;
- минимум проверок Android head: lint, unit tests, assembleDebug и применимые dependency/security checks;
- connected/device tests обязательны для функций, которые нельзя надёжно доказать JVM-тестом, когда доступен доверенный emulator/physical-device runner;
- release APK/AAB не собирать с debug key;
- private release/upload key, keystore, passwords и T-Invest token не передавать в чат, PR body, artifact, log или repository;
- release signing automation допустима только через защищённый environment/secret custody;
- OWNER/QA получает debug APK и тестирует его на реальном устройстве; feedback привязывается к exact build SHA;
- RuStore upload выполняется только для accepted release commit после green checks и smoke-проверки подписанной сборки.

CI artifact не является опубликованным релизом, а успешная установка debug APK не доказывает корректность release signing, store metadata или модерации.

### 2.11. OWNER: обновление и запуск актуального Android debug с GitHub

Если OWNER просит «обновить приложение», «установить актуальную версию из GitHub» или аналогичное без дополнительных уточнений, это означает именно следующий локальный Windows/Android Studio поток:

1. Использовать корень текущего checkout `omni-cio-gateway`, а не случайную текущую папку PowerShell и не старую feature branch.
2. Целевое состояние исходников — accepted `origin/main`. Перед переключением выполнить `git fetch origin --prune`.
3. Если рабочее дерево содержит незакоммиченные изменения, сначала сохранить их через `git stash push -u -m "backup-before-owner-update"`; не удалять их и не делать destructive reset молча.
4. Переключиться на accepted main. Для чистого checkout использовать `git switch main` + `git merge --ff-only origin/main`. Если локальный `main` расходится с `origin/main`, не merge/rebase автоматически: сохранить локальную ветку/работу и явно привести рабочий checkout к `origin/main` только ради этой установки.
5. Проверить exact SHA через `git rev-parse --short HEAD`; не считать обновление успешным, пока HEAD не соответствует текущему accepted `origin/main`.
6. Для сборки/установки использовать Gradle Wrapper репозитория: `./gradlew :app:installDebug --no-configuration-cache` (Windows: `.\gradlew.bat :app:installDebug --no-configuration-cache`). Не использовать `assembleDebug` как замену установке.
7. Debug-вариант имеет отдельный package `ru.omnicio.app.debug`; он может существовать рядом с release `ru.omnicio.app`. После установки запускать именно debug package, а не старую release/старую debug-иконку.
8. Если `installDebug` завершился `BUILD SUCCESSFUL`, но приложение само не открылось, это не ошибка установки: запустить `ru.omnicio.app.debug` через Android Studio Run или ADB. Каноническая PowerShell-проверка/запуск:
   - `$adb="$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"`
   - `& $adb shell dumpsys package ru.omnicio.app.debug | Select-String "versionName|versionCode"`
   - `& $adb shell am force-stop ru.omnicio.app.debug`
   - `& $adb shell monkey -p ru.omnicio.app.debug -c android.intent.category.LAUNCHER 1`
9. Если Android Studio после обновления показывает unresolved AndroidX imports и баннер о changed Gradle files, сначала выполнить Sync Project with Gradle Files. Не переписывать корректный Kotlin-код только ради красной IDE-подсветки до успешного Gradle Sync.
10. При ошибке dependency locking на IDE-only конфигурации вида `debugRuntimeClasspathCopy` проверять текущую каноническую lock policy репозитория; не генерировать произвольный новый lock state и не отключать dependency locking локальным обходом.
11. После успешной установки OWNER ожидает две вещи: подтверждённый exact Git SHA/версию и фактически запущенное приложение на подключённом устройстве.

Этот контракт является ответом по умолчанию на будущие запросы OWNER об обновлении Android-приложения с GitHub; не заставлять OWNER заново объяснять различие между старой feature branch, accepted main, установкой APK и запуском debug package.

## 3. Правило минимального репозитория

Каждый новый файл должен иметь одну доказуемую текущую ответственность.

Перед созданием любого файла обязательно:

1. найти существующий код с той же или близкой ответственностью;
2. проверить его фактических consumers;
3. решить, можно ли расширить или переработать существующий файл;
4. создать новый файл только если существующий файл после изменения потеряет понятную ответственность.

Запрещено создавать дубликаты вида:

- *_v2.py;
- *_new.py;
- *_final.py;
- *_fixed.py;
- *_copy.py;
- backup_*;
- old_*;
- второй helper с тем же поведением;
- второй config для того же параметра;
- второй workflow для тех же проверок без необходимости разделения authority.

Одна ответственность должна иметь одну каноническую реализацию.

Если старый код полностью заменён и не имеет current consumer — удалить его в той же coherent change.

Не хранить копии удалённого кода как архивные файлы. Архив — Git history.

## 4. Reuse-first алгоритм

До написания кода выполнить поиск по репозиторию:

- точное имя функции/класса;
- похожие символы;
- одинаковые API endpoints;
- одинаковые environment variables;
- одинаковые SQL операции;
- одинаковые error codes;
- одинаковые provider mutations;
- одинаковые сериализаторы/валидаторы;
- одинаковые UI components;
- одинаковые assets.

Порядок решения:

1. переиспользовать существующий код без изменения;
2. расширить существующий код;
3. обобщить существующий код, если есть минимум два реальных consumers;
4. заменить старую реализацию одной новой;
5. только затем создавать новую реализацию.

Не создавать abstraction "на будущее" без текущего consumer.

Не создавать generic framework ради одной функции.

## 5. Закон Python

Python-код должен следовать принципам PEP 8 и PEP 20:

- explicit лучше implicit;
- simple лучше complex;
- readability имеет приоритет над clever code;
- ошибки не должны проходить молча;
- при неоднозначности нельзя угадывать.

Правила:

- функции и методы должны иметь понятные типы аргументов и результата;
- использовать современный built-in typing, когда это делает контракт яснее;
- использовать pathlib вместо ручной сборки путей;
- использовать context managers для ресурсов;
- ловить конкретные исключения, а не bare except;
- try-блок держать минимальным;
- сохранять первичную причину ошибки через exception chaining, когда это полезно;
- не использовать mutable global state без доказуемой необходимости;
- не прятать I/O и provider mutation внутри "безобидных" utility-функций;
- provider adapters делать тонкими;
- business logic не связывать с конкретным provider без необходимости;
- функции должны иметь одну понятную ответственность;
- не использовать metaprogramming, decorators или inheritance, если простая функция/композиция решает задачу;
- async использовать только для реально асинхронного I/O или concurrency;
- не добавлять dependency, если задача корректно решается стандартной библиотекой;
- не подавлять type/lint/security ошибки без документированной технической причины;
- не оставлять TODO/FIXME вместо завершённой обязательной части задачи.

Комментарии и docstrings объясняют назначение, единицы измерения, ограничения,
причину нетривиального решения и поведение при ошибке. Публичная функция и общий
параметр должны иметь понятное имя и контракт. Не дублировать очевидную операцию
комментарием и не оставлять комментарий, который расходится с реализацией.

Размер кода не является целью сам по себе. Цель — минимальное количество кода, достаточное для полного и проверяемого поведения.

## 6. Единственный источник конфигурации

Не дублировать одно значение в нескольких местах.

После bootstrap проекта стремиться к:

- pyproject.toml — Python dependencies, tooling configuration и единственный versioned Timeweb target в `[tool.omnicio.timeweb]`;
- uv.lock — единственный resolved dependency lock; `requirements-runtime.txt` и `requirements-dev.txt` являются его generated exports, CI проверяет их совпадение с lock;
- сторонние Python packages устанавливать только как wheels с проверкой хешей; собственный reviewed checkout собирать offline, без разрешения зависимостей и build isolation, используя build tools из того же lock;
- Dockerfile — production image contract;
- environment variables / Timeweb secrets — runtime configuration;
- AGENTS.md — developer law.

Версии Python, framework и основных tools не должны расходиться между несколькими файлами.

Если значение вычислимо из одного source of truth — вычислять, а не копировать.

По прямому поручению OWNER от 09.10.2026 общие параметры поддерживаются так:

- версия приложения задаётся только в `[project].version` файла `pyproject.toml`;
  backend читает metadata установленного пакета, а сборка выводит из неё HTML,
  `version.js`, offline shell и service worker. Заголовки API, OpenAPI и provider
  User-Agent используют ту же версию. Версия движка, каталога, схемы, legal
  документов и исторического перехода БД — самостоятельные контракты;
- названия и переводы интерфейса имеют единственный каталог `web/i18n.js`;
  палитра и её семантические CSS variables — `web/tokens.css`, общие числовые
  настройки интерфейса — `web/config.js`. Потребители используют именованные
  параметры; сборка и offline cache обязаны включать их в тот же выпуск;
- повторяющиеся backend интервалы, лимиты и математические параметры имеют
  именованные определения в существующем модуле соответствующей ответственности
  либо в небольшом общем модуле с реальными потребителями. `config.py` остаётся
  единственным читателем environment variables;
- у общего числа указываются смысл, единицы и допустимые границы. Параметры
  различного смысла не объединяются только из-за совпадения чисел; локальные
  переменные вычисления и буквальные значения протокола не становятся глобальной
  изменяемой конфигурацией;
- изменение общего параметра проверяется через его действующих потребителей;
  производные значения вычисляются, а не поддерживаются вручную в нескольких местах.

## 7. Зависимости

Новая dependency разрешена только если:

1. стандартная библиотека не решает задачу разумно;
2. уже установленная dependency не решает задачу;
3. dependency активно поддерживается;
4. лицензия и security приемлемы;
5. она уменьшает суммарную сложность проекта;
6. удаление dependency в будущем не требует переписывания всей business logic.

Запрещено устанавливать большую библиотеку ради одной тривиальной функции.

Каждое удаление dependency должно удалять и все оставшиеся imports/configuration, если consumers отсутствуют.

## 8. Архитектурные границы

Разделять:

- Android UI/state boundary;
- local secret/data boundary;
- common Timeweb API boundary;
- business logic;
- local persistence;
- common persistence;
- provider adapter;
- deployment/release tooling.

В local-first Android архитектуре персональный portfolio authority находится на устройстве пользователя: локальная защищённая БД + проверенные ответы T-Invest. Серверный request parameter, push payload, purchase entitlement или общий instrument API не могут назначить/подменить локальный портфель.

T-Invest credential запрещено возвращать в OMNICIO API response, логировать, отправлять в crash reporting/AI или сохранять на Timeweb в новом Android потоке. Он вводится пользователем только на устройстве, хранится через Keystore и используется приложением напрямую против официального T-Invest API.

Legacy web authority (email/session/tenant/RLS) продолжает действовать только для существующих legacy endpoints до их проверенного удаления. Новый Android код не должен воспроизводить server-side account/session architecture без отдельной необходимости.

Local app state не предоставляет broker write authority.

Deployment не предоставляет broker write authority.

Merge не предоставляет broker write authority.

AI output не предоставляет broker write authority.

Purchase entitlement не предоставляет broker write authority.

Любые чувствительные действия должны иметь отдельную явную authority boundary.

## 9. PostgreSQL

PostgreSQL является relational authority после принятого production cutover.

Правила:

- tenant isolation проектировать с первого schema change;
- runtime role — least privilege;
- использовать RLS и FORCE RLS там, где таблица tenant-bound;
- browser/request input не выбирает tenant authority;
- production runtime role не получает superuser, create role, create database, replication или bypass RLS;
- accepted production migration после выпуска не переписывать;
- content уже выпущенных migration закреплять regression-digest проверкой; изменение digest accepted migration является RED;
- PostgreSQL migration проверять каноническим PostgreSQL-native integration test на поддерживаемой production major version там, где CI/runtime предоставляет тестовый PostgreSQL; Oracle PL/SQL analyzer не является authority для PostgreSQL dialect;
- изменение schema делать новой migration;
- migration должна быть детерминированной;
- retry/idempotence проверять там, где workflow допускает повтор;
- частично применённая migration не должна оставлять систему в неизвестном состоянии;
- destructive migration требует отдельного recovery plan;
- перед production schema mutation иметь проверяемую recovery точку; прямое поручение владельца от 08.10.2026 устанавливает отдельный узкий переход 1.2.0 → 1.3.0 в существующем кластере без новых копий. Для него допускаются только проверенные по digest 0027–0028 в одной транзакции, с проверкой исходной установки, схемы до/после и повторным чтением результата при неопределённом ответе. Исторические миграции, bootstrap конфигурации и произвольный SQL этим исключением не разрешены. Транзакционный откат не является подтверждением восстановления базы; требование Sonar §18 сохраняется;
- production использует один существующий кластер 4215095. Режим single_existing_database не создаёт клоны, дополнительные кластеры, новые физические/логические копии или платные хранилища; существующие резервные данные не удаляются. Ручной экспорт production в CI этим режимом запрещён. Политика и состояние копий отображаются отдельно от готовности приложения;
- новые Android common-intelligence таблицы не получают tenant/user columns без реального server-side consumer;
- legacy публичный profile ID/email identity/session/auth таблицы продолжают защищаться существующими правилами только до проверенного удаления legacy web consumer; новый Android identity на них не строится;
- существующие legacy broker credentials не раскрывать/не логировать и не переносить автоматически в Android; пользователь заново вводит read-only credential локально;
- новый Android поток не создаёт server-side broker credential row;
- local app не отправляет заявки или переводы; сохранённая локальная стратегия является входом аналитического/scenario engine, а не broker authority.

## 10. Timeweb

Перед provider-sensitive изменением сверять актуальную официальную документацию Timeweb.

Не предполагать, что provider state мгновенно отражает data plane.

Разделять:

- control-plane proof;
- data-plane proof;
- application readiness.

Правила provider mutation:

1. точно идентифицировать resource;
2. проверить precondition;
3. выполнить минимальную mutation;
4. при однозначном success прочитать состояние снова;
5. catalog/preset/configurator presence не считать доказательством runtime capacity;
6. capacity моделировать на уровне фактического placement candidate: конфигурация + регион + availability zone, если provider разделяет эти понятия;
7. при timeout/423/ambiguous response и при любом provider error без детерминированного доказательства результата не повторять mutation вслепую;
8. capacity классифицировать по документированному/наблюдаемому provider `error_code`, а не только по HTTP status; placement-level refusal (например, Timeweb `no_free_node`) разрешает перейти к следующему заранее допустимому placement, а location-level refusal (например, `servers_is_run_out_error`) закрывает остальные candidates этой location без новых mutation;
9. capacity fallback не может повышать утвержденный cost/security/configuration contract;
10. persistent desired-state retry разрешен только когда desired state и cost ceiling явно versioned в репозитории и одобрены OWNER; retry должен быть serialized, bounded по каждому run и прекращать provider mutation сразу после достижения desired state;
11. после ambiguous/conflict результата выполнить bounded read-only reconciliation и только после доказательства состояния принимать следующее решение.

Никогда не ослаблять TLS, firewall или tenant security ради успешного deployment.

Для post-provisioning доступа к Timeweb VDS из CI:

- не хранить root-пароль в GitHub;
- использовать краткоживущий SSH-ключ, приватная часть которого существует только на runner;
- публичный ключ добавлять к точно идентифицированному managed server через provider API;
- SSH host key сервера независимо сверить в аутентифицированной консоли Timeweb и передать как одну запись `IPv4 ssh-ed25519 public-key` через `TIMEWEB_SSH_KNOWN_HOSTS`; не превращать непроверенный `ssh-keyscan` в источник доверия; отсутствие или смена ключа блокирует SSH до повторной сверки;
- cleanup SSH-ключа выполнять даже при ошибке конфигурации;
- secret-bearing SSH/provider job запускать только из accepted `main`;
- перед выпуском TLS доказывать, что DNS указывает на управляемый сервер; stale AAAA не игнорировать.

Для App Platform через Dockerfile:

- production Dockerfile должен иметь понятный startup contract;
- EXPOSE должен соответствовать реально слушаемому порту;
- secrets не встраивать в image;
- health endpoint должен быть дешёвым и детерминированным;
- readiness должна отдельно доказывать критические dependencies, если они обязательны;
- private network выбирать осознанно при создании приложения, потому что этот выбор нельзя считать легко обратимым;
- release привязывать к точному accepted GitHub main SHA;
- autodeploy не является release authority.

## 11. Secrets

Никогда не хранить в Git:

- passwords;
- API tokens;
- database DSN с credential;
- Telegram secrets;
- private keys;
- session signing secrets;
- Timeweb credentials.

Secrets находятся только в защищённом GitHub/Timeweb custody.

Код из pull request / feature branch никогда не получает production provider secrets. Secret-bearing deploy/reconcile job может исполнять только accepted `main` (или отдельный явно одобренный release ref с эквивалентной защитой).

Никогда не печатать secrets в logs, exceptions, screenshots, fixtures или test output.

Логи должны содержать безопасный error code и минимально необходимый operational context.

## 12. Ветка разработки

Никогда не разрабатывать непосредственно в main.

Для одной coherent задачи:

1. получить свежий main;
2. убедиться, что нет конфликтующей активной ветки;
3. создать одну focused branch;
4. выполнить всю задачу в этой ветке;
5. не смешивать независимые feature/cleanup/repair без необходимости.

Название ветки должно описывать результат, а не временное действие.

Долгоживущие ветки избегать.

## 13. Обязательный цикл разработки

Для каждого material change использовать:

### Observe

- прочитать фактический current code;
- прочитать callers и consumers;
- проверить configuration;
- проверить current main / branch / diff;
- при provider task проверить актуальный provider contract;
- при bug task получить точный failure evidence.

### Model

Сформулировать:

- ожидаемое поведение;
- invariants;
- data flow;
- authority flow;
- failure states;
- rollback/recovery;
- acceptance criteria.

### Challenge

До реализации проверить:

- malformed input;
- empty input;
- duplicate input/state;
- stale state;
- partial state;
- timeout;
- retry;
- race;
- restart;
- replay;
- unauthorized state;
- revoked state;
- schema drift;
- provider drift;
- rollback;
- second consumer;
- semantic twin в другом модуле.

### Implement

- минимальный coherent diff;
- reuse-first;
- без дублирования;
- без speculative architecture;
- удалить заменённый dead code в той же задаче.

### Verify

Проверять применимое:

- format;
- lint;
- typing;
- unit;
- integration;
- regression;
- security;
- secret scan;
- dependency audit;
- database;
- frontend build;
- browser;
- accessibility;
- production image build;
- runtime health;
- changed-surface review.

### Reopen

После успешных тестов заново открыть каждый изменённый файл и проверить:

- действительно ли код делает то, что планировалось;
- нет ли dead code;
- нет ли duplicate code;
- нет ли stale imports;
- нет ли лишней dependency;
- нет ли расширения permissions;
- нет ли нарушения tenant/security/recovery boundary.

Green test не заменяет Reopen review.

## 14. Разработка feature

До кода сформулировать Definition of Done.

Feature нельзя merge, пока не реализованы все обязательные пункты Definition of Done, даже если CI полностью green.

Алгоритм:

1. записать конечный пользовательский/system outcome;
2. определить acceptance criteria;
3. найти существующие реализации;
4. выбрать минимальное изменение;
5. реализовать основной happy path;
6. реализовать обязательные failure paths;
7. добавить только необходимые тесты;
8. проверить consumers;
9. удалить заменённый dead code;
10. проверить полный diff;
11. сверить результат с каждым acceptance criterion;
12. только затем считать feature complete.

Не дробить одну маленькую feature на множество файлов только ради "чистой архитектуры".

Но также не превращать один файл в набор несвязанных подсистем.

## 15. Исправление ошибки

Ошибка исправляется по причине, а не по симптому.

Алгоритм:

1. получить точный failing SHA;
2. получить exact log/error;
3. определить первый слой, где фактическое состояние расходится с ожидаемым;
4. найти producer;
5. найти consumers;
6. найти semantic twins;
7. определить, почему существующий guard/test не обнаружил defect;
8. исправить defect class минимальным coherent изменением;
9. добавить regression protection;
10. проверить adjacent failure states;
11. заново выполнить применимые проверки;
12. перечитать changed files;
13. не закрывать bug только потому, что исходный error message исчез.

Если исправление просто скрывает ошибку, catch-ит её без корректного результата, выключает тест, снижает assertion, coverage или security — это не исправление.

## 16. RED режим

Material failure переводит текущий head в RED.

В RED режиме:

- head считать замороженным;
- не добавлять независимые features;
- сначала определить root cause;
- исправить один coherent defect set;
- создать replacement head;
- применимые проверки должны пройти на replacement head.

Нельзя получать GREEN через:

- continue-on-error;
- отключение теста;
- skipped required check;
- ослабление assertion;
- исключение файла из проверки ради скрытия ошибки;
- снижение coverage threshold;
- fail-open;
- расширение permissions;
- удаление security guard.

Повторить тот же head допустимо только при доказанном transient infrastructure failure без изменения source.

## 17. Тесты без тестового мусора

Тест должен защищать важное поведение, а не существовать ради количества.

Для нового поведения обычно достаточно:

- happy path;
- ключевой boundary/failure path;
- regression test для найденного defect.

Добавлять больше тестов только когда разные failure classes реально различаются.

Не дублировать одинаковую проверку в пяти test files.

Fixtures должны быть небольшими и переиспользуемыми, если есть реальные повторные consumers.

Не создавать tests для private implementation detail, если observable contract можно доказать проще.

Integration test предпочтительнее большого набора mock-heavy tests, когда реальная boundary дешёвая и детерминированная.

Provider destructive integration tests не запускать против production без отдельной authority.

## 18. CI

CI должен быть минимальным, но достаточным.

Предпочитать один основной CI workflow с независимыми jobs вместо множества почти одинаковых workflow-файлов.

Разделять workflow только когда есть реальная граница:

- release/deploy authority;
- production mutation;
- secret/environment custody;
- platform-specific runner;
- отдельный destructive gate.

Required check относится к exact latest head.

Старый green SHA не сертифицирует новый commit.

Queued, pending, cancelled и failure не являются green.

Skipped/neutral допустимы только если pipeline явно и корректно доказал, что check не применим к этому change.

SonarQube Cloud является обязательным code-quality gate изменений в pull request.
Прямое поручение OWNER от 09.10.2026 заменяет прежнее требование успешного анализа
`main`: лимит LOC и результат анализа `main` не блокируют merge или production.
Новая политика не заявляет, что PR analysis проверяет весь накопленный код.

- Quality Gate = success необходим, но сам по себе недостаточен;
- на exact latest PR head unresolved New/Open issues = 0;
- Accepted issues = 0 и unresolved GitHub/Sonar annotations = 0;
- нельзя получать green отключением правил, исключением production-кода из корректного для его языка analyzer, снижением quality threshold или переводом реального дефекта в Accepted;
- language/dialect mapping обязана быть корректной: PostgreSQL `.sql` нельзя анализировать как Oracle PL/SQL только из-за расширения; если Sonar не поддерживает production dialect, PostgreSQL correctness доказывается каноническим migration integration test и production reconciler, а исправление mapping не отменяет эти проверки;
- immutable accepted migration нельзя переписывать только ради удовлетворения правила analyzer, неприменимого к её фактическому dialect;
- перед merge проверяется результат доверенного Sonar GitHub App именно для текущего PR и его latest head; cancelled, pending, stale или относящийся к другой ветке результат не считается успешным;
- перед production проверяется происхождение exact accepted `main` из реально merged PR того же репозитория, равенство принятого Git tree проверенному дереву PR и успешный Sonar этого PR; прямой push, непроверенный merge conflict resolution или смена head требует нового проверенного PR;
- все остальные применимые проверки текущего `main`, проверки исходников, безопасности, PostgreSQL и браузера остаются обязательными. Число строк не является показателем качества кода; найденный реальный дефект устраняется независимо от статуса анализатора.

## 19. Green != Complete

Это обязательное правило.

Нельзя merge только потому, что все проверки зелёные.

Перед merge отдельно проверить:

- все ли задачи текущей ветки реализованы;
- все ли acceptance criteria выполнены;
- не осталась ли запланированная часть feature;
- нет ли TODO/FIXME вместо обязательной реализации;
- нет ли dead/duplicate code;
- нет ли неиспользуемых dependencies;
- нет ли временного bypass;
- соответствует ли реальное поведение заявленному результату.

Если CI green, но feature не закончена — продолжить разработку в этой же ветке.

## 20. Ready и merge

Перед Ready:

- branch основана на актуальном main либо divergence осознанно устранён;
- полный diff известен;
- scope coherent;
- acceptance criteria выполнены;
- exact head checks terminal success;
- blocking review threads = 0;
- нет unresolved material issue;
- changed files повторно прочитаны.

Предпочтительный merge: squash merge.

После merge:

1. получить новый exact main SHA;
2. подтвердить, что merge действительно попал в main;
3. запустить/проверить post-merge gates, если они применимы;
4. только accepted main может стать release candidate.

Merge не означает deployment.

## 21. Release

Release candidate строится только из exact accepted main.

Нельзя release:

- произвольную feature branch;
- старый commit;
- локально изменённое дерево;
- image неизвестного происхождения.

Перед production promotion проверить:

- liveness;
- readiness;
- release identity;
- database identity;
- TLS;
- secrets/config;
- rollback target;
- critical user path.

На RED production остаётся last known good.

## 22. Frontend и assets

Продуктовый scope задаёт `docs/ui-plan.md`; инвестиционное ядро — `docs/system-plan.md`. Новые функции вне этих двух планов не добавлять. Устаревшие десять разделов, сложный каталог именованных стратегий, избранное, пользовательский ИИ-чат, графики и рыночная новостная лента не являются требованиями нового интерфейса.

Обзор ставит стоимость, выбранный счёт, доступные для новых покупок деньги и одно существенное действие перед подробностями. Портфель показывает все позиции без тарифной квоты количества: идентификатор, количество, лот, стоимость, доля, состояние данных. Поиск и постраничная/виртуальная выдача не ограничивают общее количество активов. Помощник содержит текущий план и существенную историю событий; сохранённое объяснение открывается без нового LLM-запроса.

Компактное оформление использует собственные компоненты OMNICIO, нейтральную светлую и согласованную тёмную тему, ясную типографику и жёлтое основное действие. Т-Инвестиции — ориентир понятности, а не разрешение копировать бренд, изображения или создавать впечатление официальной принадлежности. Цвет не является единственным носителем статуса. Сохраняются читаемость, клавиатура, доступный фокус, reduced-motion и мобильные зоны нажатия.

Денежные показатели имеют валюту, период, источник, метод и время. Не подменять инвестиционный результат разницей снимков стоимости. Неизвестное не равно нулю. Баланс, доступность покупки, подтверждённые и ожидаемые выплаты — разные показатели. При частичных/устаревших данных показать предел расчёта. Каждая кнопка имеет реальный consumer и состояния загрузки, успеха, ошибки или недоступности.

Цель, срок, резерв, способность переносить убытки, валюта цели и использование выплат сохраняются на сервере с проверкой версии. Система может предложить черновик, но не угадывает личные обстоятельства и не подтверждает риск-профиль за человека. Загрузка, сохранённое значение и несохранённая правка имеют приоритет над defaults. Ошибка чтения не разрешает перезаписать профиль. Запоздалый ответ другого аккаунта/версии не стирает правку; при 409 показывается конфликт. Изменение условий делает прежний зависимый план неактуальным.

В production нет синтетических балансов, доходности, новостей, вероятностей дефолта и фиктивных рекомендаций. UI-этап проверяет ещё не подключённые сценарии на явно обозначенных изолированных test/preview fixtures. В личном кабинете production такая функция имеет честное состояние «расчёт пока недоступен». Макет не становится готовой платной функцией.

Пользователь сам совершает действия у брокера. Ссылка не равна исполнению, а сохранение настроек не даёт торговых полномочий. План привязан к снимку портфеля, рынку и версии условий; новый план заменяет старый, один бюджет не расходуется дважды. Не обещать прибыль, защиту от всех кризисов, безошибочное предсказание банкротства или гарантированную доставку уведомления.

`assets/brand` остаётся каноническим хранилищем исходных ресурсов бренда. Не копировать один visual asset в несколько мест. Generated assets получают версию из `pyproject.toml`; производный файл коммитится только при реальном build/runtime consumer. Переиспользовать компоненты без универсальной абстракции ради одного случая.

Короткая контекстная помощь объясняет назначение, выбранное значение, последствия и условный пример простыми русскими словами. В продукте не показываются endpoint, токены LLM, промпты, внутренние очереди или инженерные пороги. Математическая доверительная оценка не обозначается вероятностью прибыли.

## 23. Documentation economy

AGENTS.md — единственный development-process law. Прямое поручение владельца от 10.10.2026 разрешает ровно два канонических продуктовых плана: `docs/ui-plan.md` и `docs/system-plan.md`. Они содержат scope и критерии 6 + 12 выпусков, не дублируют этот процесс и не размножаются в 18 отдельных документов.

Не создавать отдельный markdown-файл для каждого bug, branch, CI failure или промежуточного этапа.

Для рабочего evidence использовать GitHub PR/issue/comments/checks.

Отдельный repository document допустим только если это часть работающей системы, например:

- API contract;
- database schema contract;
- operational runbook, реально необходимый оператору;
- legal/public document;
- machine-readable contract.

Если документ перестал иметь current consumer — удалить.

## 24. Cleanup

При каждом изменении проверять, что можно безопасно удалить в пределах scope.

Удалять:

- dead code;
- unreachable code;
- unused import;
- unused dependency;
- orphan config;
- obsolete feature flag;
- retired provider adapter;
- duplicate helper;
- old generated file;
- obsolete instruction;
- stale test, проверяющий удалённое поведение.

Перед удалением доказать отсутствие текущего consumer.

Не удалять accepted production migration или recovery-critical artifact без отдельного decommission proof.

## 25. Security review

Перед публикацией material change посмотреть на него с пяти точек зрения:

1. attacker;
2. tenant A против tenant B;
3. operator;
4. reviewer;
5. rollback/recovery.

Проверить:

- privilege expansion;
- IDOR;
- tenant selection from client;
- secret leakage;
- unsafe defaults;
- replay;
- race;
- partial failure;
- ambiguous provider mutation;
- fail-open;
- unsafe logging;
- uncontrolled external input.

## 26. Экономия разработки

Всегда выбирать решение с минимальной общей стоимостью владения, а не минимальным количеством строк в одном commit.

Экономное решение:

- меньше файлов;
- меньше dependencies;
- меньше duplicate paths;
- меньше provider-specific business logic;
- меньше configuration sources;
- меньше CI duplication;
- меньше ручных действий;
- больше reuse;
- более простая recovery;
- более точные тесты.

Не оптимизировать преждевременно производительность, если нет измеренного bottleneck.

Не строить систему на гипотетические будущие требования.

## 27. Обязательный вопрос перед новым кодом

Перед написанием новой функции, класса, файла или workflow разработчик обязан ответить:

1. Есть ли уже код, который это делает?
2. Можно ли изменить существующий код?
3. Почему нужен новый symbol/file?
4. Кто будет его consumer?
5. Как он будет тестироваться?
6. Как он будет удалён/заменён в будущем?
7. Создаёт ли он новую authority/security boundary?
8. Можно ли решить задачу меньшим количеством кода?

Если ответы неубедительны — новый код не создавать.

## 28. Обязательный вопрос перед merge

Перед merge разработчик обязан ответить:

1. Что именно обещала эта ветка?
2. Всё ли обещанное реализовано?
3. Что доказано тестами?
4. Что тесты не могут доказать?
5. Проверено ли это вручную/интеграционно там, где нужно?
6. Какие failure states проверены?
7. Какие semantic twins найдены?
8. Удалён ли заменённый dead code?
9. Нет ли дублирования?
10. Есть ли credible rollback/recovery?
11. Exact head полностью проверен?
12. Не осталось ли причины продолжать эту же ветку?

Если хотя бы один обязательный пункт не закрыт — merge запрещён.

## 29. Изменение этого закона

AGENTS.md можно улучшать по мере взросления проекта.

При изменении закона:

- не создавать второй policy file;
- изменять существующее правило вместо добавления конфликтующего;
- удалять устаревшие правила;
- сохранять документ коротким настолько, насколько это возможно без потери обязательных invariants;
- при конфликте двух правил сначала устранить конфликт в этом файле, затем продолжать разработку.

## 30. Нормативные внешние ориентиры

При необходимости сверяться с первичными источниками:

- Python PEP 8: https://peps.python.org/pep-0008/
- Python PEP 20: https://peps.python.org/pep-0020/
- Python typing: https://typing.python.org/
- GitHub protected branches: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- GitHub status checks: https://docs.github.com/en/pull-requests/reference/status-checks
- Timeweb App Platform Dockerfile: https://timeweb.cloud/docs/apps/deploying-with-dockerfile
- Timeweb App Platform health check: https://timeweb.cloud/docs/apps/healthcheck-path

## 31. Короткая формула

Ищи -> переиспользуй -> моделируй -> делай минимальный diff -> проверяй failure states -> доказывай -> перечитывай -> только потом merge.

Не создавай вторую реализацию, если можно сделать правильной первую.

Не путай GREEN с COMPLETE.

Не исправляй симптом, если можно исправить класс дефекта.

Не усложняй систему без доказуемой необходимости.

Сделай систему правильной, затем докажи это.

