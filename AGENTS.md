# OMNICIO 1.2.0 — Development Law

Статус: CANONICAL / REQUIRED  
Область действия: весь текущий и будущий код репозитория  
Назначение: единый закон разработки без дублирующих процессных инструкций

## 1. Главный принцип

Этот файл — единственная каноническая инструкция разработчика проекта.

Продуктовое основание редакции: прямое поручение владельца от 06.10.2026 о полной переработке OMNICIO по эталону `docs/reference/omnicio-1.0.0.png`. Эталон задаёт композицию и набор функций; показанные на нём суммы, новости, показатели надёжности и доходности не являются реальными данными. Новый продуктовый контракт и текущая готовность описываются в README.md. Старый план R0–R17 больше не определяет порядок новой разработки. Сохранение проверенных инфраструктурных и защитных компонентов допускается только при наличии текущего потребителя; переименование старого интерфейса не считается переработкой.

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

Поддерживаемая производственная архитектура строится только вокруг:

- GitHub — код, ветки, pull request, CI, review и release provenance;
- Timeweb Cloud — production runtime, App Platform, сеть, секреты и PostgreSQL;
- production OmniCIO Personal использует многопользовательскую tenant-модель с ограничиваемой регистрацией; лимит новых аккаунтов задаётся server-side `REGISTRATION_MAX_USERS`, а существующий подтверждённый пользователь продолжает входить независимо от заполнения лимита;
- human login — VK ID OAuth 2.1 + PKCE и T-ID Authorization Code с серверным обменом; подтверждённая пара provider/subject связывается ровно с одним `user_id`, новые identity создаются только при открытой регистрации и наличии server-side capacity; browser input не определяет tenant authority и не может назначить роль/профиль. Провайдер без выданных реквизитов не изображается работающим; вход не предоставляет доступ к брокеру. Объединение аккаунтов по совпадению email или имени запрещено;
- T-Invest credential всегда принадлежит конкретному `user_id`, вводится только в аутентифицированной сессии этого пользователя, проверяется сервером и хранится только в зашифрованном виде; данные разных пользователей нельзя смешивать или читать по browser-provided identity;
- self-service удаление аккаунта допускается только из действующей server-side сессии текущего пользователя, требует повторного подтверждения собственного публичного profile ID, не принимает `user_id`/VK ID из браузера как authority и в одной транзакции удаляет user row с каскадным удалением VK identity, сессий, legal acceptances и T-Invest connection; анонимизированный security audit event может сохраняться без идентификатора пользователя;
- публичные legal pages обязаны описывать фактически включённый access mode и не публикуют домашний адрес, ИНН, паспортные или иные избыточные персональные реквизиты OWNER;
- обычное production-включение `REGISTRATION_ENABLED=true` требует актуальных legal documents, явного versioned `MULTIUSER_LEGAL_APPROVED=true`, подтверждённого regulatory gate и опубликованных реквизитов оператора; отдельное явно одобренное OWNER исключение `CONTROLLED_LIVE_TEST_MODE=true` допускается только для временного live-test максимум с двумя пользовательскими аккаунтами (`REGISTRATION_MAX_USERS<=2`), без утверждения о наличии regulatory confirmation, с неизменным `RKN_NOTIFICATION_CONFIRMED=false`; при попытке увеличить лимит выше 2 без regulatory gate production deploy обязан fail closed;
- Python — основной backend/runtime язык, если задача не требует другого языка;
- браузерный frontend — только тот код, который реально нужен сайту;
- основная навигация: Главная, Портфель, Рынок, Стратегии, ИИ-помощник, Цели, Аналитика, События, Профиль, Настройки. На широком экране — постоянный sidebar; на мобильном — нижняя панель Главная/Рынок/ИИ/Стратегии и drawer полного меню. Один реестр маршрутов управляет обеими панелями, History API/back и выбранным разделом; навигация не меняет tenant/session authority. Внутренние инструменты, восстановление, подключения и уведомления размещаются в соответствующем разделе, а не добавляют старые самостоятельные пункты;
- мобильный installed PWA предпочитает fullscreen display с standalone fallback и safe-area CSS; обычная browser tab не должна пытаться обходить browser/OS security для скрытия системных панелей, а Fullscreen API вызывается только из явного пользовательского действия;
- история брокерских операций используется сервером для реальной аналитики: отделение пополнений и выводов, дохода, возврата капитала, комиссий и налогов. Любой персональный ответ ограничивается действующей сессией. Изменение стоимости портфеля нельзя выдавать за доходность, а абсолютную прибыль позиции — за процент.

Не добавлять Cloudflare, Neon, Render, Cloud.ru и другие provider-зависимости без нового явного решения OWNER. VK ID и T-ID являются явно одобренными human-login providers. Существующий GitHub/Timeweb выпуск остаётся целевой платформой.

Нельзя оставлять в рабочем дереве старый исполняемый код "на всякий случай". Git history является архивом.

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

- HTTP/UI boundary;
- authentication/session boundary;
- tenant authority;
- business logic;
- persistence;
- provider adapter;
- deployment/release tooling.

Browser input никогда не является источником tenant authority.

VK ID подтверждает внешнюю идентичность через Authorization Code flow с PKCE. Tenant authority определяется только server-side связью `vk_user_id -> user_id`; callback/query/browser input не может назначить другой профиль, роль или tenant. OAuth `state` обязателен, flow имеет короткий TTL, access/refresh tokens VK ID не являются сессией OmniCIO и не сохраняются после получения подтверждённого `vk_user_id`. Публичный 9-значный profile ID является только идентификатором для UI/поддержки и никогда не предоставляет authority.

Сохранённый T-Invest credential запрещено возвращать в browser/API response, логировать или хранить в открытом виде. Browser может передать новый credential только для проверки/замены в уже аутентифицированной owner-сессии. Выбранный broker account обязан повторно подтверждаться через provider перед сохранением.

Login не предоставляет broker write authority.

Deployment не предоставляет broker write authority.

Merge не предоставляет broker write authority.

AI output не предоставляет broker write authority.

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
- публичный profile ID генерировать сервером/БД из монотонной sequence, не принимать его от browser;
- VK ID owner identity хранить как проверенный provider subject, полученный только после успешного code exchange и user-info запроса;
- PKCE verifier/state хранить только в краткоживущем зашифрованном Secure + HttpOnly + SameSite=Lax flow cookie и удалять после callback;
- session token хранить у клиента только в Secure + HttpOnly + SameSite cookie, а в БД хранить только digest;
- VK ID login fail-closed при отсутствии валидного `VKID_APP_ID` или provider failure; создание новой identity дополнительно fail-closed при закрытой регистрации, исчерпанном `REGISTRATION_MAX_USERS` или неполных legal/regulatory gates;
- broker credential хранить только encrypted-at-rest отдельным server-side ключом, не возвращать через API и не включать в audit/log metadata;
- login/session не дают broker write authority; любые будущие реальные торговые действия требуют отдельного execution/risk boundary и явной authorization модели.

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

SonarQube Cloud является обязательным code-quality gate:
- Quality Gate = success необходим, но сам по себе недостаточен;
- на exact latest head unresolved New/Open issues = 0;
- Accepted issues = 0 и unresolved GitHub/Sonar annotations = 0;
- нельзя получать green отключением правил, исключением production-кода из корректного для его языка analyzer, снижением quality threshold или переводом реального дефекта в Accepted;
- language/dialect mapping обязана быть корректной: PostgreSQL `.sql` нельзя анализировать как Oracle PL/SQL только из-за расширения; если Sonar не поддерживает production dialect, PostgreSQL correctness доказывается каноническим migration integration test и production reconciler, а исправление mapping не отменяет эти проверки;
- immutable accepted migration нельзя переписывать только ради удовлетворения правила analyzer, неприменимого к её фактическому dialect;
- перед feature merge accepted `main` также должен иметь 0 unresolved Sonar issues; обнаруженный debt сначала устраняется отдельной focused cleanup-веткой;
- baseline проверяется свежим анализом exact current `main` и актуальным unresolved issue inventory; исторический summary старого commit/check не считается текущим состоянием после последующих исправлений.

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

Интерфейс 1.0.0 создаётся вокруг плотной сетки эталона, а не путём накопления CSS-исправлений старого кабинета. Каждая видимая кнопка имеет действующий consumer и состояния загрузки/успеха/ошибки/недостатка данных. Цели, избранное и пользовательские настройки сохраняются на сервере с version check; ошибка загрузки не разрешает перезаписать сохранённое состояние defaults. В production нет синтетических балансов, графиков, новостей, вероятностей успеха и фиктивных уведомлений. Тестовые fixtures находятся только в tests. Ознакомительный режим не подменяет реальные показатели; отсутствие источника обозначается явно. ИИ является отдельным подключаемым сервисом и не получает полномочий на сделки. Каталог содержит десять подходов эталона: Сбалансированная, Консервативная, Агрессивная, Доходная, Накопление, Стратегия Баффета, Стратегия Богла, Стратегия Далио, Лестница облигаций, Дивидендная. Математические результаты содержат период, данные, метод и ограничения; подбор параметров на будущем запрещён.

Не копировать один и тот же visual asset в несколько мест.

assets/brand является каноническим хранилищем исходных brand resources, пока архитектура явно не изменена.

Если frontend pipeline требует generated asset:

- source остаётся один;
- generated output не дублируется вручную;
- generated file коммитить только если runtime/build действительно требует этого.

Переиспользовать компоненты, но не создавать universal component ради одного использования.

Числовые настройки профиля и policy проектировать touch-first: единицы измерения,
доступные без обязательного ввода точные шаги и осмысленные ограниченные диапазоны/варианты.
Каждая настройка и общий control получают контекстную помощь через канонический HelpButton.
Короткая справка объясняет назначение, закреплённая — выбранное значение, последствия
увеличения/уменьшения или включения/выключения, условный пример и границы функции.
Использовать простые русские слова. Значения примера не выдавать за данные счёта;
сохранённый параметр без действующего расчётного consumer прямо описывать как таковой.
Не обещать доход, предел убытка, исполнение сделки или доставку уведомления текстом подсказки.
Стартовые значения являются только явно обозначенным черновиком: успешная загрузка,
сохранённые значения и несохранённая правка всегда приоритетнее, а ошибка загрузки не
разрешает молча подставлять или сохранять defaults.
Клавиатурная доступность сохраняется, но ввод чисел не обязателен. Анимация сопровождает
смену состояния, не работает непрерывно и учитывает prefers-reduced-motion.
Согласия, торговые полномочия и разрешения повышенного риска остаются явным opt-in.

Автосохранение рабочей стратегии: любая фактическая правка параметра переводит копию
в «Пользовательскую». Исходные templates не меняются. Сервер хранит рабочую копию
отдельно от подтверждённых profile/policy; сохранение не даёт торговых полномочий.
Дебаунс и single-flight обязательны; ответ старой версии/другого аккаунта не стирает
новую правку. При 409 — явное разрешение конфликта, при неопределённом результате —
сверка, а не «Сохранено». Шаблоны не переустанавливают личные суммы и неизвестные факты.
Методика, инженерные параметры, историческая проверка и вероятность результата —
разные сущности. Не выдавать математический confidence level за вероятность прибыли.

## 23. Documentation economy

AGENTS.md — единственный development-process law.

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
