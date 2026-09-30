# Omni-CIO Development Law

Статус: CANONICAL / REQUIRED  
Область действия: весь текущий и будущий код репозитория  
Назначение: единый закон разработки без дублирующих процессных инструкций

## 1. Главный принцип

Этот файл — единственная каноническая инструкция разработчика проекта.

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
- авторизация по российскому мобильному номеру `+79XXXXXXXXX` через одноразовый SMS-код — выбранный human login;
- Python — основной backend/runtime язык, если задача не требует другого языка;
- браузерный frontend — только тот код, который реально нужен сайту.

Не добавлять Cloudflare, Neon, Render, VK ID, Cloud.ru и другие старые provider-зависимости без нового явного решения OWNER.

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

- pyproject.toml — Python dependencies и tooling configuration;
- один lock/source dependency mechanism;
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

SMS OTP подтверждает владение конкретным российским мобильным номером в формате `+79XXXXXXXXX`. После успешной проверки сервер сам разрешает internal user/session. Публичный 9-значный profile ID является только идентификатором для UI/поддержки и никогда не предоставляет authority.

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
- изменение schema делать новой migration;
- migration должна быть детерминированной;
- retry/idempotence проверять там, где workflow допускает повтор;
- частично применённая migration не должна оставлять систему в неизвестном состоянии;
- destructive migration требует отдельного recovery plan;
- перед production schema mutation иметь проверяемую recovery точку;
- публичный profile ID генерировать сервером/БД из монотонной sequence, не принимать его от browser;
- телефон хранить encrypted-at-rest, а поиск/unique constraint выполнять по keyed blind index; полный телефон и OTP запрещены в логах;
- OTP хранить только как keyed digest, ограничивать TTL, число попыток, resend и hourly rate;
- session token хранить у клиента только в Secure + HttpOnly + SameSite cookie, а в БД хранить только digest;
- production registration fail-closed: до готовых legal documents, реквизитов оператора ПД и SMS provider registration должна оставаться выключенной.

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

Не копировать один и тот же visual asset в несколько мест.

assets/brand является каноническим хранилищем исходных brand resources, пока архитектура явно не изменена.

Если frontend pipeline требует generated asset:

- source остаётся один;
- generated output не дублируется вручную;
- generated file коммитить только если runtime/build действительно требует этого.

Переиспользовать компоненты, но не создавать universal component ради одного использования.

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
