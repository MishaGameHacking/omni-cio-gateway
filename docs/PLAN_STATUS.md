## 28.10.2026 — инвестиционный OSINT развёрнут на существующем сервере

Текущий backend: `94f42c48ac4073e7750c78e396bc661da4b31be0`, ветка `codex/investment-osint-2026-10-28`,
PR 891. Это продолжение прямого запроса владельца на сбор/обработку публичных
инвестиционных данных. После уточнения о локальном Codex владелец явно вернулся
к прежней задаче и снова указал GitHub. Проверки — на LAPTOP-NPSGA016 / WSL;
рабочее исполнение и данные — существующий Timeweb9417611. Новых серверов нет.
APK50 остаётся прежним. Не менять интерфейс, торговые полномочия или платные модели
в рамках этой задачи.

Run40703109199: 2224 теста +1557 подтестов; Sonar точного source HEAD без замечаний.
Deploy40704536699 SUCCESS, предыдущая полная установка40700323988 SUCCESS.
На 2026-10-28T14:41:11.448096+00:00 подтверждены 542 новости, 1 PDF-отчёт (37 страниц, 5 кандидатов).
Есть ограничения покрытия: GDELT429, недоступные сайты/файловый хост,
общая RSS MOEX частична из-за предела500 элементов. Не объявлять всё покрытие,
финансовую валидацию кандидатов или многосуточную нагрузочную приёмку завершёнными.
Факты, ссылки и квитанции: [выпуск OSINT](docs/INVESTMENT_OSINT_RELEASE_2026-10-28.md).

---

# Выполнение главного плана Analyst AI

## OWNER 24.10.2026 — прямое создание в Москве или Санкт-Петербурге

Последнее указание владельца: создать необходимый сервер самостоятельно, напрямую, без обращения по почте. Разрешены только Москва или Санкт-Петербург. Это заменяет предыдущий выбор других российских и зарубежных регионов. Вся разработка, сборка APK и проверки выполняются на Timeweb; GitHub используется для резервного копирования и ранее разрешённого транспорта доступа. Сохраняются почасовое списание, минимальная фактически достаточная стоимость, строго портретное приложение, прежняя подпись APK и исправление только выявленных проверками ошибок.

Через API Timeweb создан выделенный сервер 121673, analyst-ai-msk-20261024, Москва / ru-3, preset 6007: Intel Xeon E3-1231v3, 4 физических ядра / 8 потоков, 8 ГБ RAM, 1 ТБ HDD, Ubuntu 24.04, 1 Гбит/с. Базовая цена 5480 ₽ в месячном пересчёте, без платных дополнительных услуг. Это минимальная по цене физическая конфигурация Москвы/Петербурга в проверенном каталоге. Нужны прямой доступ к процессору и фактическая проверка KVM для обязательной Android-матрицы; доступность тарифа не доказывает успешное выполнение этих проверок.

Заказ подтверждён API: состояние installing, IP пока не выдан, autoinstall_ready=0 — сервер подготавливает провайдер. SSH, фактическая память, диск, KVM_CREATE_VM и графика нового сервера ещё не проверены. Старый сервер 9408159 и ключ подписи сохранены до проверенного переноса. Новый APK, зелёная ветка и рабочий backend этим заказом не подтверждаются.


## OWNER 24.10.2026 — только Россия, минимальная конфигурация

Владелец уточнил: «Создай конфигурацию на российском сервере! Выбери самый дешёвый, но необходимый нам! Без запаса!»
Выбирать только российскую локацию Timeweb, минимальную фактически достаточную конфигурацию и почасовое списание. Разработка, сборка и проверки выполняются на Timeweb; GitHub служит резервной копией и уже разрешённым транспортом доступа. Это заменяет прежнее разрешение выбирать любую страну. Новые функции не добавлять. Сохранять подпись APK, портретную ориентацию, существующие данные и полные проверки приложения. Наличие тарифа не доказывает возможность заказа, доступный KVM или успешную проверку APK.


## OWNER 24.10.2026 — почасовая оплата Timeweb

OWNER требует почасовую оплату и продолжение текущей работы.
Использовать почасовую тарификацию облачных ресурсов. Не оформлять месячный
или годовой пакет оплаты и не подключать автопополнение ради этой задачи.
Проверять реальную доступность и достаточность более дешёвых конфигураций.
Ненужные временные серверы и их платные адреса удалять после проверки.
Разрешённый канал команд GitHub Actions и разработка только на Timeweb,
вертикальный дизайн и все обязательные проверки остаются в силе.

## OWNER 23.10.2026 — Timeweb и постоянное разрешение

Разработка, редактирование приложения, сборка APK и все проверки выполняются
на Timeweb. GitHub хранит резервные копии исходников; OWNER отдельно разрешил
GitHub Actions как канал SSH-команд к Timeweb. Повторно спрашивать разрешение
на этот канал, необходимые исправления, проверки и развёртывание в согласованной
задаче не нужно. Разрешение не заменяет фактическую проверку результата.
Подбирать минимально достаточные по цене серверы: Россия в приоритете,
затем ближайшие страны. Ресурсы для этой задачи разрешены; не создавать
ненужные экземпляры. Приложение и телефонный дизайн строго вертикальные.
Исправлять только подтверждённые ошибки существующего приложения; сохранить
все проверки и единый итоговый коммит исправлений. Секреты не публиковать.

## Проверка доступа и переноса сборки на Timeweb — 23.10.2026

SSH к серверу 9408159 подтверждён через разрешённый канал GitHub Actions.
Разрешение OWNER сохранено в AGENTS.md, MASTER_PLAN.md и PLAN_STATUS.md.
Исходники разработки: 79be182168e21ae8248e0e0dfa6deb0abfbacbcf,
рабочий каталог /root/analyst-ai-development-79be1821.

Сервер имеет около 1 ГБ RAM, без Android SDK и /dev/kvm.
Более дешёвые российские предложения 6751, 6761, 6753, 6763 и 2581
отклонены провайдером по отсутствию ресурсов; 2455 возвращает preset_not_found.
Пробный сервер 9409007 (ru-2 / nsk-1, preset 4245, 4 CPU / 8 ГБ / 80 ГБ,
6800 руб./месяц без IPv4) остался no_paid и не стал доступен по SSH.
Аккаунт не заблокирован, баланс положительный, но не покрывает 7000 руб.
на 30 дней сервера с IPv4. Точную платёжную информацию в журналы не выводили.
Документация провайдера требует запас средств на 30 дней создаваемых серверов.
https://timeweb.cloud/docs/cloud-servers/manage-servers/create-server

9409007 и его адрес d378efc5-0d10-4ef6-9eab-133f43b48f6f удалены;
инвентарь подтвердил отсутствие обоих ресурсов и работающий 9408159.
Проверка: https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40006850088
Проверка требования оплаты: https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40006543477

Полный Android runtime API 37 / 16 КБ и 4 КБ на Timeweb ещё не пройден.
Поддержка KVM у незапустившегося сервера не проверена. Подпись APK сохранять;
существующий закрытый ключ ещё не переносился. Нового APK не опубликовано.
Backend ещё не запущен; реальная привязка владельца Telegram не выполнена.
Не считать ветку зелёной и не ослаблять проверки из-за инфраструктурного блока.

## Единый набор исправлений существующего кода — 23.10.2026

F01/F16/F22/F23. OWNER уточнил: исправлять существующее приложение без новых
функций; собрать исправления в один итоговый коммит. Сохраняется работа до
`5c941106ba4d1f2731f0993bca8d73bd8e79b828`, включая исправление окна риска.
Промежуточные изменения этой задачи объединяются; это не merge в main и не
производственный выпуск. Версия 0.11.0-preview /35, Android17/API37, package,
подпись, реальная 3D-сцена и нативные редакторы остаются прежними.

Уточнение OWNER в ходе этой задачи: только вертикальный дизайн, без перехода
телефонного приложения в landscape; разработка и проверки также на Timeweb.
`BootstrapActivity`, `MainActivity`, `ProfileUiProbeActivity` теперь portrait.
APK verifier проверяет ориентацию обоих production-компонентов внутри собранного
manifest, а runtime требует portrait при принятом Android запросе user_rotation=1.
Сохранены проверки текста/курсора/видимости IME, сеанса, состояния 3D, цели и
предпросмотра; один лишь неизменённый размер без этих данных не даёт PASS.
Снимки не поворачиваются и не масштабируются. Регрессии отклоняют landscape,
чужой/изменённый текст, неверный курсор, открытие скрытой IME и потерю состояния
во время capture. Старые результаты landscape ниже являются историческими.
Ограничение API37 для больших экранов описано в
[официальной документации](https://developer.android.com/about/versions/17/changes/ff-restrictions-ignored).
Оба полных Android-профиля окончательного SHA ещё обязательны.

Исправления существующего поведения:

- VolumeWorkspaceClient проверяет декодированный URI path отдельно от query.
  Поиск `..`/`A..B` больше не падает до сети; `%2e%2e`, чужие пути, fragments
  и неподдерживаемые методы по-прежнему отклоняются. Девять Kotlin/JUnit
  проверок транспорта и BackendConfig прошли; исходный код проваливал три.
- Компактная шапка учитывает доступную высоту и fontScale. Без IME composer
  ограничен половиной области, история сохраняет место. Ввод имеет собственную
  ограниченную прокрутку; тестовый драйвер адресует именно её. Расчёты,
  нативный фокус и содержимое запроса не меняются.
- Новая ошибка отправки/оценки стоимости раскрывает её карточку после длинного
  развёрнутого ответа. Восстановление вопроса сначала раскрывает достаточную
  геометрию редактора, затем требует очищенного и снова доступного поля.
  Один POST/GET, request UUID, сохранённое сообщение и запрет повторной
  отправки без восстановления проверяются прежними строгими условиями.
- После подтверждения задания сервером и успешной записи checkpoint интерфейс
  снимает ошибку исходной отправки только при совпадении request_id. Ошибка,
  её неоднозначность и необходимость восстановления хранятся вместе. Другой
  идентификатор, неподтверждённая ошибка или активная операция не дают её скрыть;
  подтверждение восстановления не отправляет новый запрос. Семь целевых
  Kotlin/JVM tests (четыре recovery и три существующих editor tests) PASS.
  Мутации, сохраняющие старую ошибку, снимающие чужую ошибку или игнорирующие
  live busy, обнаружены тестами. Локальная проверка исполняет реальные типы
  состояний и action wrapper; Compose/Android integration остаётся за CI.
- Поиск сохранённого вопроса использует существующий предел 20 семантических
  страниц вместо 10 при прежнем общем deadline 12s. В runtime область истории
  при font200 составляет 199px: после десяти прокруток кадр ещё показывает
  длинный ответ. Модель с логическими координатами текста и двух размеров
  viewport воспроизводит отказ старого предела и раскрытие целого сохранённого
  сообщения новым поиском. Отсутствующее, чужое, неоднозначное или обрезанное
  сообщение по-прежнему не принимается; GET/POST и cleared editor обязательны.
- Перед вводом названия цели probe ждёт новое активное окно и его собственный
  видимый список с заголовком. Устранена гонка между кадром прежней страницы и
  свежим корнем диалога. Три регрессии исполняют реальный обработчик входа;
  удаление ожидания воспроизводит зафиксированный отказ драйвера. Модельные
  тесты не объявляются доказательством Android runtime.
- В plans/partial обнаружение подписи операции больше не разрешает прямой tap
  по потенциально обрезанным или ещё движущимся координатам. Probe раскрывает
  тот же нативный переключатель, ждёт три устойчивых кадра существующим helper,
  делает один tap и требует checked=true перед подтверждением. Количество
  2→5, привязка операции и неполнота источника проверяются прежними условиями.
  Четыре регрессии исполняют настоящий обработчик и ProfileProbe: восемь
  вариантов движущейся/обрезанной геометрии, font100/200 и raw/qualified tags;
  исходный обработчик воспроизводит отказ. Неоднозначная, уже выбранная или
  не отвечающая на tap операция не допускает подтверждения или второго toggle.
- Синтетические DashboardApiTests больше не создают настоящий HTTP transport
  из переменных прокси хоста. Сохраняются те же ответы/проверки API и строгий
  отказ при неожиданном обращении к брокеру. Это устраняет пять локальных
  ImportError из-за необязательного SOCKS транспорта, не меняя production HTTP.
- В assistant/job/font200 отдельный поиск заголовка сохранённых заданий также
  исчерпывал 10 страниц в области истории 237px. Только этому поиску передаётся
  существующий максимум 20 страниц, при прежнем общем deadline12s. Остальные
  нажатия сохраняют максимум10; native owner, устойчивость геометрии и enabled
  обязательны. Четыре новые регрессии исполняют настоящий обработчик и tap:
  font100/200, raw/qualified tags, отсутствие и disabled карточки. Старый tap
  воспроизводит отказ короткого viewport; новый делает ровно одно нажатие.

- В `1a1e5068` поиск точного текста потери ответа в assistant/ready/font200
  также исчерпал10 страниц истории199px. Для этого поиска установлен предел20
  с прежним deadline12s. Три новые регрессии исполняют настоящий reveal перед
  восстановлением: обе высоты истории, отсутствие/чужой package ошибки;
  старый предел воспроизводит отказ. Без ошибки нет GET или повторного POST.

- Runtime `644dbf736` подтвердил исправления ассистента/font200 и остановился
  в strategy/ready/font200: после подтверждения версии4 compact-режим
  полностью убирал SpectrumTabs даже без IME. LiveStrategyScreen сохраняет
  вкладки при скрытой клавиатуре; временное освобождение места во время ввода
  осталось. Встроенный runtime уже проверяет выбор «Версии» и возврат2→5;
  эти проверки и ограничения не изменены. Это исправление UI, не новая функция.

- Runtime `faa142020` подтвердил все сценарии стратегии/font200 и обнаружил
  недостаточный обход analysis/empty/font200: после10 семантических страниц
  viewport `[0,357][320,616]` ещё показывал MonitorCheckCard перед историей.
  Только поиск «Сохранённых проверок пока нет.» получает существующий предел20
  при прежнем deadline12s. Четыре регрессии исполняют реальный ProfileProbe и
  весь empty-сценарий: оба размера viewport, отсутствие/чужой package текста,
  enabled платная кнопка. Старый предел воспроизводит отказ; критерии успешной
  проверки не ослаблены. Код приложения этим исправлением не меняется.

- Runtime `ec69c587` подтвердил analysis/empty/font200 и остановился в
  analysis/partial/font200 на точной причине cooldown. После10 страниц кадр
  ещё показывает раскрытый утренний результат, перед вечерним и последней
  проверкой условий. Для этого поиска установлен прежний ограниченный
  максимум20 при deadline12s. Ещё четыре регрессии исполняют весь partial:
  короткий/обычный viewport, отсутствующая/чужая причина и enabled платная
  кнопка; старый предел воспроизводит отказ. Код Android/backend не меняется.

Последняя локальная проверка изменённых CI scripts: **960 tests PASS**,
4 предусмотренных environment skips,1.253s; syntax334/failures0. Из них девять проверок анализа
выполнены без skips. Остальные результаты ниже относятся к ранее проверенным
неизменённым компонентам; окончательный SHA проверяется CI заново.

Проверен охват запуска/обновления, сессий, сетевого клиента, хранения состояния,
редакторов, переходов окон, backend и инфраструктуры CI. Локально: 946 CI tests
(2 предусмотренных environment skips с доступным JDK compiler), 61 Node tests, 52 tool tests,
15 mesh tests и 11 native-alignment tests — PASS; bash syntax четырёх скриптов
PASS. Python syntax audit: 334 source files, failures0. Полный backend suite:
1505 tests/1409subtests PASS, 23.25s; startup/health/OpenAPI PASS. Окружение
соответствует requirements; pip check PASS. Один DeprecationWarning исходит
из установленного Starlette/AnyIO, не скрыт и не является отказом теста.
Sonar и Android compile/JVM/lint должны повторно пройти на окончательном SHA.

Доказательства прежних кандидатов, не результат финального SHA:

- `ec69c587`: Backend39985985522 —1505/1409subtests PASS; Sonar39985976949
  —0/0/all_types:true/complete:true. Android39985985523 build120525287606
  —все варианты/JVM/lint,950 CI tests PASS,9m17s. Runtime120530545982 подтвердил
  API37/PAGE_SIZE16384, install/upgrade/launch, spatial/session/privacy/goals,
  все30 business/font100 и24 business/font200. Analysis/empty/font200 PASS
  в16:52:31UTC. Следующий partial: `List target not reachable: Причина: С
  прошлого анализа прошло недостаточно времени`, swipes10, viewport259px.
  Preview SHA256 `9f6c1afa5add2c904b47a6aaca7cef76dd4416bc44888786ee43dbafa12a0d96`.
  Failure PNG SHA256 `47b9f9454ed6536d28b23aed70046b2a7ab735e1e31e63f234d8fc914848f933`.
  Профиль4096 не запускался; APK не опубликован.
- `faa142020`: Backend39980635623 —1505/1409subtests PASS; Sonar39980628419
  —0/0/all_types:true/complete:true. Android39980635604 build120506799660
  —все варианты/JVM/lint,946 CI tests PASS,9m38s. Runtime120512505678 подтвердил
  API37/PAGE_SIZE16384, install/upgrade/launch, spatial/session/privacy/goals,
  все30 business/font100 и23 business/font200. Strategy/ready/font200 PASS
  в16:12:23UTC; все четыре сценария стратегии прошли. Analysis/empty/font200:
  `List target not reachable: Сохранённых проверок пока нет.`, swipes10;
  кадр показывает предшествующий текст, список продолжает прокручиваться.
  Preview SHA256 `fa5f07c1a4c2c6e787b4b5219a5d3f32448dc3bc51d82d45026ee3318e631296`.
  Failure PNG SHA256 `a76c4fae3cd802ddf812902925e1d26d146e53514aa16b50c21b568905644233`.
  Профиль4096 не запускался; APK не опубликован.
- `644dbf736`: Backend39975624069 —1505/1409subtests PASS; Sonar39975613714
  —0/0/all_types:true/complete:true. Android39975624067 build120489403982
  —все варианты/JVM/lint,946 CI tests PASS. Runtime120494602197 подтвердил
  API37/PAGE_SIZE16384, install/upgrade/launch, spatial/session/privacy/goals,
  все30 business/font100 и14 business/font200 (risk4,assistant5,plans5).
  Strategy/ready/font200: `Scroll layout not ready: profile-tabs`;
  на кадре версия4 и закрытая IME, вкладок нет. Причина — compact-условие в UI.
  Preview SHA256 `e38c2843e346160a627e49116e70170c97bf2da90735427d9a2f8f8264541d2f`.
  Failure PNG SHA256 `f368e8da3f55cf4eb897e51a0894e59be1ac50da4c00a4e348c67b2b35a219b2`.
  Профиль4096 не запускался; APK не опубликован.
- `1a1e5068`: Backend39970599098 —1505/1409subtests PASS; Sonar39970585851
  —0/0/unique0/all_types:true/complete:true. Android39970598792 build120472050473
  —все варианты/JVM/lint,943 CI tests PASS. Runtime120477433428 подтвердил
  API37/PAGE_SIZE16384, install/upgrade/launch, spatial/session/privacy/goals,
  все30 business/font100 и4risk/font200. Assistant/ready/font200 остановился
  на точном тексте потери ответа после10 страниц в истории199px.
  Failure PNG SHA256 `0843a6bf513e6ff919a2f100fe72047ace67111c40bfac9929e56b2e058422f3`.
  Preview SHA256 `873dd84426ece05a57a718e02098f53fd09c8ecdb7e152b19cdbbf48e68e9c7b`.
  Профиль4096 не запускался; cleanup120486163714 PASS. APK не опубликован.
- `9b7f310d`: Backend39964464224 —1505/1409subtests PASS; Sonar39964455783
  —0 общих/0 новых/unique0/all_types:true/complete:true; Android39964464136
  build120450685199 —все варианты/JVM/lint PASS. Runtime120455766022 подтвердил
  API37/PAGE_SIZE16384, установку/обновление/запуск, spatial/session/privacy/goals,
  все30 business/font100 (включая исправленный plans/partial), risk/font200 и
  assistant ready/empty/partial/error при font200. Отказ assistant/job/font200:
  `List target not reachable: Сохранённые задания · 1`, swipes10, viewport237px.
  Preview SHA256 `1a384051184960d96273213d4e4d4f0846b7d0b51f5a95028d773c9cf93c25d0`.
  Профиль4096 не запускался; cleanup120464964804 PASS. APK не опубликован.
- `3bbca44a`: Backend39959715887 — 1505/1409subtests PASS; Sonar39959704389
  — 0 общих/0 новых/unique0/all_types:true/complete:true. Android39959715888
  build120434956872 — все варианты/JVM/lint PASS за9m39s, 197 tasks,
  935 CI tests PASS с3 environment skips. Runtime120439958732 подтвердил
  API37/PAGE_SIZE16384, install/upgrade/launch, spatial/session/privacy/goals
  и первые11 business/font100, включая все5 assistant cases. Plans/partial
  остановился на disabled подтверждении после прямого tap по обнаруженному
  переключателю. На кадре операция остаётся невыбранной, счётчик запросов2,
  contract-errors0: подтверждение не отправлено. Failure PNG SHA-256
  `39072cdb8e23521cfdda3eca5f1c7596e22b463632307b38da7175ea79460ae4`.
  Preview SHA-256 `4a9bdfedc0f32199eb07172aa3709c3b4c0d9a35185d82f2c05c393c28c3315a`.
  Профиль4096 не запускался; cleanup120445440697 PASS, APK не опубликован.
  Серверная интеграцияb59de152 прошла Backend1553/1481subtests, Sonar0/0
  и owner inventory; обе её родительские истории сохранены.
- `c00293b7`: Backend39953432154 — 1505/1409subtests PASS;
  Sonar39953425475 — 0 общих/0 новых/unique0/all_types:true/complete:true.
  Android39953432312/job120413835739 потерял связь с self-hosted Windows runner
  во время lintAnalyzePreview. GitHub сообщил `The self-hosted runner lost
  communication with the server`, а не ошибку компиляции. Cleanup120419823088
  PASS; повтор только упавшей build job120420926185 остался в очереди, новый
  preflight120420982079 PASS. Все четыре зарегистрированных Windows runners
  наблюдались Offline. APK, JVM/lint и runtime этого SHA не подтверждены;
  серверная интеграция577559cd прошла Backend1553/1481subtests и полный Sonar0/0.
- `acdd625b`: Backend39946490423 — 1505/1409subtests PASS; Sonar39946484143
  — 0 общих/0 новых/unique0/all_types:true/complete:true; Android build120390411962
  — варианты/JVM/lint и934 CI tests PASS. Runtime39946490484/job120394518641
  подтвердил API37/PAGE_SIZE16384, install/upgrade/launch, spatial/session/privacy,
  goal/font100/font200, все30 business/font100 и4 risk/font200. Assistant/font200
  прошёл нативный ввод/поворот, показ ошибки, один POST и один GET того же UUID,
  очищенный доступный редактор; поиск сохранённого сообщения исчерпал10 страниц.
  Failure PNG SHA-256 `2cd191f40100227fc2fb0cd4a75b89b035410e705ff4ccce9c45fe6f66d9d48f`.
  Это пока не полный runtime PASS; профиль4096 ещё не достигнут. Приватная
  временная передача удалена job120403673803, APK не опубликован.
- `f9b69a3`: Backend/Sonar0/Android build PASS; runtime39932211503 подтвердил
  все 30 business cases/font100 и четыре risk/font200, затем обнаружил
  нулевую высоту истории assistant/font200. Это основание исправления layout.
- `19e64aff`: Backend1505/1409subtests, Sonar0/0 и build PASS;
  runtime39939913031/job120373059879 подтвердил API37/PAGE_SIZE16384,
  install/upgrade/launch, spatial/session/privacy/goals, risk/font100 и
  нативный ввод/поворот ассистента. Ошибка отправки осталась ниже длинной истории
  после 10 разрешённых прокруток; failure PNG SHA-256
  `6a9c860e9b96cee3e3b2931c871b2380d1d964bfdbef1d0f120041ce1528666a`.
- `f69676a9`: Backend39943216976 — 1505/1409subtests PASS;
  Sonar39943208557 — 0 общих/0 новых/unique0/all_types:true/complete:true;
  build120379541311 — все варианты/JVM/lint и931 CI tests PASS.
  [Runtime39943216874](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39943216874)
  подтвердил API37/PAGE_SIZE16384, install/upgrade/launch, spatial/session/privacy
  и goal/font100. Goal/font200 остановлен до ввода: драйвер получил новый корень
  без списка после выбора списка прежнего окна (`Expected one exact visible
  app list`). Скриншот показывает открывающуюся форму «Новая цель», SHA-256
  `4ba6c56664b0f90cd17fb5087870b7559c48141aacdc7a68cf38ed37158a11c0`.
  Это отказ перехода тестового окна, не подтверждённое падение приложения.
  Исправление отображения ошибки чата этим запуском ещё не проверено.

Обязательны обе полные runtime-матрицы API37/16384 и4096 при font100/font200
именно финального APK. Зелёный build не заменяет runtime. Main не изменён;
новый APK не опубликован, телефон и живой backend не объявляются проверенными.

## Ожидание окна сравнения риска при font200 — 23.10.2026

Область F01/F22/F23, продолжение PR #880 от
`0bd11737cb6219f49be50caeb771e20c401c7bf2`. Версия остаётся
0.11.0-preview / 35, Android 17 / API37. Существующие исправления каталога,
портфеля, валют, черновиков, native IME и preflight повторной сборки сохранены.

### Подтверждённый результат основы

- [Backend 39927331812](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39927331812)
  — **1505 tests / 1409 subtests PASS**, 20.62s; аудит 330 Python-файлов
  без ошибок и strict Sonar PASS. [Полный Sonar 39927324925](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39927324925)
  — **0 OPEN/CONFIRMED всех типов / 0 новых / unique:0**, all_types:true,
  complete:true, exact-head check `120327828515`.
- [Android 39927331871](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39927331871)
  — build `120327377022` PASS: **922 CI tests**, 3 предусмотренных skips,
  Gradle всех вариантов/JVM/lint за 9m22s, 197 выполненных задач.
  CI checkout `f9556649b65eaa0ae7314c670a65befd8f3fd672` имеет точное
  дерево опубликованного кандидата `f739902da1e5366f5ee4c3414b6ee988510834c3`.
- Runtime `120331544496` подтвердил фактический `getconf PAGE_SIZE=16384`
  на API37 x86_64, clean install, upgrade с 0.10.0/34 и оба запуска preview.
  **Все 30 business cases font100 PASS**, включая catalogue ready, empty,
  partial и error. Это подтверждает исправленный переход каталога при font100.
- Следующий `risk/ready;font=2.0` начат в 09:15:56 UTC и остановился
  перед первой проверкой пустых предположений в scenario dialog:
  `risk_scenario_probe.py::exercise_scenario_comparison` вызвал
  `probe.reveal(COMPARE, AREA)` сразу после tap «Рассчитать свой сценарий».
  Последний tap в 09:16:13.919 ещё относится к window156. В 09:16:14.602
  native driver сообщил `frame_error=IOException: Expected one exact visible app list`.
  Python `ConnectionError: UiAutomation session ended before a complete frame`
  последовал после закрытия драйвером соединения; ADB оставался подключён.
  Успешный font200 comparison или rotation этим запуском не установлен.
- Failure screenshot уже показывает отдельный dialog «Сравнение ваших
  сценариев» с длинным вводным текстом при font200. PNG blob
  `42df389817dcbcd592ef1ed475488be76df81861`, preview blob
  `c51dc5afb4bb0ad5964cfa8e0bae41b237821967`. Число совпадений native списка
  не выводилось, поэтому ноль против нескольких не объявляется измеренным.
- Полная font200 business-матрица и portfolio не достигнуты; 4096 skipped.
  Cleanup `120338240224` PASS, `verified_absent` в 09:17:35.966 UTC.
  Приватный APK не сохранён. Preview SHA256
  `ec5b5dfbc6fabcb2e046d758fc5ed07e39dc46253abbc92900a249d5c1012cc5`,
  29,853,394 bytes; APK report сохраняет `device_install_test=separate_required_check`.
- Серверный `907399f562214a75366323ebdf83dac42cf28831` отдельно прошёл
  [Backend 39927982498](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39927982498)
  — **1553 tests / 1481 subtests**, 26.14s, audit336 без ошибок, и
  [полный Sonar 39927978072](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39927978072)
  — **0/0, all_types:true, complete:true**, check `120329518818`.

### Причина и граница исправления

`RiskWorkspaceScreen` открывает отдельный `RiskScenarioDialog`;
`WorkspaceDialog` размещает заголовок первым Text внутри собственного
`workspace-content`. Старый экран и новый dialog используют одинаковый tag,
поэтому одного поиска tag после tap недостаточно для подтверждения перехода.
Код, timing и screenshot согласуются с гонкой между старым кадром probe и
новым root, который строгий native driver читает непосредственно при scroll.

Probe запоминает native window перед открытием и переиспользует
`wait_for_new_app_window` по заголовку «Сравнение ваших сценариев».
Ожидание требует нового валидного window ID, ровно одной видимой enabled
области приложения с точным tag и заголовка внутри этой области. Только
после этого прежний ограниченный reveal ищет кнопку «Сравнить сценарии».
Ожидание не требует видимости нижней кнопки или признака scrollable.
Driver, протокол, timeout/scroll limits, валидация пустого ввода, точные
денежные результаты и rotation assertions не меняются.

### Проверка нового кандидата

Полный локальный CI-набор: **927 tests PASS**, 4 предусмотренных skips,
0.939s. Compile audit всех **331 tracked Python-файлов PASS**, failures:[].
Целевые risk tests — **10/10 PASS**, включая 5 новых методов; независимый
review APPROVE. Working/staged diff check PASS.

Регрессия выполняет настоящий handler до первого нативного ввода через
empty-input guard и прежние bounded reveals. Моделируются задержанный кадр
старого окна, появление нового root до списка и списка до заголовка,
масштабы 1/2 и оба вида resource ID. Исходный HEAD handler воспроизводит
отказ на всех четырёх конфигурациях; новый доходит до первого редактора
без прокрутки чужого окна. Независимый no-op mutant ожидания также
воспроизводит отказ 4/4. Negative guards отвергают прежнее/невалидное окно,
заголовок вне списка и ошибочно разрешённую кнопку при пустом вводе.
Эта модель не выполняет native text entry/rotation и не заменяет Android.

Kotlin, backend, SDK и signing остаются неизменными относительно основы;
повтор неизменённых локальных backend/JVM suites не требовался. Собственные
удалённые gates нового SHA остаются обязательными.

Новому SHA обязательны собственные полный Sonar, Gradle/JVM/lint и обе полные
API37-матрицы с фактическими 16384/4096. `[private-apk]` сохраняет приватный
draft только после всех gates. Физический телефон, live Timeweb, Telegram
owner binding и серверный канал обновления остаются отдельными этапами.

## Подготовленная синхронизация server с app 0bd11737 — 23.10.2026

Область F23. Родители подготовленного объединения:
server `70aea700625c7b2cf8861dbd86f01acf2f0f311d` и
app `0bd11737cb6219f49be50caeb771e20c401c7bf2`
(tree app `f739902da1e5366f5ee4c3414b6ee988510834c3`).

Перенесены три недокументационных пути: Android workflow и его JS/Python
регрессии. Успешный preflight выдаёт prepared_attempt; build при несовпадении
с текущим run_attempt повторяет полный prepare перед SDK, а при ошибке
сразу запускает cleanup до прочих always-шагов. Существующие ownership,
anonymous-denial, read-back, digest и upload/download guards сохраняются.
Production transfer module, Kotlin, native driver и backend не изменены.
README и этот реестр сохраняют все строки обоих родителей в исходном
порядке; конфликты были только между добавляемыми в начало разделами.

### Локальная проверка объединённого дерева

- Полный CI/release-набор: **949 tests за 1.032s, OK, skipped=4**.
  Два пропуска требуют Android SDK, два — полного JDK для host-регрессий.
- Аудит всех **336 отслеживаемых Python-файлов**: **0 failures**,
  compile-without-execution; проверен индекс с разрешёнными конфликтами.
- Все **777 общих app-путей**, кроме двух документов и server-specific
  набора, совпадают с `0bd11737` по набору путей и Git blob/mode.
- Все **13 server-specific путей** точно сохранены из `70aea700`, включая
  Telegram OIDC/owner enrollment, установщик и read-only inventory.
- Все **340 путей `app/` и `ci-ui-driver/`** и **162 пути `backend/`**
  неизменны относительно `70aea700`; production `ci_private_transfer.cjs`
  также совпадает с обоими родителями. Backend/JVM suites повторно не запускались.
- Working/staged diff check — PASS; неразрешённых конфликтов индекса
  и незастейдженных изменений нет. Независимое read-only review
  трёх перенесённых путей и сохранённых server/source границ — APPROVE.

### Доказательства родителей и границы приёмки

Server `70aea700` прошёл собственный [Backend CI 39925790746](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39925790746),
job `120321704044`: **1553 tests / 1481 subtests**, 28.69s, audit336,
health/OpenAPI и strict Sonar PASS. Его [полный Sonar 39925784357](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39925784357),
job `120321681542`, check `120322227864`, подтвердил **0 OPEN/CONFIRMED
всех типов, 0 новых, unique:0, all_types:true, complete:true**.
CI merge `992a9b01ba608f80ddc779e8af7f61fce6243518` имеет то же дерево
`1774eb694c56d9a53cfbd198c013048b3fd259bf`, что этот server-родитель.

App `0bd11737` прошёл собственный [Backend CI 39927331812](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39927331812),
job `120326843926`: **1505 tests / 1409 subtests PASS**, 20.62s,
audit330 и strict Sonar PASS. [Полный Sonar 39927324925](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39927324925),
job `120326819752`, check `120327828515`: **0 OPEN/CONFIRMED всех типов,
0 новых, unique:0, all_types:true, complete:true**.
В [Android CI 39927331871](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39927331871)
preflight `120327281541` PASS; build `120327377022` прошёл SDK в
08:50:42 UTC и выполняет Gradle. Runtime нового SHA ещё не подтверждён.

App-родитель `25e73835` отдельно прошёл Backend **1505/1409** и полный
Sonar **0/0**; ссылки сохранены в app-разделе ниже. Его Android attempt1
остановился на SDK timeout 600s до Gradle/runtime. Attempt2 прошёл SDK
и APK rule tests и дошёл до Gradle. После нового head она отменена
в 08:49:42 UTC во время Gradle, без BUILD SUCCESSFUL, upload или runtime.
[Cleanup job 120327130953](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39925032873/job/120327130953)
подтвердил verified_absent в 08:49:49.116 UTC. В переиспользовании preflight
была выявлена несовместимость с текущей transfer identity; это отдельный
orchestration-дефект, а не наблюдавшийся runtime FAIL попытки2.

Новый server SHA требует собственных Backend CI и полного Sonar.
Приёмка app `0bd11737` включает собственные Gradle/JVM/lint и обе полные
API37-матрицы с фактическими PAGE_SIZE 16384/4096 и font100/200.
Локальные regression tests не подтверждают новый APK, физический телефон,
live Timeweb, DNS/TLS, реальный Telegram owner binding или доставку
проверенных APK-байтов в канал обновления.

## Сохранённые записи app/server

## Preflight текущей попытки повторной сборки — 23.10.2026

Область F23; родитель app `25e73835dfee05b7c22645ddf8e541dcf3e7caf7`,
tree `cf09a5f7c622a8539fd0e92e2e3a878497d245a9`. Исправления ожидания окна,
направления issuer lookup и весь Kotlin/backend остаются прежними.

### Доказательства и причина

- [Backend39925032850](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39925032850)
  родителя PASS: 1505 tests / 1409 subtests, 24.86s; audit330.
  [Полный Sonar39925027214](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39925027214)
  PASS: check120320038927, 0/0/unique0, all_types:true, complete:true.
  CI merge `36c78c041148e90d62f07bc44b4428ee4e361b19` имеет то же дерево.
- [Android39925032873 attempt1](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39925032873/attempts/1),
  build120319322820: первый пакет `platforms/android-37.0` получил
  `subprocess.TimeoutExpired` после 600s. CLI не вывел отдельной причины;
  сеть, lock и конкретная причина ожидания не установлены. Gradle/runtime
  не начались. Cleanup120323461186 подтвердил `verified_absent` в08:40:37UTC.
- Одна повторная попытка2 на том же SHA прошла SDK и APK rule tests
  (08:41:45/08:41:57UTC) и дошла до Gradle. Новый build120323801609
  начал работу в08:41:21, а успешный preflight120323843846 сохранил время
  исходного выполнения 08:29:47–08:30:03. Его результат был переиспользован.
- Transfer identity включает GITHUB_RUN_ATTEMPT. Старый draft уже удалён,
  нового `ci-transfer-39925032873-2` нет в полном списке releases (29 записей).
  Поэтому upload этой попытки не получает обязательный пустой draft.
  Это подтверждённая несовместимость orchestration с текущими guards;
  не наблюдавшийся native UI FAIL и не повод ослаблять uploader.

### Исправление и граница повторов

Preflight выдаёт prepared_attempt только после успешного полного prepare.
Build сохраняет зависимость от preflight и перед SDK сравнивает этот output
с текущим github.run_attempt. При несовпадении выполняется тот же prepare
для новой попытки; при совпадении повторного создания draft нет.
При ошибке повторного prepare сразу выполняется cleanup, до остальных
always-шагов; завершающая очистка workflow остаётся обязательной.
Ownership, anonymous-denial, read-back, digest, upload и download проверки
не меняются. SDK-платформа, timeout и signing также не меняются.

Это поддерживает повтор **build job**. Для повторного runtime после успешной
сборки и cleanup нужны новые входные APK: следует повторить build job с его
зависимыми задачами либо весь workflow. Повтор job вместе с зависимыми
задачами предусмотрен [GitHub REST API](https://docs.github.com/en/rest/actions/workflow-runs#re-run-a-job-from-a-workflow-run).
Один runtime не может использовать
удалённую передачу прежней попытки; соответствующий отказ сохраняется.

### Проверка нового дерева

Полный локальный CI-набор: **922 tests PASS**, 4 предусмотренных skips,
0.951s. Transfer Node suite: **10/10 PASS**; workflow contract: **13/13 PASS**.
Добавлены одна JS-регрессия полного lifecycle prepare1 → cleanup → отказ
upload2 → prepare2 → upload2 и три Python-проверки output/condition/order.
Исходный workflow не проходит все три новых contract-проверки.
Production transfer module не менялся; его прежние guards сохраняются.
Аудит всех **330 Python-файлов PASS**, failures:[]; working/staged diff check PASS.
Собственные Backend/Sonar, Gradle/JVM/lint и обе полные API37-матрицы
16384/4096 нового SHA обязательны.
Физический телефон, Timeweb, Telegram owner binding и APK-канал остаются
отдельными этапами; новый приватный APK пока не подтверждён.

## Подготовленная синхронизация server с app 25e73835 — 23.10.2026

Область F01/F02/F20/F22/F23. Родители подготовленного объединения:
server `469bab1964c1041125e01884a071e6b6df01e82c` и
app `25e73835dfee05b7c22645ddf8e541dcf3e7caf7`.

Перенесены пять Python-путей app: общий барьер нового нативного окна,
его вызовы catalogue/portfolio и две группы полных регрессионных обработчиков.
Поиск эмитента после «Факт → Компания» направлен к началу того же списка.
Наблюдавшийся Android catalogue FAIL и условная геометрическая регрессия
issuer lookup различаются в сохранённой app-записи ниже. Native driver,
Kotlin и backend при этом слиянии не изменены. README и этот реестр
сохраняют все строки обоих родителей в исходном порядке; конфликты
затронули только добавляемые в начало документальные разделы.

### Локальная проверка объединённого дерева

- Полный CI/release-набор: **946 tests за 0.970s, OK, skipped=4**.
  Два пропуска требуют Android SDK, два — полного JDK для host-регрессий;
  они не являются результатами native runtime или криптографической проверки APK.
- Аудит всех **336 отслеживаемых Python-файлов**: **0 failures**,
  compile-without-execution. Новые файлы включены в индекс до аудита.
- Все **777 общих app-путей**, за исключением двух документов и набора
  server-specific, совпадают с `25e73835` по Git blob/mode и набору путей.
- Все **13 server-specific путей** сохранены точно из `469bab19`, включая
  Telegram OIDC/owner enrollment, установщик и read-only inventory.
- Все **340 путей `app/` и `ci-ui-driver/`**, а также **162 пути `backend/`**
  точно совпадают с `469bab19`. Неизменённые локальные backend/JVM suites
  повторно не запускались; предыдущие доказательства относятся к своему SHA.
- `git diff --check`, `git diff --cached --check`, отсутствие конфликтов
  индекса и незастейдженных изменений — PASS.

### Собственные удалённые результаты app 25e73835

- [Backend CI 39925032850](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39925032850),
  job `120319209924`: **1505 tests / 1409 subtests PASS**, 24.86s;
  аудит 330 Python-файлов — PASS.
- [Полный Sonar 39925027214](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39925027214),
  job `120319189504`, check `120320038927`: **0 OPEN/CONFIRMED всех типов,
  0 новых, unique:0, all_types:true, complete:true**.
- На момент подготовки [Android CI 39925032873](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39925032873)
  выполняет SDK37/Gradle в build job `120319322820`; runtime ожидается.
  Результаты нового APK, обеих полных API37-матриц 16384/4096 и font100/200
  этим локальным слиянием не объявляются пройденными.

Новый server SHA требует собственных Backend CI и полного Sonar.
Проверки app/server не заменяют физический телефон, установку нового
Timeweb backend, DNS/TLS, реальный Telegram owner binding и доставку
проверенных APK-байтов в канал обновления.

## Сохранённые записи app/server

## Смена окна перед прокруткой модального содержимого — 23.10.2026

Область F01/F22/F23, продолжение app
`b87f74d0b5a243e37003e8295a880c9181a02705`. Исправления валют, контекста
счёта, процентного черновика и статуса выбранного уведомления сохраняются.

### Проверенные результаты родителя

- [Android CI 39920366222](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39920366222):
  build `120304104185` PASS — 906 CI tests с 3 предусмотренными skips,
  Gradle всех вариантов, JVM и lint, 9m10s. CI checkout
  `5142629e0cf0086814a688b3bc76f87f32398544` имеет то же дерево
  `18d816621b46f5986c0082c7f2a606d46217754b`, что опубликованный app.
- [Backend CI 39920366201](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39920366201)
  — 1505 tests / 1409 subtests PASS, 40.90s; аудит 327 Python-файлов
  и strict Sonar PASS. [Полный Sonar 39920360758](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39920360758)
  — 0 OPEN/CONFIRMED всех типов, 0 новых, unique:0, all_types:true,
  complete:true; exact-head check `120304511811`.
- Runtime `120307938449` прошёл установку, обновление с 0.10.0/34 и запуск
  preview на API37 с измеренными PAGE_SIZE 16384, native 3D, session,
  privacy и goals. **26 business cases font100 PASS**: risk 4, assistant 5,
  plans 5, strategy 4, notifications 4 и analysis 4. Новая проверка
  прочтения именно выбранного события прошла настоящий Android.
- `catalogue/ready/font100` остановился на первом reveal кнопки
  «Проверить ограничения». Instrumentation сообщил
  `frame_error=IOException: Expected one exact visible app list`;
  `ConnectionError: UiAutomation session ended before a complete frame`
  возник после закрытия соединения драйвером. ADB оставался подключён.
  Новый app crash в сохранённых diagnostics не установлен.
- Font200 business/portfolio и весь профиль 4096 не достигнуты.
  Cleanup `120313746549` PASS, `verified_absent` в 08:15:38 UTC.
  Приватный APK не создан. SHA-256 preview:
  `291f065c79d49698331561e4c836370d3c1221875603bf5aff3919ce6707be57`,
  29,853,394 bytes; отчёт сохраняет
  `device_install_test=separate_required_check`.
- Серверное слияние `469bab1964c1041125e01884a071e6b6df01e82c`
  отдельно прошло [Backend CI 39920920957](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39920920957)
  — 1553 tests / 1481 subtests, 23.57s, и
  [полный Sonar 39920913615](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39920913615)
  — 0/0, all_types:true, complete:true, check `120306479548`.

### Причина и граница исправления

`failure.png` показывает полностью открытый purchase dialog с видимой
disabled кнопкой «Проверить ограничения» и кнопкой «Закрыть».
Последний tap относился ещё к каталогу, window144. Сразу за ним обработчик
вызывал reveal: старый кадр мог содержать прокручиваемый список каталога,
а native scroll уже читал новый root диалога, содержимое которого помещается.
Именно свежий native root используется строгим `findList()` драйвера.
Число совпадений не выводилось в журнале, поэтому 0 против нескольких
не объявляется измеренным. Код, timing и кадр согласуются с этой гонкой.

Общий `wait_for_new_app_window` пассивно ожидает отличный от исходного
валидный native window ID, ровно одну видимую enabled область приложения
с точным tag и ожидаемый верхний маркер внутри неё. Признак scrollable
не требуется для готовности: помещающийся диалог сразу отдаёт цель,
а длинный затем использует прежнюю ограниченную semantic scroll.
Те же переходы исследованы в portfolio modal flows; source-паттерн
исправляется там до следующего полного runtime, без объявления их
наблюдавшимися отказами. Native driver, протокол, лимиты и assertions
пустой цены/результата/точной позиции не ослабляются.

Дополнительный issuer lookup в `_exact_holding` идёт вверх после
«Факт → Компания». Оба шага используют один ScrollState; после clamp
новым размером содержимого первый Text эмитента может остаться выше
viewport. Полный обработчик воспроизводит отказ исходного направления
на модельных высотах 453 и 720 и проходит на 1300, где смещение становится 0.
После исправления все три геометрии доходят до точных ACCOUNT_B/SHARE_A
и selected-holding. Эти координаты не являются измерением Android/font200.

### Проверки нового кандидата

Общий локальный CI-набор: **919 tests PASS**, 4 предусмотренных skips,
0.964s. Включены 9 новых catalogue tests и 4 portfolio traversal tests:
задержанный старый кадр при открытии окна, помещающийся и прокручиваемый
dialog, строгие package/window/list guards и полный путь к выбранной
позиции. Проверены research/dossier, actions/risks/back на модельных
масштабах 1/2; это регрессии последовательности, не замена Android runtime.
При отключении только нового ожидания исходная гонка воспроизводится.
Аудит всех **330 tracked Python-файлов PASS**, failures:[]; diff --check PASS.
Backend, Kotlin и native driver не изменены относительно проверенного
родителя; повторять неизменённые локальные backend/JVM suites не требовалось.
Удалённые проверки нового SHA остаются обязательными.

Новому SHA обязательны собственные полный Sonar, Gradle/JVM/lint и обе
полные API37-матрицы с фактическими 16384/4096. `[private-apk]` сохраняет
приватный draft только после всех gates. Физический телефон, live Timeweb,
Telegram owner binding и обновление серверного APK остаются отдельными
этапами; успешные локальные модели или серверный CI их не заменяют.

## Подготовленная синхронизация server с app b87f74d0 — 23.10.2026

Область F01/F02/F07/F11/F16/F20/F22/F23. Родители подготовленного объединения:
server `b5ab3fac5eaba0a39494390c2b1fa5a9720e0549` и
app `b87f74d0b5a243e37003e8295a880c9181a02705`.

Перенесены нормализация брокерского кода валюты, сохранение метаданных
при автономном обновлении и появлении одного инструмента на нескольких счетах;
account-specific количества, суммы и блокировки остаются отдельными.
Также перенесены проверка отсутствующего выбранного счёта чата, сохранение
неверного процентного ввода в debug-стратегии и привязка UI-проверки к статусу
выбранного уведомления. Предыдущие app-исправления IME, инициализации форм,
точности Decimal и владения заданиями сохраняются из актуальной основы.
Server OIDC/owner enrollment, установщик и read-only inventory остаются прежними.
Конфликты возникли только в README и этом реестре; записи обеих веток сохранены.

### Локальная проверка объединённого дерева

- Полный backend: **1553 passed, 1481 subtests passed за 36,79 с**.
  Единственное предупреждение — устаревающий alias AnyIO BlockingPortal
  в установленном Starlette TestClient; ошибок тестов нет.
- Полный Python-набор CI/release: **933 теста за 0,976 с, OK, skipped=4**.
  Четыре предусмотренных пропуска относятся к отсутствию полного JDK/Android SDK;
  это не подтверждение Android runtime, подписи APK или установки.
- Аудит Python без исполнения: **333 файла, 0 ошибок**.
- Равенство Git blob/mode и набора путей: **340 app/driver путей** точно
  совпадают с `b87f74d0`; **13 server-specific путей** сохранены из `b5ab3fac`.
  Все остальные **774 пути**, кроме серверного набора и двух документов,
  точно совпадают с app-родителем.
- `git diff --check`, `git diff --cached --check` и отсутствие неразрешённых
  конфликтов подтверждены. Разрешения документов сохраняют истории обоих родителей.

Локальная проверка объединения не заменяет собственные удалённые Backend CI
и полный Sonar нового server SHA. Android/Compose/Filament, подпись,
установка и обновление, обе полные API37-матрицы с фактическими PAGE_SIZE
16384/4096 и font100/200 проверяются в app PR #880 на точных байтах кандидата.
Приватный APK пока не подтверждён; физический телефон, новая VM, DNS/TLS,
реальный Telegram owner binding и доставка в канал остаются отдельными проверками.

## Сохранённые записи app/server

## Сохранение валют, черновика и статуса выбранного уведомления — 23.10.2026

Область F01/F07/F11/F16/F22/F23, продолжение PR #880 от актуального
`3bd89e55a72ab99069a7f99a61dffcf473e32a2a`. Итог объединяет независимые
исправления с параллельно обновлённой рабочей веткой. Её modal-host IME lease,
native visibility с Compose fallback, инициализация стратегии и плана,
точность Decimal-сценариев, владение заданиями и навигация probe сохранены.

### Подтверждённое состояние основы

- [Android CI 39916113435](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39916113435):
  build job `120290545219` PASS — Gradle всех вариантов, JVM, lint,
  899 CI tests с 3 предусмотренными пропусками, 9m20s.
  Checkout merge `46df5518a46592173bb2d82fda953410db1f35cb` имеет то же
  дерево `86b5c6e41cdcadeba772a3c67fab9abf8cc9f7c8`, что app head.
- [Backend CI 39916113418](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39916113418)
  — 1492 tests / 1409 subtests PASS, 22.94 s, strict Sonar PASS.
  Полный Sonar check `120290341418` подтверждает 0 OPEN/CONFIRMED всех типов,
  0 новых, unique:0, all_types:true, complete:true.
- [Runtime job120293776830](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39916113435/job/120293776830)
  подтвердил API37 с фактическим PAGE_SIZE 16384, install/upgrade/launch,
  spatial/session/privacy/goals и 18 business cases при font100:
  risk 4, assistant 5, plans 5, strategy 4. Предыдущие отказы поворотов IME,
  сохранения плана и поиска элементов в этих случаях пройдены.
- Следующий `notifications/ready/font100` завершился
  `The selected event did not change to read`. На failure.png выбранная
  карточка «Синтетическое изменение лимита» уже содержит «Прочитано»;
  диалог закрыт, requests:4, contract-errors:0. Полного endpoint trace нет,
  назначение запросов устанавливается по fixture и коду.
  Cleanup `120299207400` подтвердил `verified_absent`.
  Полная font200 business/portfolio-матрица и профиль 4096 не завершены.
- SHA-256 preview исходного кандидата:
  `e080e3115ef6d98f9eeb0ba88aeeff2530ea56d0c2d70104f823dbb0ef453d06`.
  Новый приватный APK этим запуском не подтверждён.
- Серверная ветка на момент сверки — `b5ab3fac`, родители server `7bd2b732`
  и app `3bd89e55`. Все 336 app/driver путей совпадают с app;
  все 13 серверных путей сохранены относительно `eb86ae68`.

### Подтверждённые исправления данных и ввода

1. `_position_metadata` нормализует брокерские ASCII-коды валют в верхний
   регистр на входе: `usd`, `UsD`, `USD` обозначают одну валюту инструмента.
   Строгая внутренняя проверка остаётся; отсутствующие, неверные и похожие
   Unicode-коды не превращаются в подтверждённые валюты.
2. `_monitor_accounts` сохраняет известную валюту в новом снимке. Общая
   информация берётся по instrument UID: новая позиция того же инструмента
   на другом счёте не стирает валюту, эмитента и источники в зависимости
   от порядка счетов. Количество, стоимость и блокировки остаются по счёту.
3. `ChatContextEditor` отличает отсутствующий выбранный ID от явного
   «Все мои счета». Ошибочный портфельный контекст блокируется до загрузки
   или выбора доступного счёта; общий вопрос и явный выбор всех доступны.
4. `StrategyWorkspaceScreen`, используемый только debug `SpectrumDashboardProbe`,
   хранит сырые процентные строки на уровне saveable-черновика. Все три
   поля проверяются вместе при обоих способах сохранения и в самом callback.
   Неверный ввод сохраняется между вкладками/пересозданием, учитывается
   в dirty; отмена восстанавливает числа и строки. Пределы полей прежние.
   `StrategyDraftSaver` перенесён без изменения формата сохранённых данных.
   Это исправление debug-экрана, не изменение серверных правил стратегии.

### Почему проверка уведомления отказала после успешного действия

`visible_label(title)` вернул отдельный нативный Text заголовка.
`labels(node)` читает только text/content-desc этого узла, а «Прочитано»
расположено в соседнем Text. Ошибка подтверждается исходниками и сохранённым
кадром; полный XML отказа этим CI не экспортирован. Нельзя заменять условие
глобальным поиском «Прочитано»: другое событие fixture уже прочитано.
Теперь Text статуса имеет `notification-state-{id}`. Probe ограниченно
прокручивает до `notification-state-synthetic-notification` и проверяет его
собственный текст «Прочитано» после прежнего реального нажатия, открытия
диалога и возврата в исходное окно. Проверка окна повторяется в финальном
предикате. Возврат от предварительно найденного статуса доставки к заголовку
идёт к началу списка: при font200 заголовок находится выше viewport.
Общие helpers, ограничения прокрутки, ожидания и ACK-контракт сохранены.

### Локальная проверка объединённого кода

- **1505 backend tests / 1409 subtests PASS**, 25.57 s. 13 новых регрессий
  проходят HTTP-границы, persist/refresh, расчёт сценария, неизвестные валюты
  и оба порядка счетов. До исправления воспроизведены потеря lowercase-кода
  и зависимость общей информации об инструменте от порядка счетов.
- **6 JVM tests PASS** процентного черновика на Kotlin 2.4.10 / JRE17,
  включая настоящий Compose Saver 1.11.4 из закреплённого BOM. Проверены
  все три диапазона, незавершённый ввод, сохранение/восстановление и запрет
  подмены видимого неверного поля прежним числовым значением.
- Семь новых notification-регрессий выполняют реальный полный `notifications()`
  и bounded scroll helpers при font100/200, с обычными и package-qualified ID.
  До исправления воспроизведены оба отказа: проверка leaf-заголовка и поиск
  заголовка вниз от статуса. Другой прочитанный event, неверный ID, скрытый
  статус, другой package/window и отсутствие переходов диалога отвергаются.
  Окна и ACK в этих локальных тестах моделируются; реальный Android ещё требуется.
- Полный локальный CI-набор: **906 tests PASS**, 4 предусмотренных environment
  skips. Аудит **327 Python-файлов PASS**; `git diff --check` и независимое
  review полного сценария уведомлений PASS. Нативные файлы восстановления
  IME, `PlanEditor` и `LiveStrategyScreen` совпадают с проверенной основой `3bd89e55`.

Полный Sonar, Gradle/JVM/lint и обе API37-матрицы с фактическими 16384/4096
обязательны для нового SHA. Предыдущие результаты не переносятся как приёмка.
Существующий `[private-apk]` сохраняет приватный draft только после всех gates.
Физический телефон, установка нового backend, Telegram owner binding и
доставка точных APK-байтов в канал обновления остаются отдельными проверками.

## Подготовленная синхронизация server с 3bd89e55 — 23.10.2026

Область F01/F02/F16/F20/F22/F23. Родители подготовленного объединённого дерева:
server `7bd2b7327454cacc001a3360e2c275c6deee6570` и app
`3bd89e55a72ab99069a7f99a61dffcf473e32a2a`. Из app перенесены владение
состоянием выбранного задания вне ленивой карточки в Plans/AnalysisTimeline,
направление поиска статуса задания и последующие исправления навигации
проверок стратегии, истории, рынков и оформления. Общие helpers, ограничения
поиска и точные assertions сохранены; назначение 17 новых регрессионных методов
и результаты исходного кода описаны в сохранённых app-записях ниже.

### Границы объединения и локальная проверка

- Все **336 путей `app/` и `ci-ui-driver/`** совпадают с app по blob/mode,
  дополнительных app/driver-путей нет.
- Все **13 серверных путей** из `7bd2b732`, включая `deploy/OWNER_TIMEWEB.md`,
  сохранены по blob/mode. Все 12 изменённых недокументационных app-путей
  совпадают с опубликованным app; других отличий вне серверного набора нет.
- Конфликты возникли только в README и этом реестре. Полные истории обоих
  родителей сохранены, незастейдженных изменений и conflict entries нет;
  working/staged diff check — PASS.
- Полный объединённый Python CI-набор: **926 tests PASS** за 2.468s,
  **2 skips** из-за отсутствия Android SDK. Обе Java host-регрессии выполнены
  в этом запуске с проверенным JDK17, а не оставлены среди пропусков.
- Аудит всех **331 отслеживаемого Python-файла**: **0 failures**,
  compile-without-execution. Новые тесты включены в индекс до аудита.

Git-дерево `backend/` равно `5e242d006823e9305685a5c48f614587066b4644` и точно
совпадает с server-родителем `7bd2b732`; неизменённый локальный backend-набор
не повторялся. Собственные удалённые результаты этого родителя:

- [Backend CI 39911152183](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39911152183),
  job120274221174: **1540 tests / 1481 subtests PASS**, 43.61s.
- [Полный Sonar 39911146161](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39911146161),
  check120274750557: **0 OPEN/CONFIRMED всех типов, 0 новых, unique:0,
  complete:true**.

### Фактическая готовность установки и обязательные следующие проверки

Read-only workflow [39759477768, attempt 2](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39759477768/attempts/2)
успешно завершился 23.10.2026 в 06:30 UTC; наблюдение 06:30:24.213146Z.
В области видимости токена нет серверов, agents, floating IP, доменов
и поддоменов; результат complete_within_token_visibility=true. Это не
доказательство отсутствия ресурсов вне этих прав. Установка, фактический
публичный hostname/TLS и привязка владельца ещё не выполнены. Проверка
каталога и публичных цен является подготовкой; заказ, полная цена для
аккаунта и пригодность VM по измерениям не подтверждены. Предпосылки и
границы сохранены в PR #887; ресурсы в этой работе не изменялись.

App `3bd89e55` уже прошёл собственные удалённые quality gates:

- [Backend CI 39916113418](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39916113418),
  job120289949465: **1492 tests / 1409 subtests PASS**, 22.94s.
- [Полный Sonar 39916108082](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39916108082),
  check120290341418: **0 OPEN/CONFIRMED всех типов, 0 новых, unique:0,
  complete:true**.
- [Android CI 39916113435](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39916113435):
  preflight PASS; build120290545219 выполняется. Полного Android PASS ещё нет.

Предыдущий runtime `7f2ee50d` отменён во время session-context после spatial PASS;
cleanup120290373119 подтвердил verified_absent в 07:12:24 UTC. Это не полный
runtime-результат и не основание сохранить APK для выдачи.

Новый server SHA требует собственных Backend CI и полного Sonar. App
`3bd89e55` требует Gradle/JVM/lint и обеих полных API37-матриц на измеренных
16384/4096 байтах при font100/200, затем
приватного сохранения точных APK-байтов и cleanup. Локальное моделирование
прокрутки не заменяет native runtime; состояние выбранного задания вне
экрана ещё не объявляется измеренным. Публикация APK и проверка физического
телефона не подтверждены. Текущие результаты — в PR #880/#887.

## Сохранённые записи app/server

## Навигация UI-проверок при обрезанной области просмотра — 23.10.2026

Область F01/F22/F23, продолжение app `7f2ee50d179f4c59d7655a40791530b372ff97d0`.

### Подтверждённое состояние родителя

- [Backend CI 39914276490](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39914276490),
  job120284149515: 1492 tests / 1409 subtests PASS, 26.24s, strict Sonar PASS.
- [Полный Sonar 39914271384](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39914271384),
  check120284750369: 0 OPEN/CONFIRMED всех типов, 0 новых, unique:0, complete:true.
- [Android build120284211894](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39914276445/job/120284211894):
  все варианты, JVM-тесты и lint PASS, Gradle 9m17s; 886 CI tests,
  3 предусмотренных environment skips. Runtime120287782819 ещё не завершён
  на момент подготовки этого изменения; полного Android PASS и нового APK нет.

### Четыре подтверждённые ошибки маршрутов проверки

| Переход | Причина | Исправление |
| --- | --- | --- |
| Первый ввод срока стратегии | Поле после карточки состояния и вертикальных вариантов выбора искали вверх от начала страницы. | Первый поиск идёт вниз; повторный поиск от расположенной ниже кнопки остаётся вверх. |
| Выбор столбца истории | Общий helper всегда искал график вверх, хотя предыдущая проверка обычно заканчивалась на tooltip перед графиком. | Направление задаёт вызывающий код: вниз от tooltip, вверх только при возврате от подробной таблицы. |
| «Сессии» и возврат к «Географии» | Горизонтальный список вкладок расположен внутри вертикального; срез после введения и нижняя часть календаря не обеспечивали его доступность. | Сначала вертикальный поиск контейнера вниз от введения либо вверх от календаря, затем прежний горизонтальный выбор. Существующая проверка геометрии требует минимум 48×48 px. |
| «Отменить» после поворота оформления | Последняя проверка возвращалась к статусу несохранённого preview, а кнопка ниже него искалась вверх. | Этот поиск идёт вниз; применение, отмена, предпочтения, поворот и восстановление не изменены. |

Общие scroll helpers, ограничения числа действий, таймауты, native input,
проверки точного текста, дат, сумм, источников и предпочтений не ослаблены.
Дополнительных попыток нажатия или автоматического поиска в обоих направлениях нет.

### Регрессии и границы доказательства

Добавлены четыре тестовых файла, всего 13 методов. Они выполняют реальные
обработчики либо реальный helper выбора столбца и существующие bounded reveal
functions над обрезанными viewport-кадрами высотой 453 px, при font1/font2.
Исходный код воспроизводил неверные направления и недоступность вложенных вкладок.
Отсутствующие поле, график, контейнер вкладок и Cancel по-прежнему дают ограниченный
отказ; неверный день не вызывает повторного нажатия. Сохраняются проверки ввода
48, запрета пустого расчёта, точных координат и даты, source calls и отмены preview.

Поворот и несвязанные подготовительные этапы моделируются: эти тесты не доказывают
нативный поворот, сохранение настроек на устройстве или полную пригодность UI.
Полный локальный CI-набор: **899 tests PASS** за 3.738s, **2 skips** из-за отсутствия
Android SDK. Обе Java host-регрессии входят в успешный запуск с проверенным JDK17.
Аудит всех 325 отслеживаемых Python-файлов: 0 failures.
Независимый обзор изменений и diff check PASS. Backend, Kotlin и общие helpers
этим набором изменений не переписывались; соответствующие локальные наборы
повторно не запускались. Новые удалённые gates обязательны.

Результат нового SHA проверяется отдельно: полный Sonar 0 всех типов, Backend,
Gradle/JVM/lint, обе API37-матрицы с измеренными PAGE_SIZE 16384/4096 и font100/200,
затем приватное сохранение точных APK-байтов и cleanup. Текущий статус — PR #880/#887.

## Восстановление заданий: направление проверки и владение состоянием — 23.10.2026

Область F01/F16/F22/F23, продолжение app `2e644eb418c8ce8947cdeae115293a45137eb986`.

### Фактический результат родителя

- [Backend CI 39910907189](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39910907189):
  1492 tests / 1409 subtests PASS, 22.91s; строгий Sonar gate PASS.
- [Полный Sonar 39910903118](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39910903118):
  check120274035873, 0 OPEN/CONFIRMED всех типов, 0 новых, unique:0, complete:true.
- [Android CI 39910907192](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39910907192):
  build120273725402 PASS, Gradle 9m9s, все варианты/JVM/lint; 882 CI tests,
  3 предусмотренных environment skips. Runtime120277124735 подтвердил API37 /
  getconf PAGE_SIZE=16384, install/upgrade/launch preview SHA-256
  `c7063d9f99f00e90d0ca501173f18cf73841deb843a2666907a73dfbdf075a69`.
  Полный UI проверялся отдельной debug-сборкой на синтетических данных.
  Spatial, session, privacy, goals и business cases до plans/job прошли;
  прежний отказ risk/ready visible+hidden IME при font100 пройден.
  В plans/job/font100: `List target not reachable: Исход требует сверки`.
  4096 не запускался; private APK не удержан. Cleanup120281404659 PASS,
  `CI_PRIVATE_TRANSFER_CLEANUP=verified_absent`; итоговые gates FAILED.

### Подтверждённая ошибка навигации probe

Plans размещает WorkspaceJobPanel ниже PendingJobRecovery, Assistant — выше.
Общий job probe после recovery всегда искал вверх. На реальном 16384 runtime
сначала выполнена одна прокрутка к началу, затем девять получили performed=false;
failure.png показывает верхнюю вводную карточку «Ваш план действий».
Fixture сохраняет state=uncertain, а production отображает точный ожидаемый заголовок.
Четыре запроса и ноль contract errors видны на снимке; вывод о назначении каждого
запроса основан на исходниках, поскольку отдельный endpoint trace не сохранён.

Probe теперь ищет вниз для plans и вверх для assistant. Лимиты поиска,
настоящие accessibility-действия, точный заголовок и пояснение неопределённого
исхода, а также запрет кнопки повтора остаются прежними. Это исправление
проверки не доказывает отсутствия всех ошибок продукта; требуется новый runtime.

### Отдельное исправление жизненного цикла выбранного задания

Plans и AnalysisTimeline сохраняли ID задания на уровне экрана, но создавали
его модель через WorkspaceJobPanel(id) внутри LazyColumn item. При удалении
карточки из composition её LaunchedEffect и coroutine scopes отменяются,
хотя выбранный ID остаётся: опрос, завершение и обновление данных зависели от
видимости карточки. Это подтверждено устройством исходников, а не причиной
ошибки поиска выше. Обе страницы используют существующий rememberWorkspaceJobState
на уровне экрана и только отображают WorkspaceJobPanel(model) в прежнем месте.
Сессионные/job keys, foreground, cancellation/retry/close и callbacks сохранены;
shared-модель и Assistant не переписаны.

### Локальная проверка нового изменения

Четыре новых регрессионных теста выполняют настоящий _BusinessCase.job и
reveal_in_list над обрезанными viewport-кадрами. Старый код падал для Plans
при font1/font2; Assistant проходил. После исправления оба порядка проходят,
отсутствующие heading/detail по-прежнему завершаются ошибкой в прежних пределах,
recovery выполняется один раз. Это offline-проверка навигации, не показания устройства.
Полный CI-набор: **886 tests PASS**, 4 предусмотренных environment skips.
Из этих пропусков два Java host smoke отдельно прошли с проверенным JDK17:
полный поток IME beyond diagnostic cap и predictive-back event contract.
Локально не выполнены только два Android SDK-dependent host smoke.
Аудит всех 321 отслеживаемых Python-файлов: 0 failures.
Независимый обзор probe/tests и обоих Android callers, а также diff check PASS.
Локальная чистая JVM-компиляция не проверяет Compose disposal; продолжение опроса
вне экрана не объявляется измеренным. Backend исходники не менялись и его локальный
набор не повторялся; новый удалённый gate остаётся обязательным.

Новый SHA требует собственных Sonar, Gradle/JVM/lint и обеих полных API37-матриц
на измеренных 16384/4096 байтах при font100/200. Результаты фиксируются в PR #880/#887.

## Подготовленная синхронизация server с 2e644eb4 — 23.10.2026

Область F02/F20/F22/F23. Родители объединённого дерева:
server `986cea32285dee524ba1dc92282dd79118dddf95` и app
`2e644eb418c8ce8947cdeae115293a45137eb986`. Перенесены приоритет native IME
visibility в наблюдателе, чистый helper и регрессии следующего восстановления.
Изменены только три Kotlin production/test-файла и две сводки; серверные
привязка владельца, установка и проверки сохранены.

Сверка Git blob/mode подтверждает все **336 путей `app/` и `ci-ui-driver/`**
из app-кандидата без дополнительных путей и все **13 серверных путей**
из `986cea32`; число включает `deploy/OWNER_TIMEWEB.md`. Все три изменённых
Kotlin-файла точно совпадают с app-родителем. Конфликты были только в README
и этом реестре; полные истории обоих родителей сохранены ниже.

`backend/` и `.github/` в объединённом дереве точно совпадают с проверенным
server `986cea32`. Его собственные удалённые результаты:

- [Backend CI 39910469778](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39910469778)
  — **1540 tests / 1481 subtests PASS**, 19.34s.
- [Полный Sonar 39910465155](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39910465155)
  — check120272556279, **0 OPEN/CONFIRMED всех типов, 0 новых, unique:0,
  complete:true**.

Неизменённые локальные backend/Python CI-наборы не перезапускались. Предыдущие
локальные доказательства сохранены в истории: 1540/1481 backend, 909 CI tests
с четырьмя предусмотренными skips, аудит 326 Python-файлов. После этой синхронизации
проверены родители, точные файлы и поддеревья, отсутствие конфликтов и незастейдженных
изменений; working/staged diff check — PASS.

Для узкого исправления наблюдателя отдельно прошли **38 чистых Kotlin/JUnit-тестов**;
две регрессии mismatch падали до исправления. Этот запуск не включает Android/Compose,
реальный Bundle или расписание WindowManager. Ни прежние server-гейты, ни эти JVM-
тесты не заменяют собственные Backend CI/полный Sonar нового server SHA и quality,
Gradle/JVM/lint и обе полные API37 runtime-матрицы нового app SHA. Публикация APK,
физический телефон, новая VM, TLS и реальная привязка Telegram пока не подтверждены.
Актуальные результаты server — в PR #887, app — в PR #880.

## Сохранённые записи app/server

## Сохранение native-видимости IME без запаздывающего снимка — 23.10.2026

Область F22/F23, продолжение app `17605e2d0d83bc6ab5e69342ca50da7e8b125dac`.
Родитель имеет собственные [Backend CI 39909976410](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39909976410)
1492 tests / 1409 subtests PASS (21.16s) и [полный Sonar 39909969954](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39909969954)
на check120270915745: 0 OPEN/CONFIRMED всех типов, 0 новых, unique:0, complete:true.
Это подтверждает устранение замечания сложности стратегии. Полный Android
runtime для этого родителя ещё не подтверждён.

### Неверная запись, подтверждённая нативным журналом

В успешном восстановлении goal из runtime кандидата `8fedd5fe` editor7 при
elapsed391943 уже имел rootImeVisible=true, focus/windowFocus=true и RESUMED,
но Compose imeVisible=false. После request-show/restore-finished наблюдатель
записал restoreKeyboard=false; при elapsed392012 повторил false, а только
elapsed392122 вернул true. Интервал неправильного saveable состояния — 179 ms.
Аналогичный переход editor4 длился 69 ms. Второй поворот внутри этого интервала
в журнале не наблюдался, поэтому его последствие проверяется детерминированной
регрессией сохранения состояния и следующего restore, а не объявляется
воспроизведённым на эмуляторе.

При сохранении false следующий owner не создаёт visible handoff и передаёт
showKeyboard=false в restoreEditorInput, который явно ставит hide в очередь
сразу после фокуса. Это отдельная ошибка источника сохранённой видимости.
Она не доказывает и не исправляет случай, когда после best-effort show оба
источника остаются false.

### Узкое исправление источника наблюдения

Текущий view.rootWindowInsets имеет приоритет над снимком Compose, когда native
insets доступны. Native false также имеет приоритет над запоздавшим Compose true;
при отсутствии native insets остаётся прежний Compose fallback. Условия
receiveFocusEvents, фокуса поля/окна и RESUMED не изменены; нет новых запросов
фокуса, retry, sleep, timeout или вмешательства в скрытую/read-only реставрацию.
Регрессии проверяют сохранённое значение через настоящий restoreEditorInput.

Kotlin 2.4.10 / Temurin 17.0.21+9 / JUnit 4.13.2: точные чистые production-
декларации и исходные тестовые файлы скомпилированы; **38 tests PASS**
(20 handoff, 11 restoration, 4 plan, 3 strategy). До смены приоритета источника
тот же набор компилировался и падал ровно в двух новых случаях mismatch;
оставшиеся 36, включая null fallback, проходили. Между red/green изменился
только production EditorInputRestoration.kt, тестовые хеши совпадают, исходники
не менялись во время зелёного запуска. Независимое ревью и diff check PASS.
Android/Compose-обвязка, реальный Bundle и расписание WindowManager этим отдельным
JVM-запуском не проверены. Наборы backend/Python CI не перезапускались локально:
их исходные деревья не менялись после подтверждённых parent-gates.

Сервер `986cea32285dee524ba1dc92282dd79118dddf95` имеет собственные
[Backend CI 39910469778](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39910469778)
1540 tests / 1481 subtests PASS (19.34s) и [полный Sonar 39910465155](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39910465155)
на check120272556279: 0 OPEN/CONFIRMED всех типов, 0 новых, unique:0, complete:true.
Эти результаты относятся к его родителю app176 и не заменяют новую синхронизацию.

Новый SHA требует собственных удалённых проверок и обеих полных runtime-матриц
API37 / измеренных 16384 и 4096. APK, физический телефон, live Timeweb/TLS/Telegram
пока не объявляются проверенными. Текущие результаты фиксируются в PR #880/#887.

## Подготовленная синхронизация server с 17605e2d — 23.10.2026

Область F01/F02/F07/F16/F20/F22/F23. Родители объединённого дерева:
server `eb86ae681243edc865b8bd549ee2c2897afb0962` и app
`17605e2d0d83bc6ab5e69342ca50da7e8b125dac`. Сохранены точные сценарные
расчёты, загрузка редакторов, актуальный busy, передача IME, узкий рефакторинг
сложности стратегии и все изменения Telegram OIDC-привязки/установки сервера.
Конфликты ограничились README и этим реестром; обе истории сохранены ниже.

Сверка индекса по Git blob/mode подтверждает все **336 путей `app/` и
`ci-ui-driver/`** из app-кандидата без дополнительных путей. Все **13 серверных
путей** вне README/реестра совпадают с `eb86ae68`; число включает
`deploy/OWNER_TIMEWEB.md`. Все изменения app вне двух сводных документов также
совпадают с app-родителем, посторонних отличий от него нет.

На первом объединённом дереве server `eb86ae68` + app `e35d2d3f` выполнены:

- Полный backend: **1540 tests / 1481 subtests PASS**, 24.387s.
  Завершённый JUnit XML содержит 1540 testcases, 3021 проверку вместе с subtests,
  0 failures/errors/skips. Текстовый stdout не содержит итоговой сводки;
  результат подтверждён полным XML и exit code 0.
- Полный CI unittest: **909 tests, 4 предусмотренных environment skips,
  0 failures**, 1.057s; выполнены 905 тестов.
- Синтаксический аудит: **326 Python-файлов PASS**.

У app `17605e2d` относительно `e35d2d3f` изменены только LiveStrategyScreen,
README и этот реестр. После обновления merge сверены точные Git-деревья
`backend/` и `.github/`: они совпадают с проверенным объединённым срезом.
Полные наборы повторно не запускались; рабочий/staged diff check, отсутствие
неразрешённых конфликтов и сверка родителей/файлов — PASS.

Server-родитель `eb86ae68` имеет собственные успешные
[Backend CI](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39906102268)
и [полный Sonar](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39906096710)
0/0, complete:true. Эти результаты не заменяют удалённые Backend CI и полный
Sonar нового server SHA.

Точный app `17605e2d` подтвердил собственные проверки качества:

- [Backend CI 39909976410 / job120270458736](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39909976410/job/120270458736)
  — **1492 tests / 1409 subtests PASS**, 21.16s, strict Sonar gate PASS.
- [Полный Sonar 39909969954 / job120270438273](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39909969954/job/120270438273)
  — check120270915745, **0 OPEN/CONFIRMED всех типов, 0 новых, unique:0,
  complete:true**. Замечание сложности стратегии устранено без изменения gate.
- [Android CI 39909976699](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39909976699)
  — preflight PASS, build120270960697 выполняется; Gradle/JVM/lint и обе полные
  runtime-матрицы API37 / 16384 и 4096 ещё не подтверждены для этого SHA.
  Предыдущий прогон `e35d2d3f` отменён, cleanup подтвердил `verified_absent`.

Предыдущий runtime остаётся FAILED; локальные проверки не подтверждают
публикацию APK, физический телефон, новую VM, TLS или реальный вход владельца.
Результаты server фиксируются в PR #887, app — в PR #880.

## Сохранённые записи app/server

## Числовые границы, загрузка редакторов и передача IME — 23.10.2026

Область F01/F07/F22/F23, продолжение PR #880 от
`8fedd5fefbb612dba63cef5a97c69e70c6126c51`. Android 17 / API37,
Filament/GLB, package, версия и прежняя подпись сохраняются.

### Подтверждённые результаты кандидатов

- Промежуточный `e35d2d3fe0643249fe6ec77ed3c37ed368f2efb1` в
  [Backend CI 39909455304](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39909455304)
  прошёл 1492 tests / 1409 subtests за 23.06s и аудит 320 Python-файлов.
  Строгий Sonar gate корректно завершился FAILED:
  [полная выгрузка 39909449009](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39909449009)
  на check120269267571 содержит ровно 1 OPEN/CONFIRMED / 1 new / unique:1,
  complete:true — kotlin:S3776, сложность LiveStrategyScreen 51 при пределе 45.
  Новый узкий рефакторинг выносит StrategyEditorStatus и StrategyHistoryCard,
  сохраняя прежние LazyColumn items, состояние, callbacks, проверки busy и поля.
  По фактическому inventory из основной функции убраны вклады 5+9+1+1;
  точный результат подтвердит Sonar нового SHA. Порог и подавления не менялись.
- [Backend CI 39905550281](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39905550281)
  — 1482 tests / 1409 subtests, strict Sonar gate PASS.
- [Полный Sonar 39905546287](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39905546287)
  — check120257134844, 0 OPEN/CONFIRMED всех типов, 0 новых, unique:0, complete:true.
- [Android build120256605084](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39905550254/job/120256605084)
  — Gradle/JVM/lint и все APK PASS, 10m15s; 881 CI-тест (3 предусмотренных skips).
- [Runtime120260086954](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39905550254/job/120260086954)
  — install/upgrade/launch, spatial/session/balance и goal при обоих размерах
  шрифта PASS на API37 / измеренных 16384. Затем FAILED в risk/ready/font100:
  после поворота текст `5`, фокус и каретка 0:0 сохранены, клавиатуры нет.
  Полная бизнес-матрица 16384 не завершена, 4096 пропущен; cleanup120263209412 PASS.
  Предыдущий дефект доступности сохранения плана ещё требует результата этой матрицы.
- Server `eb86ae68` прошёл собственные [Backend CI](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39906102268)
  (1530 tests / 1481 subtests) и [полный Sonar](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39906096710)
  0/0, complete:true. Новые изменения этого раздела требуют отдельной синхронизации.

### Точный расчёт без повторной валидации выходной суммы как входа

Настоящие HTTP-запросы к `/workspace/risks/scenario` и
`/workspace/risks/scenarios/compare` воспроизвели 500 для `1e-40` на обычном
снимке 200 RUB с выбранной позицией 80 RUB. Точное изменение `8e-41` допустимо
для вычисленного Decimal, но повторный `decimal()` над денежной строкой
применял более узкие ограничения внешнего ввода, возвращал None и приводил
к TypeError при суммировании. Также воспроизведены ответы 200 с `complete=true`
и null при переполнении суммарного изменения или конечной стоимости.

Внутренний Decimal теперь передаётся прямо в сумму. Общий парсер, его пределы,
контекст точности и правила округления не менялись. Локальный `_scenario_money`
проверяет существующий контракт `money()` для изменения позиции, общего изменения
и полного итога; непредставимый результат даёт `422 scenario_result_out_of_range`.
Неизвестная оценка остаётся неполной с `estimated_after=null`.

Новые 10 HTTP-регрессий: до исправления 9 failures / 1 pass; после исправления
целевой набор 149 tests PASS. Полный backend: **1492 tests / 1409 subtests PASS**,
20.12s. Покрыты оба знака малого процента, ноль, сравнение 2–4 сценариев,
переполнение на трёх уровнях и неполная оценка.

### Первичная загрузка и восстановленный редактор

LiveStrategyScreen ранее показывал доступные поля до первого ответа и чтения
локального черновика, после чего безусловно заменял введённое пользователем.
Теперь доступность зависит от реально инициализированного saveable состояния:
первичная загрузка блокирует поля и radio, восстановленный черновик остаётся
доступным во время повторного GET. Обработчик повторно проверяет готовность
в момент вызова. WorkspaceAction.busy читает текущее состояние через getter,
поэтому ранее созданный callback видит запуск preview/confirm до рекомпозиции.

PlanEditor мог открыться до снимка, сохранить пустой account ID и после загрузки
показывать выбранным первый radio без соответствующего счёта и инструментов.
Теперь появление списка инициализирует только пустой ID. Явный или восстановленный
выбор не меняется при перестановке и временном отсутствии счетов; исчезнувший
выбранный счёт отображается без ложного radio-выбора с просьбой выбрать доступный.
Добавлены JVM-регрессии задержанной загрузки, восстановления, live busy и выбора
счёта; выполнение Android/Compose-кода требует нового CI.

### Переход между окнами при восстановлении клавиатуры

В неуспешном прогоне из 47 наблюдений IME видна только в первом, ещё старом
вертикальном окне. Перед новым диалогом Activity получает WINDOW_FOCUS_GAIN
с inputType=0, после чего система запускает hide; настоящий числовой редактор
диалога подключается позже. Сохранённое намерение показывать клавиатуру остаётся
true до request-show, поэтому потеря исходного saveable intent не является
первой причиной. В журнале есть автоматический
`HIDE_SOFT_INPUT_EXTRACT_INPUT_CHANGED` без команды пользователя.
[AOSP](https://android.googlesource.com/platform/frameworks/base/%2B/HEAD/core/java/android/inputmethodservice/InputMethodService.java)
связывает этот hide с TYPE_NULL. Сам журнал не доказывает, что смена
decorFitsSystemWindows является единственной причиной порядка событий.

Передача ввода защищает окно Activity ещё в родительской композиции диалога,
до его show. Ожидающие видимого восстановления редакторы удерживают защиту
родителя до готовности целевого окна и запроса показа. Готовность поля освобождает
только его целевое окно; завершение/отмена освобождает удержание родителя.
Защищённое удержание не может снять другой редактор под модальным окном.
Существующие флаги окон и очистка при отмене сохраняются.

Независимый разбор обнаружил и воспроизвёл второй порядок: диалог уже получил
фокус без полей, затем после асинхронной загрузки счетов появился восстановленный
редактор плана. Теперь освобождение текущей защиты не закрывает координатор:
поздний редактор снова защищает родителя до блокировки своего целевого окна.
Только удаление самого диалога окончательно запрещает новые удержания. Старые
callbacks не снимают новую защиту. Две регрессии на точных production-классах
сначала падали, затем прошли после этой коррекции.

Отдельная настоящая компиляция Kotlin **2.4.10** / Temurin **17.0.21+9** и
JUnit **4.13.2**: **35 tests PASS** (20 handoff, 8 restoration, 4 plan, 3 strategy).
Выполнены неизменённые исходные тесты над точными чистыми декларациями из текущих
файлов; хеши исходников до и после запуска совпали. Android/Compose-обвязка не
включена в этот отдельный запуск. Порядок Dialog дополнительно сверён с исходником
`androidx.compose.ui:ui-android:1.11.4` из официального Google Maven; фактическая
передача окна и системной IME остаётся обязательной проверкой эмулятора.

`decorFitsSystemWindows=false`, safeDrawing и проверка доступного сохранения
над IME остаются. Продуктовые Python-probes не менялись: они правильно выявили
отсутствующую клавиатуру. Новая отрицательная регрессия сохраняет исходную ошибку,
не принимает старый кадр за восстановление и не повторяет ввод.
Полный набор CI: **882 tests, 4 предусмотренных environment skips, 0 failures**,
0.943s. Синтаксический аудит: **320 Python-файлов PASS**.

Новый SHA требует собственных Sonar, Gradle/JVM/lint и обеих полных runtime-матриц
API37 / 16384 и 4096. APK, физический телефон, новая VM, TLS и реальная привязка
Telegram пока не объявляются проверенными. Результаты нового SHA фиксируются в PR.

## История предыдущих кандидатов

## Синхронизация server с 8fedd5fe — 23.10.2026

Область F01/F02/F07/F16/F20/F22/F23. Объединены server
`013937225a9f79a0a6728d29d6267faffbaf1869` и app
`8fedd5fefbb612dba63cef5a97c69e70c6126c51`. Исправления IME-insets,
готовности нативного ввода и currency-сценариев сохранены вместе с
одноразовой Telegram OIDC-привязкой владельца и установщиком Timeweb.
Конфликты ограничились README и этим реестром; обе истории сохранены ниже.
Все 334 пути `app/` и `ci-ui-driver/` совпадают с app по blob/mode, лишних путей нет.
Все 13 серверных путей вне двух сводных документов сохранены из `01393722`;
в это число входит `deploy/OWNER_TIMEWEB.md`.

Проверено полное объединённое дерево:

- Backend: **1530 tests / 1481 subtests PASS**, 23.16s.
- CI unittest: **908 tests, 4 предусмотренных environment skips, 0 failures**,
  0.993s; выполнены 904 теста.
- Синтаксический аудит: **325 Python-файлов PASS**.
- Рабочий и staged diff check, сверка blobs/modes — PASS.

Удалённые проверки app `8fedd5fe`:

- [Backend CI 39905550281](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39905550281)
  успешен, включая строгий Sonar gate.
- [Полный Sonar 39905546287](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39905546287)
  подтвердил check `120257134844`: 0 OPEN/CONFIRMED всех типов, 0 новых,
  unique 0, `complete:true`. Для main `f5491216` также подтверждены 0/0.
- [Android CI 39905550254](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39905550254)
  выполняет сборку; обе полные runtime-матрицы API37 ещё требуют результата.

Новый server SHA требует собственных удалённых Backend CI и полной выгрузки
Sonar; результаты родителей не заменяют его проверку. Статус нового среза
фиксируется в PR #887. Реальная установка Timeweb, TLS, вход владельца через
Telegram, физический телефон и выпуск APK этой синхронизацией не подтверждены.

## Сохранённые записи app/server

## Диалоги над клавиатурой и валютные сценарии — 23.10.2026

Область F01/F07/F22/F23, продолжение PR #880. Android 17 / API37,
Filament/GLB, нативный ввод, package и прежняя подпись сохраняются.

### Подтверждённое исходное состояние

- `main` остаётся на `f54912165127bfab42673743cd141d635e20881f`:
  [Backend CI](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39669696793)
  успешен; [полная выгрузка Sonar](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39669696991)
  содержит 0 OPEN/CONFIRMED всех типов, 0 новых, unique:0, complete:true.
- Последний [Android CI `fa9f5b22`](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39852793494)
  прошёл build/JVM/lint; runtime job `120088492180` подтвердил установку,
  обновление и запуск на API37 / фактических 16384 байт. Risk и assistant
  при font100 прошли, включая исправленный повтор сообщения ошибки.
  Следующий `plans/ready` завершился `List target not reachable: Проверить и сохранить расчёт`.
  Полная матрица 16384 не завершена, 4096 пропущен; новый APK не выдан.
- Серверная ветка `01393722` имеет собственные успешные Backend и Sonar.
  Новая VM, TLS и привязка владельца Telegram этими проверками не подтверждены.

### Доступность действий при открытой клавиатуре

В сохранённом кадре quantity содержит `5`, числовая IME открыта и перекрывает
нижнюю часть формы. Область `workspace-content` всё ещё доходит до y=616;
последующие прокрутки не сдвигают её. Общий `WorkspaceDialog` не учитывал
IME-insets. Теперь `DialogProperties(decorFitsSystemWindows=false)` и внешний
`safeDrawingPadding()` ограничивают область прокрутки с учётом клавиатуры,
системных панелей и вырезов. Ширина, пределы 600/680dp и общий 3D-renderer сохранены.
Дополнительный `imePadding` не нужен: safeDrawing уже содержит и потребляет IME.
[Контракт Android](https://developer.android.com/develop/ui/compose/system/insets-ui).

Отдельно тест мог вызвать dismiss до появления IME: единственное false-наблюдение
не ожидало асинхронного показа. Журнал фиксирует последующее onShown без hide;
точное раннее false в старом журнале не записано. Поведенческая регрессия
с отложенным показом клавиатуры воспроизводит прежний отказ. Ввод теперь ждёт
нативные focus/IME, затем точный текст и каретку; пустое поле допускает
корректный Compose selection -1/-1 до первого символа. Проверка плана требует
доступной кнопки сохранения над видимой клавиатурой. Критерии runtime не ослаблены.

### Валюта инструмента в сценариях риска

Концентрации и их picker используют `instrument_currency`, но `_scenario_position`
сопоставлял currency-сценарий с `value.currency`. Для USD/EUR-инструментов в
рублёвом снимке это давало 422, а RUB затрагивал все оценённые в рублях позиции.
Сопоставление использует тот же существующий `instrument_currency(item)`;
подпись Android изменена на «Валюта инструмента». Денежная арифметика, валюта
оценки и запрет выдуманной FX-модели не менялись. Неизвестная/некорректная
валюта сохраняет неполный ответ и `estimated_after=null`.

Все 7 новых HTTP-регрессий падали до исправления и прошли после него:
USD/EUR/RUB, неизвестная валюта и compare двух сценариев на одном снимке.
Полный backend: **1482 tests / 1409 subtests PASS**, 20.70s; compileall и
diff check PASS. В `main` нет `volume_state.py`: этот дефект относится к 3D-ветке.
Полный локальный набор CI: **881 tests, 4 предусмотренных platform/environment
skips, 0 failures**, 0.932s. Первые две ошибки Node были ограничением локальной
песочницы; запуск в рабочей среде прошёл без изменения тестов или их критериев.
Отдельный read-only обзор серверной ветки `01393722`: 126 tests / 183 subtests
PASS; воспроизводимых новых дефектов в проверенных owner-enrollment,
порядке установки и network-inventory сценариях не обнаружено.
Новый SHA ещё требует собственных Sonar 0/0, Android build и обеих полных
матриц API37 / 16384 и 4096. Результаты фиксируются в PR #880; физический
телефон, новая установка Timeweb и выпуск APK пока не объявляются проверенными.

## Подготовленная синхронизация server с fa9f5b22 — 22.10.2026

Область F01/F02/F16/F20/F22/F23. Локальный merge подготовлен с родителями
`1c9f95aafb0612e808fcaefc1feb78b1d4dcb9fe` (server) и
`fa9f5b22d754b0622e4599945f38f4d1c5c65926` (app).
Все 334 файла `app/` и `ci-ui-driver/` совпадают с app-кандидатом по blob/mode;
все 13 серверных путей сохранены из `1c9f95aa`. Конфликты были только в README
и этом реестре; полный текст обоих родителей сохранён ниже.

Полный локальный CI-набор сервера: **903 tests PASS**, 4 предусмотренных skips,
0.868 s. Diff check — PASS. Дерево `backend/` полностью совпадает с `1c9f95aa`,
поэтому pytest повторно не запускался. Новый server SHA должен получить
собственные удалённые Backend CI и полный Sonar; результаты родителя
не заменяют приёмку нового коммита.

Удалённые проверки app `fa9f5b22`:

- [Backend CI 39852793503, job120083108590](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39852793503/job/120083108590)
  — **1475 tests / 1409 subtests PASS**, 23.03 s; синтаксический аудит 316 файлов
  и строгий Sonar gate — PASS, 0 annotations.
- [Полный Sonar 39852786612, job120083083951](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39852786612/job/120083083951)
  — 0 OPEN/CONFIRMED, 0 новых, unique 0, `all_types:true`, `complete:true`;
  exact-head check120083919493.
- [Android CI 39852793494, build120083203022](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39852793494/job/120083203022)
  ещё выполняется. Полные runtime-матрицы нового app-кандидата не подтверждены.

## Сохранённые записи обоих родителей

## Ошибка и пустая история ассистента — 22.10.2026

Область F01/F16/F22/F23, продолжение PR #880. Android 17 / API37,
Filament/GLB, нативный ввод, package и подпись сохраняются.

### Завершённый CI кандидата 211c6de1

Точный head `211c6de16fb50e2d0eaf8f1d71033fc43401da26`:

- [Backend39846798072](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39846798072)
  — 1475 tests / 1409 subtests PASS, strict Sonar 34 gate tests / 0 annotations.
- [Полный Sonar39846787949](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39846787949)
  — 0 OPEN/CONFIRMED всех типов, 0 новых, scope all_open_and_confirmed,
  all_types:true, complete:true, exact-head check120063016118.
- [Android build120063248061](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39846798007/job/120063248061)
  — PASS: 875 CI-тестов (3 предусмотренных skips), Gradle/JVM/lint,
  debug/preview/release APK и test-only driver; BUILD SUCCESSFUL in 9m 11s.
- [Runtime120068641831](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39846798007/job/120068641831)
  — API37, фактический PAGE_SIZE 16384; install/upgrade/launch прошли.
  Preview APK SHA-256 `e82e521e6b0879e26f9ba316763d74c2cedea6335baa189879f26800520c2b9f`.
  Risk ready/empty/partial/error и assistant ready/empty/partial при font100
  прошли. Следующий assistant/error остановился после retry; итоговый Android
  gate FAIL, профиль 4096 пропущен. Полная business/portfolio-матрица при
  font200 не достигнута; отдельные spatial/goal-проверки font200 прошли.
- [Cleanup120078389274](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39846798007/job/120078389274)
  — CI_PRIVATE_TRANSFER_CLEANUP=verified_absent. Новый приватный APK не выдан.

В assistant/ready прошли прежние проверки сохранения текста, фокуса, caret,
видимой IME, стабильных кадров, post-capture и возврата ориентации. Для risk
также прошёл намеренно скрытый ввод. NATIVE_EDITOR_RESTORE_TRACE после успешных
поворотов содержит 7 restore-start / 7 restore-finished и 0 restore-not-ready.
В ограниченной истории IMMS новые assistant WINDOW_FOCUS_GAIN имеют тип
редактора 163841. Это доказательство
font100 на одном 16KB-профиле, а не приёмка всех сред или физического телефона.

### Причина следующего отказа и исправления

Первый точный ERROR и нажатие «Повторить» прошли; число синтетических запросов
выросло до 2, ошибок контракта 0. После прокрутки к кнопке текст ошибки был
выше текущего viewport. Второй `reveal(ERROR)` искал только к концу списка:
одна результативная и девять безрезультатных прокруток завершились прежним
`List target not reachable`. WorkspaceEmpty располагает текст перед Retry;
при повторном запросе resource сохраняет ошибку. Исправление меняет только
направление второго поиска на `start`; exact ERROR, actual retry, рост requests,
driver, лимиты и таймауты сохранены. Новая viewport-регрессия использует
настоящий reveal_in_list: до исправления воспроизведён тот же отказ после
10 прокруток вниз, после исправления целевой набор 6 tests PASS.

Скриншот также показал приглашение «С чего начнём?» при не загруженной истории.
Теперь оно требует `messages.data != null`, отсутствия error и busy и пустых
messageItems. Проверка error нужна и при сохранённых пустых data после
неудачного refresh. Успешно загруженная пустая история сохраняет приглашение;
IME, отправка, стоимость, snapshot и recovery этим изменением не затронуты.

Полный локальный CI-набор нового совместного дерева: 876 tests PASS,
4 существующих environment skips, 0.893 s. Diff check и независимое review
скриншота, app guard и поведенческой регрессии — PASS. Новый head требует
собственных Backend, полного Sonar 0/0, Android build и обеих полных матриц
API37 / 16384 и 4096. Прежний частичный успех не заменяет эти gates.
Серверный `1c9f95aa` отдельно прошёл Backend 1523 tests / 1481 subtests и
полный Sonar 0/0; новая VM, TLS, Telegram owner binding и канал обновления
этими проверками кода не подтверждены.

**Ниже сохранена история предыдущих кандидатов:**

**Предыдущая синхронизация серверной ветки:**

## Локальная синхронизация server/app — 22.10.2026

Область F01/F02/F16/F20/F22/F23. Подготовлено объединённое дерево для merge с родителями
`34ac2cbe1393c792d2f3e40723928fcc4047f3ba` (серверная ветка) и
`211c6de16fb50e2d0eaf8f1d71033fc43401da26` (app-кандидат).
Одноразовая привязка владельца и общий валидатор Telegram OIDC сохранены;
перенесены EditorImeHandoff, доступность черновика ассистента, исправление
валидации дат, диагностика IMMS и перенос формирования payload в
ChatRequestSnapshot.messagePayload. Конфликты возникли только при добавлении
истории в README и этот реестр; записи обеих веток сохранены ниже.

Сверка индекса по Git blob SHA и mode подтвердила:

- Все 334 файла `app/` и `ci-ui-driver/` совпадают с `211c6de1`.
- Все 17 изменённых app-путей вне README/реестра совпадают с app-кандидатом,
  включая backend/volume_contract.py и восемь регрессий диапазона дат.
- Все 13 серверных путей вне README/реестра сохранены из `34ac2cbe`, включая
  Telegram OIDC, enrollment, installer и серверные workflow. Неожиданных
  различий относительно объединения этих двух наборов нет.

Проверки предшествующего объединённого дерева
`acfb2d2932d23bea5bb8f2d3941842ad5b44b91a`:

- Полный backend: **1523 tests / 1481 subtests PASS**, 23.55 s.
- Полный CI-набор: **902 tests PASS**, 4 предусмотренных environment skips, 1.030 s.
- Tools: **52 tests PASS**, 0.033 s.
- Синтаксический аудит **322 Python-файлов** и diff check — PASS.

Точное сравнение текущего индекса с этим проверенным деревом показывает только
три изменённых файла: AssistantWorkspaceScreen.kt, README.md и этот реестр.
Git trees `backend/`, `.github/scripts/` и `tools/` полностью совпадают;
полные локальные наборы не запускались повторно. Сверка нового индекса,
сохранности серверных изменений и diff check — PASS.

Удалённые проверки app-кандидата `211c6de16fb50e2d0eaf8f1d71033fc43401da26`:

- [Backend CI 39846798072, job120062102026](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39846798072/job/120062102026)
  — **1475 tests / 1409 subtests PASS**, 26.87 s; строгий Sonar gate — PASS,
  34 tests, 0 annotations.
- [Полный Sonar 39846787949, job120062066777](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39846787949/job/120062066777)
  проверил exact SHA `211c6de1`; check120063016118 подтверждает 0 OPEN/CONFIRMED,
  0 новых, `all_types:true`, `complete:true`.
- [Android CI 39846798007](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39846798007)
  ещё выполняется. Backend/Sonar PASS не означает прохождения полных runtime-матриц.

Новый серверный коммит должен получить собственные Backend CI и полный Sonar inventory в PR #887;
результаты `34ac2cbe` и app-кандидата не переносятся на него как приёмка.
Android-проверки `211c6de1` относятся к app-кандидату в PR #880; обязательные
матрицы API37 / 4096 и 16384 сохраняются. Новая VM, TLS, фактический Telegram
OIDC-вход и привязка владельца, APK и канал обновления здесь не проверялись.

## Сохранённая история app/server

## Исправления черновика и диапазона дат — 22.10.2026

Область F01/F16/F22/F23. Изменения сохраняют Android 17 / API37,
настоящий Filament/GLB, package, прежнюю подпись и неизменные критерии
видимой/скрытой IME. Разработка продолжается в PR #880.

### Локальный черновик и восстановление ввода

В завершённом `5c22501d` риск при font100 прошёл оба поворота, а ассистент
остановился с сохранёнными текстом, фокусом и caret `5:5`, но без IME.
`rememberJobCheckpoints()` после recreation начинает локальное чтение
с `loading=true`; прежний общий `busy` на это время отключал редактор.
История IMMS фиксирует сначала `TYPE_NULL`, затем корректный editor type
в одном окне. Она не показывает, какой объект EditorInfo обрабатывался
внутри позднего IME callback, поэтому единственная причина всех отказов
клавиатуры по этим записям не объявляется доказанной.

`AssistantComposerAvailability` разделяет локальное редактирование и
разрешение отправки. Только чтение checkpoints перестаёт отключать поле;
known recovery/error/pending, активные send/estimate/job/recovery сохраняют
прежние ограничения. Загрузка продолжает блокировать отправку и выбор
модели. Сам обработчик до изменения pendingEstimate и сетевого действия
теперь проверяет valid и canSubmit. Четыре JUnit-регрессии проверяют
переход loading/ready, обнаружение незавершённого запроса, повтор чтения
при ошибке и одновременную активную операцию; callback запрещён во всех
закрытых состояниях. Snapshot-проверки, стоимость и storage.prepare сохранены.

Параллельный `8e441b33d626485b6ed2e64b6650bddbb01e5f7f` получен из GitHub
и включён fast-forward без потери изменений. Его `EditorImeHandoff`
сохраняется; совместимость с доступностью черновика проверена независимо.
Backend этого SHA прошёл 1467 tests / 1409 subtests, однако строгий Sonar
gate обнаружил 9 параметров в restoreEditorInput при допустимых 7.
Это отдельное замечание новой структуры, а не ошибка серверных тестов.
Связанные setKeyboardVisible/prepareInput/releaseInput объединены в
EditorInputCommands: параметров стало 7, порядок вызовов, ранние возвраты,
default callbacks, try/finally и assertions сохранены. Правило не подавлено.

### Валидация диапазона дат до арифметики

`date_range(None, date(1, 1, 1))` и `date(1, 1, 30)` раньше выбрасывали
OverflowError до проверки допустимого периода. Дата проходит синтаксический
разбор HTTP-параметров, поэтому ошибка достигала `/workspace/refresh`
и `/workspace/instruments/{uid}/candles`. Конец периода теперь проверяется
до вычитания default lookback. Ответ — `422 invalid_date_range`; задание
не создаётся и брокер не вызывается. Допустимые границы и default lookback
сохраняют прежнее поведение. Из 8 новых регрессий до исправления 4 падали
с исходным OverflowError, после исправления проходят все.

### Проверки при подготовке совместного кандидата

- Полный backend: 1475 tests / 1409 subtests PASS, 21.67 s.
- Полный CI-набор после fast-forward: 875 tests PASS, 4 предусмотренных skips.
- Tools: 52 tests PASS; diff check и Python syntax PASS.
- Kotlin 2.4.10 / JRE17: 23 JVM-теста PASS (4 composer, 8 restoration,
  11 handoff/ownership). Для отдельного запуска без Android SDK чистые
  handoff-классы скопированы дословно из исходного файла; Android/Compose
  wrapper этим прогоном не компилируется и требует полного Gradle CI.
- Независимое review доступности черновика и её совместимости с handoff — PASS.

Новый совместный SHA требует собственной компиляции Android, JUnit/lint,
строгого Sonar и обеих полных матриц API37 / 4096 и 16384. Итоги последнего
SHA фиксируются в PR #880. Ни прежние результаты, ни наличие исходников
не заменяют runtime; APK, физический телефон и новая установка Timeweb
не объявляются проверенными на основании этих локальных прогонов.

### Результат CI 7640325e и следующий рефакторинг

[Backend CI 39845827773](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39845827773)
на `7640325ed767200446d2c15f5decd771a2e1df26` выполнил
1475 tests / 1409 subtests, 32.71 s. Его общий результат — FAIL только
из-за строгого Sonar gate: [полный аудит 39845815289](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39845815289)
нашёл одно новое OPEN/CONFIRMED замечание, `all_types:true`, `complete:true`.
В AssistantWorkspaceScreen Cognitive Complexity составила 46 при лимите 45.

Формирование тела отправки перенесено из вложенной startMessage-лямбды
в ChatRequestSnapshot.messagePayload. Набор и значения полей, условный
confirm_premium, генерация UUID после проверок и все guards отправки
сохранены. Это структурный рефакторинг без подавления правил или изменения
лимитов. Повторный полный Sonar, Gradle и обе runtime-матрицы должны
проверить новый SHA; результаты родителя их не заменяют.

## Журнал предшествующих срезов

**Последний завершённый CI и полученная история IME, F01/F16/F22/F23, 22.10.2026:**
Проверенный head `5c22501db3b5233ab6b2f96e3f10fa627d9a7e8f`:

- [Backend 39837751829, job120030419618](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39837751829/job/120030419618)
  — PASS: 1467 tests / 1409 subtests; строгий Sonar gate также прошёл.
- [Полный Sonar 39837737653, job120030375994](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39837737653/job/120030375994)
  — 0 OPEN/CONFIRMED всех типов, 0 новых, `complete:true`,
  scope `all_open_and_confirmed`; exact-head check120031628969.
- [Android 39837751847, build job120030860689](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39837751847/job/120030860689)
  — PASS: готовый Temurin JDK `17.0.20.1+1` проверен; 875 CI-тестов,
  3 предусмотренных пропуска. Gradle debug/preview/release APK, test-only
  driver, lint и JVM-тесты прошли; `BUILD SUCCESSFUL in 9m 20s`.
- [Runtime job120036125111](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39837751847/job/120036125111)
  — FAIL на `assistant/ready/font100` при повороте собственного окна Activity
  (`dialog:false`). На Android 17 / API37 с измеренным PAGE_SIZE 16384
  установка, обновление и запуск preview прошли. В этом же запуске прошли
  оба поворота диалога риска при font100: с видимой IME и после её явного
  скрытия. Это частичные результаты одного запуска, не полная UI-приёмка.
- В отказавшем assistant-сценарии черновик, native focus и caret `5:5`
  сохранились. Из 47 наблюдений единственный кадр с видимой IME относится
  к старому portrait-окну; в новой ориентации видимая IME не наблюдалась.
  Матрица 16384 не завершена, 4096 пропущена. Aggregate job120042229788
  и authoritative job120042274066 корректно завершились FAIL.
- [Cleanup job120042159912](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39837751847/job/120042159912)
  — PASS: `CI_PRIVATE_TRANSFER_CLEANUP=verified_absent`; отсутствие временного
  release и tag подтверждено HTTP 404. Выдача device-test APK и публикация
  не выполнены.

Диагностика после отказа впервые дала пригодную для сопоставления ограниченную
историю IMMS: из 32 StartInput-записей 31 отнесена к кандидату, одна
не атрибутирована, отклонённых парсером нет; все 16 show/hide-записей приняты,
отклонённых нет. Это ограниченные системные кольцевые истории, не полный
непрерывный журнал. События одного сбора:

| Время в записи | Наблюдение |
| --- | --- |
| 19:32:25.515 | Восстанавливаемый редактор: `enabled:false`, фокуса ещё нет. |
| 19:32:25.550 | StartInput `WINDOW_FOCUS_GAIN`: `TYPE_NULL` / `input_type:0`, порядковый идентификатор Binder-окна `19`. |
| 19:32:25.676 | Восстановление продолжилось с `enabled:true`. |
| 19:32:25.694 | Поле получило native focus, `viewIsTextEditor:true`. |
| 19:32:25.756 / .757 | В том же Binder-окне `19` зарегистрирован `input_type:163841`: `CHECK_FOCUS`, затем `APP_CALLED_RESTART_INPUT_API`. |

Идентификатор `19` относится только к очищенной Binder-проекции этого сбора;
порядковые идентификаторы WM ведутся отдельно. Отказ относится к собственному
окну Activity ассистента. Гипотеза об исключении лишь родительского окна
модального WorkspaceDialog не объясняет этот сценарий.

**Подготовленное исправление, runtime ещё не подтверждён:**
`EditorImeHandoff` временно исключает собственное окно из IME-target
(`FLAG_ALT_FOCUSABLE_IM`), пока восстанавливается редактор с ранее видимой
клавиатурой, в том числе во время ожидания enabled. Ближайший
`DialogWindowProvider` определяет окно диалога; иначе используется Activity.
Passive readiness требует `view.isFocused && view.onCheckIsTextEditor()`.
После подготовки любой реальной input session этого окна ограничение
освобождается: disabled-редактор не блокирует другой готовый редактор.
Refusal, ошибка, cancellation и disposal освобождают индивидуальное владение;
учёт по идентичности Window и поколению защищает новое владение от старого cleanup.
Исходный ALT и изменения прочих flags сохраняются. Текстом по-прежнему владеет
caller; новые данные текста или секретов в saved state не добавлены.

В [Android 17 r1 ImeFocusController](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-17.0.0_r1/core/java/android/view/ImeFocusController.java)
снятие ограничения обнаруживается на следующем traversal готового окна:
система вызывает обычный window-focus input path для текущего focused View.
Кандидат сохраняет прежние window/frame barriers перед явным show и прежний
порядок hidden/readOnly. Дополнительных таймеров или повторов show нет.
Окно loading до композиции редактора этим guard не охвачено; обязательные
update/auth gates сохраняются. Исправление направлено на измеренную гонку
после композиции поля, а не объявляется доказательством всех startup-путей.

Локально — 875 CI-тестов PASS (4 существующих environment skips, 0.885 s),
diff check и независимое ревью PASS. Два связанных JVM-класса содержат
19 test methods: 11 новых проверок handoff и 8 проверок восстановления,
включая два новых отказа подготовки и расширенную проверку cleanup при отмене.
Локальный JVM недоступен (`libjli.so`); их выполнение и компиляция остаются
удалёнными CI gates. В risk/assistant после полного успешного поворота,
post-capture наблюдения и возврата ориентации читается та же ограниченная
история IMMS. Это отдельное чтение после проверки, не изменение её ожиданий.
История после отказа остаётся до cleanup; tracker по-прежнему включается
только при отказе. Новый `restore-not-ready` точнее отражает оба вида отказа:
фокус не принят или native input session ещё не готова.

Новый кандидат требует собственного полного CI и обеих API37-матриц;
исходные visible/hidden проверки, driver, таймауты и критерии не ослаблены.

0.11.0 / 35 остаётся кандидатом только для Android 17 / API37. Совместимый
приватный APK владельцу допускается после обеих полных матриц 4096/16384
на его точных байтах с прежними package и подписью. Проверка телефона,
новая установка Timeweb и канал обновления не подтверждены этим запуском;
разрешение на отдельную серверную работу сохраняется.

**Предыдущие записи сохраняют состояние на момент указанных кандидатов:**

**Уточнение диагностического парсера, F01/F16/F22/F23, 22.10.2026:**
На `eb0d64221415e2ce5663a5e7d35e0068204f68fe`
[Backend39836987926](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39836987926)
прошёл 1467 tests / 1409 subtests (16.75 s), но строгий quality gate отказал.
[Полный Sonar39836976759](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39836976759)
зафиксировал ровно одно новое открытое `python:S6353`, все типы, complete:true:
рекомендацию concise digit class в `.github/scripts/ime_service_history.py`.
Исправление использует `\d` и явный `re.ASCII` на всех четырёх `fullmatch`;
ограничение только ASCII-цифрами сохранено. Добавлены случаи Unicode digits
в полях StartInput/ShowHide и идентификаторах окон. Gate не ослаблен;
приложение, driver, ввод и обе матрицы не изменены. Новый head требует своего CI.
Локально — 875 CI-тестов PASS, 4 существующих environment skips, 1.012 s;
включены 14 parser tests. Диагностический отказ не объявляется исправленным.

**Android CI восстановлен до runtime; отказ IME остаётся, F01/F16/F22/F23, 22.10.2026:**
Проверенный кандидат `0fded2305511a10291907543c562a6cd66305f32`:

- [Android 39832771304](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39832771304),
  build job120013086317 — PASS. Реально проверен готовый Windows tool-cache
  Temurin JDK `17.0.20.1+1`; 860 CI-тестов с 3 предусмотренными пропусками,
  Gradle debug/preview/release APK, test-only driver, lint и unit tests прошли.
  Прежний отказ загрузки setup-java больше не блокирует этот Windows build.
- [Backend 39832771138](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39832771138)
  — 1467 tests / 1409 subtests PASS; [полный Sonar 39832761671](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39832761671)
  — 0 OPEN/CONFIRMED всех типов, 0 новых замечаний.
- Runtime job120018290841 — FAIL на API37 / измеренных 16384 байтах при
  повороте диалога риска. Черновик `5`, native focus и caret `0:0` сохранены,
  IME после поворота отсутствует. Полная UI-матрица 16384 не пройдена;
  профиль 4096 пропущен после отказа. Подготовка образов не считается его проверкой.
- Cleanup job120022849876 — PASS: `CI_PRIVATE_TRANSFER_CLEANUP=verified_absent`.
  Отсутствие временного release и tag подтверждено двумя HTTP 404;
  aggregate120022914200 и authoritative120022962270 корректно FAIL.
  Выдача device-test APK и публикация пропущены; проверенный APK не выдан.

Платформенные show-запросы завершаются отказом либо отменой. Server hide
завершился скрытием; поздний IME-запрос
`HIDE_SOFT_INPUT_EXTRACT_INPUT_CHANGED` отменён в состоянии ALREADY_HIDDEN.
Этот поздний запрос не доказывает причину ранее скрытой клавиатуры.
Фактическая история EditorInfo на причинном интервале ещё не получена;
сохранённые focus/caret сами по себе не подтверждают готовый InputConnection.

Текущее изменение добавляет только диагностику после отказа: bounded
очищенная проекция критической истории `dumpsys input_method` с привязкой
к кандидату. Продуктовый порядок фокуса/show/hide, действия driver,
таймауты и критерии приёмки сохраняются. Изменение не объявляется исправлением
IME; новый SHA ещё должен пройти собственный полный CI и обе API37-матрицы.
Исторические успешные части не переносятся на будущий кандидат как приёмка.
Локальный общий набор — 873 CI-теста PASS, 4 существующих environment skips,
0.889 s с writable TMPDIR и `NODE_OPTIONS=--test-isolation=none` для данного
окружения. Включены 12 новых тестов парсера; интеграционный сценарий проверяет
исходную ошибку и чтение истории до восстановления ориентации. Независимое
ревью сверило формат с Android 17 r1 и отсутствие вывода текста/сырых имён.

**Параллельная серверная ветка, F02/F20/F23:**
`34ac2cbe1393c792d2f3e40723928fcc4047f3ba` включает синхронизацию с `0fded230`.
[Backend 39833845532](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39833845532)
— 1515 tests / 1481 subtests PASS;
[полный Sonar 39833836376](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39833836376)
— 0 OPEN/CONFIRMED и 0 новых замечаний. Это проверка серверного кода,
не новая установка Timeweb, не проверенный OIDC-вход и не доставка APK.

**Предыдущая синхронизация серверной ветки:**

**Синхронизация серверной ветки, F01/F02/F16/F20/F22/F23, 22.10.2026:**
Объединены server `a6f2568a` и app `0fded230` с сохранением обоих родителей.
Сохранены одноразовая привязка владельца Telegram и серверные проверки;
перенесены проверка установленного JDK для Windows-сборки и актуализация
документации Android 17. Сверка Git blobs и modes подтвердила совпадение всех
330 файлов app/driver и восьми остальных изменённых путей app с `0fded230`;
все 13 серверных путей вне README/реестра, backend и deploy сохранены из `a6f2568a`.
Локально прошли 887 CI-тестов (4 предусмотренных пропуска), 52 проверки
инструментов, синтаксический аудит 319 Python-файлов и diff check.
Backend-набор повторно не запускался: его код и тесты побайтово не изменились.
Синхронизация исходников не подтверждает развёртывание сервера.
Собственные Backend CI и полный Sonar нового server-head обязательны;
результаты предыдущего коммита не переносятся на новый SHA.
Полная Android-матрица app-кандидата проверяется отдельно в PR #880;
она не заменяет проверку объединённого server-head и реальную установку сервера.


**Восстановление подготовки сборочной машины, F01/F22/F23, 22.10.2026:**
Последний проверенный head `8fe52f6098cef1a90e45fc3ba95c773f20405a1a`:

- [Backend 39795793706](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39795793706),
  job119882660791 — 1467 tests / 1409 subtests PASS, 23.68 s;
  strict Sonar gate: 34 tests, 0 annotations, PASS.
- [Полный Sonar 39795784530](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39795784530),
  job119882632160 — 0 OPEN/CONFIRMED всех типов, 0 новых, `complete:true`;
  exact-head check119883611286. На main `f5491216` полный inventory также 0/0.
- [Android 39795793709](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39795793709):
  attempt1/build119882737402 завершился до checkout и компиляции: загрузка
  закреплённого actions/setup-java с codeload.github.com трижды превысила 100 s.
  Cleanup119885713533 — PASS/`verified_absent`. Attempt2 закончился
  `startup_failure`; API вернул только пропущенный runtime119888683585.
  Это не результат компиляции или UI-проверки, причина attempt2 не установлена.

Подтверждённый успешный build119856511461 предыдущего `51510ac9`
использовал готовый tool-cache `Java_Temurin-Hotspot_jdk/17.0.20-101/x64`:
setup-java сообщил 17.0.20+101, а Gradle — Eclipse Adoptium 17.0.20.1.
`verify_cached_jdk.py` заменяет только загрузку setup-java в Windows job:
требует завершённый cache, проверяет путь, фактически запускает Java/javac
и допускает только JDK 17 x64 от Eclipse Adoptium. Различие vendor suffix
не считается ошибкой major version. Нет сетевой установки или смены сертификата;
нет обхода сборки, Sonar, Backend, cleanup или матрицы API37 / 16384 и 4096.
Linux job сохраняет штатный setup-java.

Локально: 860 CI-тестов PASS, 4 существующих пропуска, 1.152 s;
все 16 новых тестов cache discovery, process checks и экспорта окружения
выполнены. Для ограниченного локального Node 24 применены writable TMPDIR
и `NODE_OPTIONS=--test-isolation=none`, тесты и assertions не изменялись.
Проверка diff и ревью завершены. Запуск фактического JDK Windows остаётся
обязательным шагом нового CI, локальные fixtures его не подменяют.

Независимое ревью восстановления ввода не выявило новой регрессии:
hidden hide до suspension, readOnly, pending disabled restore, same-owner guard
и шесть cancellation cases сохранены. Результат позднего IME hide остаётся
неподтверждённым до полного runtime новых байтов. Локальные проверки скрипта
и итог нового CI фиксируются в PR #880; прежние результаты не переносятся
на новый SHA. APK, Timeweb и production channel не обновлены.

**Историческое согласование сервера `a6f2568a` с восстановлением IME, F01/F02/F16/F20/F22/F23, 22.10.2026:**
При подготовке `a6f2568a` объединены server `2560c8af` и app `8fe52f60`:
сохранены owner enrollment и серверные проверки; перенесены безопасная
диагностика IME и новый порядок восстановления видимого редактора.
App и отдельный driver совпадают с app-кандидатом; 13 серверных путей вне
README и реестра сохраняют содержимое `2560c8af`.

Локально объединённое дерево прошло 871 CI-тест (4 предусмотренных пропуска),
52 проверки инструментов и аудит 317 Python-файлов; diff check — PASS.
Backend-код и его тесты побайтово совпадают с `2560c8af`, поэтому полный
backend-набор повторно не выполнялся. Прежние 1515 тестов / 1481 подпроверка
ниже относятся к предыдущему дереву, а не к новому серверному head.

На момент этой локальной сверки server-head ещё требовал собственных
Backend CI и полного Sonar inventory; последующие результаты приведены в PR #887.
Результаты app `79cb04c1`, `51510ac9` и `c86b9190` ниже относятся только к указанным SHA.
App `8fe52f60` ещё требует полной API37-матрицы; исправление IME и готовность APK
не подтверждены. Новая VM, внешний TLS, реальный Telegram-вход и привязка
владельца также не подтверждены. APK и канал обновлений этим объединением
не публикуются; серверные проверки фиксируются в [PR #887](https://github.com/MishaGameHacking/omni-cio-gateway/pull/887).

**Упрощение теста отмены, F01/F16/F22, 22.10.2026:**
Кандидат `c86b9190b8e210464d79e6c34887f6d19942d370`:

- [Backend 39794038157](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39794038157),
  job119876825961 — 1467 tests / 1409 subtests PASS; итоговый job — failure
  из-за строгого Sonar gate.
- [Полный Sonar 39794027321](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39794027321),
  exact-head check119877617030: 1 OPEN/CONFIRMED finding, 1 новый,
  все типы, `complete:true`. `kotlin:S3776` в тесте отмены:
  Cognitive Complexity 27 при допустимых 15; issue `AaFj-IJq-Mhw8ApFNdwK`.
  Успешный статус самого диагностического workflow не означает чистый inventory.
- [Android 39794038166](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39794038166),
  build job119876936200 — подготовка runner завершилась ошибкой загрузки
  закреплённого actions/setup-java с codeload.github.com после трёх таймаутов.
  Компиляция, JUnit и runtime не выполнялись; это не новый результат эмулятора.
  Cleanup job119880771549 подтвердил `CI_PRIVATE_TRANSFER_CLEANUP=verified_absent`.

Только структура теста отмены изменена: два цикла сохраняют шесть сочетаний
visible/hidden × window/focus/frame; coroutineScope в отдельной suspend-функции
сохраняет отмену дочерней coroutine. Общий waitAt приостанавливается только
в выбранной точке; waiting.await, cancelAndJoin, общий timeout 5000 ms
и все три assertions сохранены. Безусловное ожидание frame больше не скрывает
пропуск раннего callback. Production, driver, gate и suppressions не менялись.
Независимое ревью — PASS. Локально: 844 CI-теста (4 предусмотренных пропуска),
Python-аудит 311 файлов и diff check — PASS. Локальный JUnit недоступен
из-за libjli.so; компиляция и снятие finding требуют exact-head CI.
Новый head ещё должен пройти Backend, полный Sonar 0/0 и обе полные
API37-матрицы на собственных байтах. APK не выдан; прежние проверки
не переносятся на новый head как готовый результат.

**Порядок восстановления фокуса и IME, F01/F16/F22, 22.10.2026:**
Диагностический head `51510ac9439a2173744a43e3d9a54590f325ffc5`:

- [Android 39788071851](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39788071851),
  build job119856511461 — все APK, Kotlin/JUnit, lint и 842 CI-теста
  (3 предусмотренных platform skips) PASS; Gradle 9m 35s.
- [Backend 39788071850](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39788071850),
  job119856399776 — 1467 tests / 1409 subtests PASS, 16.96 s.
- [Полный Sonar 39788059724](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39788059724),
  job119856356486 — 0 OPEN/CONFIRMED всех типов, 0 новых, `complete:true`
  для точного head; check119857339900.
- Runtime job119863114964 — FAIL на risk/ready/font100 при повороте диалога.
  Текст, focus и caret 0:0 сохранены, IME исчезает. API37 / измеренные 16384:
  clean install и upgrade PASS, полный UI — нет; 4096 не запущен.
  APK SHA-256 `24d65e49f7c22087a87f2d2309839c8673d92a095f62b3688b550e622833eeb0`,
  29853394 bytes. Rotation PNG проверен по байтам и визуально:
  `6f1ba3e0942bdff0dfc9132b18387938391c0847c4db2028a0188df7f8e9a235`,
  148452 bytes. Cleanup job119868894456 — `verified_absent`.
  Aggregate119868971798 и authoritative119869017621 корректно FAIL; APK не выдан.

Новая диагностика разобрала последние 120 UID-строк без rejection;
platform capture прочитал 427 строк, выделил 248 связанных записей и вывел
последние 120. Причинный интервал сохранён. Native observations: 44 samples,
3 IME-positive, 4 state transitions без обрезания. Первый positive ещё portrait;
следующие два уже landscape, но frame не атомарен: timestamps охватывают
чтение окон, а editor сериализуется позже. Последующие 41 sample и post-timeout
показывают прежний exact/focused editor с отсутствующей IME.

В текущем risk-сегменте editor4/attempt1 постоянно enabled; нет отмены,
ожидания disabled или новой попытки. Restore-start — 13:57:07.485 UTC,
focus — 08.482, explicit request-show — 08.594, finished — 08.595.
Оба признака IME true в 09.001 и false в 09.493. Driver до отказа только
читает frames; portrait cleanup ещё не начался. Server hide128 от 07.951
завершается в 08.910; show82 от 08.517 — onShown в 08.930. Show82 предшествует
explicit restore и не приписывается ему. Поздний IME hide88 с причиной
`HIDE_SOFT_INPUT_EXTRACT_INPUT_CHANGED` (08.883) имеет onHidden в 09.501.

В [Android 17 r1 InputMethodService](https://android.googlesource.com/platform/frameworks/base/+/android-17.0.0_r1/core/java/android/inputmethodservice/InputMethodService.java)
этот default callback скрывает IME при `EditorInfo.inputType == TYPE_NULL`.
[InputMethodManager](https://android.googlesource.com/platform/frameworks/base/+/android-17.0.0_r1/core/java/android/view/inputmethod/InputMethodManager.java)
может передать исходный EditorInfo даже при null InputConnection. Штатный
Decimal editor в точном Compose 1.11.4 получает тип 0x2002 и IME_FLAG_NO_FULLSCREEN.
Промежуточная цель без готового редактора согласуется с кодом и событиями,
но фактический EditorInfo/window этого callback не записан. AOSP r1 также
не объявляется доказанно тождественным конкретной сборке эмулятора.

Изменён порядок только для восстановления видимой IME доступного writable
editor: requestFocus/awaitFocus предшествуют RESUMED/window focus/frame/
bringIntoView; следующий frame и единственный explicit show остаются после
готовности окна. Такой порядок соответствует [официальному руководству Android](https://developer.android.com/develop/ui/views/touch-and-input/keyboard-input/visibility)
и начинает подготовку Compose input session раньше прежнего ожидания окна.
Готовность platform InputConnection до конкретного события WM этим не доказана.
Для hidden intent и readOnly сохранён прежний порядок целиком; same-batch hide
не переносится за suspend. Disabled restore остаётся pending, cancellation
распространяется, отказ focus не считается успехом. Повторы, новые таймауты,
input-session перехватчики и изменения driver/gate не добавлены.

Безопасный ImeTracker allowlist дополнен точными Android 17 именами
`HIDE_CLOSE_CURRENT_SESSION` и `PHASE_SERVER_ALREADY_VISIBLE`; прежние значения
сохранены, похожие неизвестные строки остаются `unrecognized`.
Локально: 844 CI-теста, 4 предусмотренных пропуска, 1.077 s — PASS;
Python-аудит 311 файлов и diff check — PASS. 29 ImeTracker tests включают
оба новых имени и сохранение безопасной проекции; 52 focused native/rotation/
typing tests также прошли. Независимое ревью порядка, hidden/readOnly,
disabled/lazy guards, cancellation и отсутствия изменений driver завершено.
Шесть существующих JVM-тестов расширены: focus перед новым window wait,
hidden intent до первого flush и cancellation в window/focus/frame.
Локально они не выполнены из-за ошибки Java libjli.so; CI JUnit обязателен.
Новый кандидат ещё требует сборки, полного Sonar/Backend и обеих полных
API37-матриц на собственных байтах; его исправление не объявлено подтверждённым
runtime. Результат фиксируется в [PR #880](https://github.com/MishaGameHacking/omni-cio-gateway/pull/880).

**Повторный сбой IME и исправление диагностики, F01/F16/F22, 22.10.2026:**
Кандидат `79cb04c1f1db9b11603300f808b40a3178608d4f`:

- [Android 39781504544](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39781504544):
  все APK, Kotlin/JUnit, lintDebug/lintPreview — PASS за 9m 5s;
  828 CI tests, 3 предусмотренных платформенных пропуска.
- [Backend 39781504548](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39781504548):
  1467 tests / 1409 subtests — PASS.
- [Полный Sonar 39781495961](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39781495961):
  0 OPEN/CONFIRMED всех типов, 0 новых, `complete:true` для точного head.
- Runtime на API37 / измеренных 16384 прошёл четыре risk/font100 случая
  и прежний отказ impact fold в assistant/ready. Проверенный impact PNG:
  `d5057d939cf70f3e9591d88ce3bb097eddd2487107fbb1ecef08578ce933606d`.
  Затем поворот несохранённого вопроса завершился отказом: текст `UIprobe`,
  фокус и caret 5:5 сохранились, IME скрылась после видимого состояния.
  Проверенный failure PNG:
  `15d29c256cbca1751079e256ed4b27887d577b179991ac5846deef746dda5f2c`.
- APK SHA-256 `9f7d1943b41e99f309aac7f80d64856949b9f96ebb7cd41478c4486b41bcf796`,
  29853394 bytes. Установка и обновление прошли, полная UI-матрица 16384 — нет;
  4096 не запущен. Cleanup job119845412597: `verified_absent`.
  Итоговый Android gate — failure, APK не выдан.

Точная временная сверка отделила старые hide от текущего поворота:
в 13:11:43.022 UTC приложение запросило show, в 13:11:43.208 оба показателя
IME были true, в 13:11:43.749 — false при сохранённом фокусе. В этом интервале
нет app restore `request-hide`. Более поздний hide в 13:11:54.886 относится
к возврату в портрет после отказа. Stale Compose-insets временно меняют
сохранённое намерение, но оно успевает стать true до первого скрытия;
причинность этой гонки не доказана. Единственный IME-visible native sample
вытеснен из прежнего tail; он мог относиться ещё к исходной ориентации.

[Android 17](https://developer.android.com/about/versions/17/behavior-changes-all)
требует явного восстановления IME после configuration recreation; приложение
уже выполняет такой запрос. В [AOSP logprint](https://android.googlesource.com/platform/system/logging/+/refs/heads/main/liblog/logprint.cpp)
UTC включает zone output `+0000`: прежний парсер отбрасывал этот формат.
Исправлена строгая поддержка UTC suffix; добавлены безопасные счётчики чтения,
принятия и отбрасывания. Второе чтение main/system допускает в вывод только
события с точной меткой пакета кандидата либо подтверждённым в его UID request;
сырой текст, component и request token не публикуются. Непривязанные системные
события остаются за пределами доказательства. Первые IME-visible и rotated
кадры сохраняются отдельно от bounded transition history. DEBUG trace
различает экземпляр редактора, попытку, disabled wait и cancellation.
Действия ввода, таймауты, stable-frame predicates и исходный failure сохранены.
Следующий кандидат служит диагностике, без маркера выдачи приватного APK;
один успешный повтор не объясняет непостоянное исчезновение клавиатуры.

Локальная проверка диагностического дерева: 842 CI-теста, 4 предусмотренных
пропуска, 1.422 s — PASS; Python-аудит 311 файлов — PASS. В их составе
27 ImeTracker, 29 native evidence, 18 hidden/visible rotation и 5 typing tests.
Независимое ревью DEBUG trace, parser privacy/scope и неизменности input/gate
завершено; diff check чистый. Это не результат нового Android runtime.

**Историческая сверка сервера и чата, F01/F16/F22, 22.10.2026:**
При подготовке `2560c8af` объединены server PR #887 (`07d4a4ed`) с app `79cb04c1`:
сохранены owner enrollment, серверные проверки и все изменения чата.
Backend CI: 1467 тестов / 1409 подпроверок; полный Sonar inventory:
0 OPEN/CONFIRMED, 0 новых, `complete:true` — это результаты именно app `79cb04c1`.
На момент той сверки Android-проверка app `79cb04c1` ещё выполнялась;
её последующий отказ отражён выше. Полная API37-матрица не подтверждена.
Локально объединённое дерево прошло 855 CI-тестов (4 предусмотренных пропуска),
52 проверки инструментов и 1515 backend-тестов / 1481 подпроверку;
аудит 317 Python-файлов и health/OpenAPI smoke — PASS.
Эти локальные результаты относятся к предыдущей серверной интеграции
и не переносятся на следующий head без собственных проверок его SHA.
Новая VM, внешний TLS, реальный Telegram-вход и привязка владельца не подтверждены.
История и ограничения ниже сохраняются; APK и канал обновлений этим согласованием
не публикуются. Проверки сервера — в [PR #887](https://github.com/MishaGameHacking/omni-cio-gateway/pull/887).

**Чат: переходы раскрытия, последнее сообщение и восстановление, F01/F16/F22, 22.10.2026:**
`5543f89f` прошёл сборку всех APK, lint/JUnit, Backend CI и полный Sonar
с нулём OPEN/CONFIRMED. Runtime `39768001717` подтвердил четыре сценария риска
при font100, затем остановился в assistant/ready: после закрытия блока
«Публикация, компания и мои позиции» driver не достиг «Возможный канал 1».
PNG SHA-256 `20be6859b01cf14c2b4f50554124b790f7505a8c55e9b87b812e8795ea7de12b`
проверен по байтам и визуально: список находится в конце сообщения, IME нет.
Промежуточный кадр сразу после закрытия не сохранён; исчезновение кнопки
или конкретная гонка переукладки этим снимком не доказаны. Профиль 4096
и оставшиеся сценарии не выполнены. Cleanup подтвердил `verified_absent`;
APK не выдан и Timeweb channel не менялся.

Исправлен подтверждённый дефект порядка действий: driver больше не начинает
прокрутку изменённого блока до наблюдения его нового нативного состояния.
Метки basis/channel перенесены с внешних Column на реальные заголовочные кнопки.
После одного нажатия требуются ожидаемое состояние и три свежих согласованных
кадра с доступной геометрией. Нажатия не повторяются, ограничение 12 секунд,
видимость, точность целей, текст источников и весь runtime-контракт сохранены.
Проверены [точные официальные исходники Compose UI 1.11.4](https://dl.google.com/dl/android/maven2/androidx/compose/ui/ui-android/1.11.4/ui-android-1.11.4-sources.jar): эта реализация
accessibility не читает аргумент частичной прокрутки, поэтому неподтверждённая
подмена размера страницы в driver не применяется.

Отдельно исправлена автопрокрутка к предпоследнему сообщению: индекс последнего
сообщения теперь учитывает два служебных элемента и кнопку ранней истории.
Наблюдение за активным заданием поднято на уровень экрана чата, за пределы
LazyColumn: карточка может уйти из композиции, не прерывая получение результата
и снятие блокировки ввода. Карточка получает уже существующее состояние задания;
второго polling-цикла при её появлении нет. Сохраняются ограничения foreground,
пользовательского сеанса, отмена и явный повтор только с разрешения сервера.
Активное повторное задание сохраняется при повороте и обновлении токена;
ответы прежнего сеанса отменяются. Удаление локальной контрольной записи
завершается до уведомления об окончании; ошибка удаления оставляет доступное
повторное действие. Параллельное закрытие и polling не уведомляют дважды.
Восстановление потерянного ответа проверяется по сохранённому user message
внутри истории и очищенному доступному native editor. Счётчики транспорта
продолжают требовать один POST и один GET с тем же UUID; оставшийся черновик,
похожий текст assistant или один успешный GET не подтверждают завершение UI.

Локально: 828 CI-тестов, 0 отказов, 4 предусмотренных пропуска; отдельно
12 fold и 18 recovery-тестов прошли. Python-аудит 311 файлов и diff check — PASS.
Для локального Node 24 использованы `NODE_OPTIONS=--test-isolation=none`
и доступный TMPDIR: все 34 Sonar subtests и 12 private-publisher subtests
выполнены, assertions и CI workflows не менялись. Независимое ревью контроллера
подтвердило cancellation, retry identity, cleanup и единственное уведомление.

Новый кандидат требует полного CI и обеих API37-матриц на своих байтах.
Текущие проверки и фактический итог фиксируются в [PR #880](https://github.com/MishaGameHacking/omni-cio-gateway/pull/880);
локальные регрессии не заменяют Android runtime или проверку телефона владельца.

**Диагностика поворота, редактор стратегии и расчёт, F01/F07/F17/F22, 22.10.2026:**
Проверка следующих бизнес-сценариев выявила несовпадение точной подписи плана:
fixture возвращает «СИНТЕТИЧЕСКИЙ РАСЧЁТ · Покупка · Синтетическая акция»,
а driver искал отсутствующую сокращённую строку. Теперь он требует полное
название результата, включая направление и инструмент. Точный поиск,
исходная последовательность действий и отдельная проверка 5 единиц сохранены.

Редактор стратегии подключён к существующему compact IME layout: в коротком
окне шапка уступает высоту полю, вкладки временно скрываются, вертикальный
contentPadding списка становится нулевым. После закрытия IME вкладки возвращаются.
Column, LazyColumn, порядок items, выбранная вкладка, черновик и вызовы нативных
редакторов остаются на прежних местах. Второй scroll-контейнер не добавлен.
Это устраняет фиксированные затраты высоты при геометрии, уже обнаруженной
в чате; отдельный runtime-кадр стратегии ещё требуется.

`0dc509df` прошёл сборку всех APK, compileDebugUnitTestKotlin/testDebugUnitTest
и lint за 8m57s, 789 CI-тестов (3 платформенных пропуска), Backend 1467/1409
и полный Sonar inventory: 0 OPEN/CONFIRMED всех типов, 0 новых, `complete:true`.
Но [runtime 39762602349](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39762602349)
на API37 / измеренных 16384 остановился на risk/ready/font100: после поворота
число, фокус и точный курсор сохранились, а клавиатура появилась и затем скрылась.
PNG `f5ba3c6023197638ebed0864cc17cd974096d967934f729547a76500987b9ae6`
проверен по байтам и визуально. Чат и профиль 4096 этот запуск не проверил.
Позднее скрытие IME пока не объяснено; его причинная связь с compact layout
не установлена. APK не опубликован; cleanup подтвердил `verified_absent`.

В точку отказа, до восстановления ориентации, добавлен отдельный захват ImeTracker
только для UID debug-кандидата и фиксированного тега. Строгая bounded-проекция
сохраняет технические operation/origin/reason/phase и время; текст, component,
токены запросов и произвольные поля не выводятся. Неизвестные enum заменяются
фиксированным `unrecognized`. Ошибка любого диагностического чтения
не подменяет исходный отказ. Успешный путь не запрашивает ImeTracker.
Это частичная трасса app UID, без событий system_server и процесса клавиатуры.
Существующий DEBUG trace дополнен пассивными `viewIsTextEditor` и `wallClockMs`:
готовность Compose не объявляется доказательством активного InputConnection.
Новых show/hide, повторов ввода, ожиданий или ослаблений gate нет.

Независимые ревью layout, точного названия плана, пассивного DEBUG trace
и безопасной интеграции ImeTracker прошли. Итоговый локальный набор:
810 CI-тестов, 4 предусмотренных пропуска, 1.199 s; отдельный запуск 5 тестов
native typing также прошёл. Добавлены 18 hostile-format/privacy регрессий
парсера и 3 проверки независимости диагностических чтений. Unicode UID,
произвольные поля и неизвестные enum не раскрываются; original gate и действия
ввода сохранены. Это не результат Android runtime: обе полные API37-матрицы
нового кандидата ещё обязательны. Проверенный APK пока не выдан.

**Согласование тестового контракта чата, F01/F16/F22, 22.10.2026:**
Параллельное ревью `7539f3c9` обнаружило гарантированный отказ следующего
сценария: рабочий UI выбирает `auto`, а debug fixture допускал только ручные
tier и не выдавал обязательные поля маршрута и стоимости. Действующий backend
уже поддерживает этот контракт. Исправлен только синтетический транспорт:
`auto` получает конкретный `selected_tier`, целочисленный предел расходов,
64-символьный hex route и явные synthetic metadata.
Отправка связана с неизменными thread/text/context/requested tier и точными
cost/route; UUID должен быть каноническим, premium требует Boolean-подтверждения.
Accepted job, lookup по request ID и polling возвращают одно сохранённое задание
с актуальными job_id/request_id/kind/state. Второй POST в сценарии потерянного
ответа по-прежнему отвергается; recovery не создаёт нового платного запроса.

Добавлены 15 JUnit-регрессий используемого debug helper через неизменённый
production ChatRouteQuote; они входят в testDebug и требуют запуска CI.
Локально прошли 789 CI-тестов (4 предусмотренных пропуска) и независимое ревью;
это не заменяет компиляцию новых JUnit и фактический Android runtime.
Компактный layout, продуктовые guards, действия и критерии приёмки сохранены.
Предыдущий `7539f3c9` прошёл build/lint/JUnit за 8m58s, 789 CI-тестов
(3 платформенных пропуска), Backend 1467/1409 и полный Sonar inventory
с 0 OPEN/CONFIRMED всех типов и 0 новых. Его незавершённый runtime не проверяет
этот новый контракт; обе полные API37-матрицы следующего head обязательны.
Проверенный APK пока не выдан.

**Поле чата в коротком окне, F01/F16/F22, 22.10.2026:**
`81e36247` прошёл build/lint, JUnit (включая 6 регрессий очереди IME),
789 CI-тестов (3 платформенных пропуска), 1467 backend-тестов / 1409 подпроверок
и полный Sonar inventory: 0 OPEN/CONFIRMED всех типов, 0 новых; main также чистая.
[Runtime 39754937746](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39754937746)
на API37 / измеренных 16384 подтвердил установку, совместимое обновление,
3D-блок, цели при font100/font200, устойчивую видимую и скрытую IME риска
в обоих направлениях поворота и раскрытие источника ассистента при font100.
PNG скрытой IME `178035817bbc72a350bafa53dd36b02543c59427eaf1eb2d6467bc8adf5280e2`
и источника `eb2deb8d47ed985b6ea96a44227951ec4a0c6eee763a151547ccfc32ba2e470d`
проверены по байтам и визуально; прежние два отказа в этом сценарии устранены.

Следующий отказ — chat/ready/font100 после поворота: окно 640×320, IME с y=106,
51 наблюдение видимой клавиатуры, но доступных native editor nodes нет.
Снимок `e2ea829e3f39e706330077059c8715c06ad66eefb5b8b4596e348dd6bd2b556d`
показывает 99 px тестовой плашки и только 7 px рабочей области над клавиатурой.
Фиксированная шапка и отступы также ограничивают production-чат без плашки.
Это отказ размещения; trace подтверждает восстановление focus/IME, но не даёт
основания считать невидимый редактор пригодным для ввода.

Чат получает адаптивную компоновку по фактической высоте после safeDrawing:
при IME и высоте меньше 240 dp шапка уступает место редактору, а доступная
3D-кнопка «Назад» располагается сбоку. Внешние отступы composer
убраны только в этом режиме; нативное поле и его прокрутка остаются прежними.
Тестовое предупреждение сохраняет явное обозначение синтетики и все счётчики;
стабильные слоты меняют геометрию без пересоздания workspace/composer.
Локально прошли 789 CI-тестов (4 предусмотренных пропуска); независимое
ревью проверило узкое окно, стабильность композиции и потребление insets.
Восстановление IME, текст/каретка, font200, действия и 12-секундный предел
не ослаблены. Android layout ещё обязан пройти полную API37-матрицу обоих
размеров страницы. Профиль 4096 в `81e36247` не выполнялся; APK не выдан.
Временная передача удалена: job `119753736381`, `verified_absent`.

**Исправление восстановления скрытой IME, F01/F16/F22, 22.10.2026:**
`fab99d7c` прошёл build/lint, 788 CI-тестов (3 платформенных пропуска),
1467 backend-тестов / 1409 подпроверок и полную Sonar-инвентаризацию:
0 OPEN/CONFIRMED всех типов и 0 новых замечаний; main также чистая.
[Runtime 39750128597](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39750128597)
на API37 с измеренными 16384 подтвердил установку, обновление, запуск,
полный 3D-блок, контекст сессии, приватность баланса и цели при font100/font200.
В risk/ready/font100 видимая IME прошла три свежих согласованных наблюдения
за одну секунду, проверку после снимка и возврат в portrait. PNG
`3ff2299d1a87256a92692869e3e09d83d69c63da912137e3e6f3f76291f3c4b9`
действительно показывает цифровую клавиатуру.

Новый цикл после её закрытия обнаружил продуктовый отказ: поворот вновь
открыл IME. Текст `5`, фокус и каретка `(0,0)` сохранились; снимок до cleanup
`44976750cc1c07a98a489a8ec82372d24e047ea983d46024f42b9635312abf72`
подтвердил открытые клавиши, поэтому это не только ошибка accessibility.
Проверка сохранила исходный отказ `Rotation reopened a deliberately dismissed
input-method window`. Профиль 4096 не выполнялся. До исправленного раскрытия
источника assistant этот запуск не дошёл; его runtime ещё не подтверждён.

Точные официальные исходники Compose 1.11.4 показывают, что новая legacy
input-session ставит implicit show в очередь при requestFocus; прежний helper
ожидал кадр до hide. Теперь сохранённое намерение фиксируется до фокуса:
после успешного requestFocus скрытие ставится в тот же пакет до первого
приостанавливающего ожидания. Видимая ветка по-прежнему ждёт фокус/кадр до show.
Отказ фокуса не изменяет клавиатуру другого редактора и не завершает pending
restore; отмена, временный disabled и readOnly сохраняют свои ограничения.
Это исправление подтверждённого порядка команд; ошибочно сохранённое true
не объявляется исключённым: ранние события предыдущей трассы были потеряны.

Сборщик больше не обрезает общий main logcat до фильтра UID/тега. Вывод всё
так же ограничен точным UID приложения, AnalystEditorRestore, разрешёнными
полями и 40 записями; тексты полей, токены и owner ID не записываются.
Локально прошли 789 CI-тестов (4 пропуска по условиям окружения). Добавлены
6 JUnit-регрессий очереди, отказа фокуса, readOnly и отмены; их запуск через
существующий :app:testDebugUnitTest ещё должен подтвердить CI нового head.
Действия ввода, точность текста/каретки, обе IME-ветки и бюджет 12 секунд
не ослаблены. Временная передача fab99d7c удалена: job `119738014482`,
`CI_PRIVATE_TRANSFER_CLEANUP=verified_absent`.
Проверенного APK для скачивания пока нет. Новый head обязан пройти обе
полные API37-матрицы, Backend/Sonar, подпись и итоговую очистку; только затем
разрешено сохранить приватный draft для владельца.

**Готовность нативных нажатий, F01/F22, 22.10.2026:**
`76eb125d` прошёл build/lint, 704 CI-теста (3 платформенных пропуска),
1467 backend-тестов / 1409 подпроверок и Sonar с 0 открытых замечаний.
Runtime `39731093048` остановился на переключении LIVE → SUBDUED:
снимок `757261c43aaaa30c418113d71a8e7d063c4cfba9` показывает прежний режим.
После съёмки формы список прокручивался к переключателю, а общий label-tap
сразу использовал первый видимый текст без ожидания завершения перемещения.
Путь MotionLevel в приложении проверен; продуктовый дефект этого перехода
не подтверждён. Теперь label-tap выбирает ближайшее нативное действие,
проверяет его доступность по всей цепочке предков и видимую область с учётом
реальных scroll-контейнеров. Три свежих одинаковых наблюдения окна, дисплея
и геометрии обязательны перед одним координатным нажатием; вложенные кнопки
не подменяют команду внешней карточки. Прежний бюджет 12 секунд сохранён.
Локально прошли 750 CI-тестов (3 платформенных пропуска), включая 46 новых
проверок готовности, неоднозначности и единственного реального нажатия.
Проверки SUBDUED/OFF, остановки кадров, текста, фокуса, IME и результата
действий не ослаблены. Очистка временного APK подтверждена `verified_absent`
(job `119670773879`); полная API37-матрица нового head ещё обязательна.
Проверенного APK для скачивания пока нет.

**Одноразовая привязка владельца, F02/F20/F23, 22.10.2026:**
Подготовлен [owner enrollment для новой установки](../deploy/OWNER_TIMEWEB.md).
После проверки подписанного Telegram OIDC-токена администратор подтверждает
нужную личность в приватном TTY командой `BIND <точный sub>`.
До подтверждения не создаются backend env, Fernet-ключ, unit приложения или БД.
Owner JSON создаётся атомарно с владельцем root и правами `0600`, без замены
файлов и следования symlink; повторный запуск после частичной установки отклоняется.
Независимое ревью подтвердило защиту Caddy drop-in и cleanup с начала установки
пакетов, обработку SIGTERM/SIGHUP и сохранение исходной ошибки при сбое cleanup.

JWT-заголовок проверяется после подписи и обязательных claims; проверка ограничена
64 доверенными RSA-ключами и связывает уникальный `kid` с проверившим подпись ключом.
Каталог Caddy теперь доступен только root и служебной группе: `root:caddy 0750`,
оба Caddyfile — `0640`; backend env и owner JSON сохраняют права root `0600`.
Отдельный каталог systemd drop-in ограничен правами root `0700`: его читает
системный manager, самому процессу Caddy этот каталог не требуется.
Сложные функции инвентаризации и установки разделены без изменения отказов.

Локально прошли 1515 backend-тестов / 1481 подпроверка и 816 CI-тестов
(4 предусмотренных локальных пропуска), включая 27 тестов сетевой инвентаризации.
GitHub на `a55d5c2c` подтвердил [1515 тестов / 1481 подпроверку и exact-head
Sonar gate](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39763435359).
[Полный Sonar inventory](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39763426383)
показал 0 OPEN/CONFIRMED всех типов, 0 новых и `complete:true`; main также чистая.
Все 27 прежних замечаний устранены. Android-код согласован с `5543f89f`, включая
компактный редактор стратегии, точное название плана и пассивную диагностику IME.
Прежние проверки сервера не приписываются новому объединённому head.
Проверки объединённого head фиксируются отдельно в [PR 887](https://github.com/MishaGameHacking/omni-cio-gateway/pull/887).
Настоящий Caddy 2.6.2 успешно выполнил офлайн `caddy adapt`; текст конфигурации
не изменился, выпуск сертификата и внешний HTTPS ещё не проверены.

GET-инвентаризация [run `39759477768`](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39759477768)
на `a1825d17` от 22.10.2026 12:58 МСК не обнаружила VM, AI-агентов, плавающих IP и доменов
в области видимости токена. Это ограниченная инвентаризация, без проверки
всего аккаунта или биллинга; ресурсы не менялись. Новая VM не установлена,
реальный Telegram-вход владельца и его привязка ещё не выполнены.

**Подтверждение удаления цели, F01/F22, 22.10.2026:**
`577cf9bd` прошёл build/lint, 704 CI-теста (3 платформенных пропуска),
1467 backend-тестов / 1409 подпроверок и Sonar с 0 открытых замечаний.
Runtime `39728571918` подтвердил 3D-блок, контекст сессии, приватность баланса,
ввод и восстановление цели, но остановился при удалении цели со шрифтом 200%:
снимок `cb85bea4c5bba67b6ff6ef7afcd3605b4f0e78c3` показывает открытый диалог.
Тест нажимал первый видимый текст без ожидания геометрии всей кнопки. Теперь
`goal-delete-confirm` использует существующую проверку видимой области и
трёх одинаковых свежих прямоугольников перед одним настоящим нажатием.
Проверка фактического удаления и единственного создания остаётся обязательной;
при отказе сохраняются только счётчики fixture и ID окна. До сценария чата
этот запуск не дошёл, поэтому исправление его фокуса ещё ожидает runtime.
Полная API37-матрица нового head обязательна; проверенного APK пока нет.

**Timeweb, проверка сети 22.10.2026 08:49 МСК:** отдельная ветка
`codex/owner-enrollment-2026-10-22`, коммит `9eb7dcf4`, run `39730159289`
подтвердили отсутствие видимых VM, агентов, плавающих IP и доменов, включая
отвязанные IPv4. Это полнота в области видимости токена, а не всего аккаунта.
24 теста нового GET-only inventory прошли; VM, DNS, TLS и ресурсы не менялись.
Подготовка первичной подтверждённой owner-привязки ведётся в этой отдельной ветке.

**Восстановление чата после поворота, F01/F16/F22, 22.10.2026:**
`606d0dd` прошёл build/lint, 1467 backend-тестов / 1409 подпроверок и Sonar
с 0 открытых замечаний. Runtime `39725964567` подтвердил полный ввод `native3d`,
3D-блок, цели при обычном и 200% шрифте и сравнение сценариев. Далее чат сохранил
текст `UIprobe` и каретку `(5,5)`, но потерял фокус/IME после поворота
(снимок `5c13b05766221304eb98792bdd69315d5a8237c0`). При пересоздании Activity
чтение сохранённых запросов временно выставляет `enabled=false`; одноразовый
focus-effect преждевременно отмечал восстановление выполненным. Теперь effect
следит за доступностью поля и сохраняет прежнего владельца до завершения
восстановления фокуса/IME. Проверки точного текста, каретки, реальной IME и
поворота не изменены; полная API37-матрица нового head ещё обязательна.
Проверенного APK для выдачи пока нет.

**Timeweb, свежая проверка 22.10.2026 08:15 МСК:** job `119652786149`
подтвердил отсутствие VM и AI-агентов в области видимости токена, наличие
Telegram client ID/secret и отсутствие готовой owner-привязки. Тарифы
6767/6769: 1 CPU / 1 ГБ / 15 ГБ за 350 ₽/мес; с IPv4 по публичному прайсу
200 ₽/мес ориентир 550 ₽/мес до backup и AI. Доступность заказа и отдельные
отвязанные IP не проверены; ресурсы не менялись. Для новой пустой установки
Fernet-ключ генерируется установщиком в приватном env. Первичный проверенный
OIDC-вход до запуска owner backend ещё требует отдельного bootstrap-процесса,
нового HTTPS callback и регистрации точного redirect в BotFather.

**Продолжение 22.10.2026, F01/F02/F20/F22/F23:** предыдущий runtime
`39679237400` прошёл сборку и установку/обновление API37/16КБ, но остановился
на вводе `native3d`: снимок `33132a8a49e620a8657a208a877faca816ecfc99`
показывает только `native3`. Проверка теперь наблюдает готовую IME и точную
каретку перед однократным вводом; полный текст, фокус и конечная каретка
остаются обязательными. При отказе выводится состояние окна без текста поля.
Локально: 704 CI-теста, 3 предусмотренных платформенных пропуска; полная
API37-матрица нового коммита ещё обязательна. Новый APK пока не выдан.

В установщике Timeweb исправлены два блокера: обязательный pinned CA брокера
теперь копируется с вложенным путём и проверяется до установки; публичный код,
venv и Caddyfile доступны сервисным пользователям даже при root `umask 077`.
Конфигурация с секретами остаётся `0600`. Все 16 тестов установщика прошли,
включая фактическую загрузку сертификата и права файлов. Это локальная
проверка подготовки; VM ещё не установлена, проверенный OIDC `sub` владельца
и новая серверная конфигурация по-прежнему необходимы.

**Сохранение цели при шрифте 200%, F01/F22, 21.10.2026:** `ba0eaaa`
прошёл build/lint, 1463 backend-теста (1406 subtests), полную выгрузку Sonar
с 0 открытых замечаний и весь 3D-блок API37/16КБ. Цель при обычном шрифте
прошла ввод, поворот, повтор запроса и удаление. При 200% после прокрутки
тест нажал текст по ещё не устоявшимся координатам: снимок
`7e0676f045dbbcad6594b507d4d792799fa8723a` показывает исходную кнопку сохранения.
Сохранение и повтор теперь выбирают `goal-submit`, требуют видимую область
не меньше 48×48 и одинаковые координаты в трёх свежих кадрах. Проверки
блокировки полей, сохранения при повороте и единственного создания оставлены.
Полная матрица нового коммита ещё обязательна. Временный APK удалён
с `verified_absent` (job `119494568072`); APK для скачивания пока не подтверждён.

**Проверка 3D-окна при шрифте 200%, F01/F22, 21.10.2026:** `e059bd1`
прошёл build/lint, 1463 backend-теста (1406 subtests) и полную выгрузку Sonar
с 0 открытых замечаний. API37/16КБ подтвердил подпись, установку/обновление,
120 шагов прокрутки и поворот. Затем тест отправил scroll основному списку
во время открытия modal; строгий driver отклонил исчезнувший список.
Снимок `fb8dcb09fa17b31daacb7ef92eafcb43219180ba` показывает готовый диалог
и доступную кнопку. Сценарий теперь ожидает окно и кнопку, проверяет две
3D-поверхности, закрывает видимую кнопку и проверяет возврат к одной поверхности.
Также добавлены ожидания открытия редактора плана и смены native-окна
уведомления; отметка прочтения ожидается после закрытия и обновления данных.
Матрица не сокращена; полный runtime нового коммита ещё обязателен.
Временный APK удалён с `verified_absent`; новый APK пока не выдан.

**Качество 3D-ветки, F01/F16/F22, 21.10.2026:** после включения чистой
main анализ `15c4ce9` выявил четыре S3776 в AI-клиенте, инвестиционном профиле,
списке позиций и экране рынков. Выделены проверка завершённости ответа, действия
сохранения, фильтрация/группировка/итоги позиций и карточка рыночной группы.
Порядок учёта платного ответа, отмены, пороги, подписи, выбор и native/3D-компоненты
сохранены. Локальные 699 CI-проверок прошли (3 платформенных пропуска);
новый Backend/Sonar и полный Android runtime ещё обязательны, APK не выдан.

**Ввод ассистента, F01/F16/F22, 21.10.2026:** проверка `39660627956`
прошла сборку, установку/обновление API37/16КБ, spatial, цели и сравнение
сценариев, затем обнаружила скрытое клавиатурой поле вопроса
(снимок `2d779e5e69fe4e6d213fa0a328af449686bec688`). Для основного и тестового
Activity задан `adjustResize`, блок ввода получил прокрутку в доступной высоте.
Подзаголовок сворачивается при открытой IME, оставляя место вводу при повороте
и увеличенном шрифте; после закрытия клавиатуры он возвращается.
3D-поверхности и нативный редактор сохранены. Тест ожидает видимый фокус и IME
до набора; точные текст, курсор и поворот остаются обязательными. Локальные
699 проверок успешны (3 платформенных пропуска); полный runtime новой версии
ещё не пройден. Приватный APK этого неуспешного запуска не сохранялся,
временные файлы удалены с подтверждением `verified_absent`.

**Проверка действия «Отложить», 21.10.2026:** runtime main `39657211169`
на API35 остановился после нажатия: диалог не открылся. Тест использовал
координаты текстового узла без ожидания устойчивого положения кнопки
(снимок `eedd29c336037570ded818b0ecd68902ead08082`). Тест теперь выбирает кнопку
конкретного действия по resource ID, требует видимую область не меньше 48×48
и одинаковые координаты в трёх свежих кадрах. Проверка открытия диалога, выбора
причины и итоговой отметки сохранена. Исправление применяется к main и 3D-ветке;
полный runtime нового коммита ещё обязателен, APK не выдан.

**Адрес сервера, F02/F20/F23:** обращения к удалённой VM остановлены в единой
точке создания HTTPS-соединения. Backend и updater используют один host;
до подтверждения новой установки вход и синхронизация закрыты с понятным
сообщением. Сессии и локальные данные не удаляются. Это подготовка безопасного
APK, а не объявление сервера установленным. Новые JVM-проверки должны пройти CI на окончательном коммите.

**Main исправлена, F07/F22/F23, 21.10.2026:** PR #885 и #886 слиты;
актуальная основа — `f54912165127bfab42673743cd141d635e20881f`.
Android `39666930293` подтвердил build/lint, установку/обновление API35/36,
полный UI, font200, очистку и V10 gate. Backend `39666930297`: 824 теста.
Отдельная проверка уже слитой main (`119464627939`) и полная выгрузка
`119463989492` подтвердили 0 открытых/подтверждённых, новых и принятых замечаний.
Сбор экспозиций вынесен из `_critical_risk` без изменения валют и порогов.
Эта основа включена в 3D-ветку; её собственная полная API37-матрица ещё обязательна.

**Текущий runtime `80d085e`, 21.10.2026:** run `39638175658` прошёл сборку,
установку/обновление API37/16КБ, весь spatial renderer, session context, privacy
и цели при font100/font200. Точная привязка risk checklist к созданному шагу
устранила прежний отказ; поворот редактора сценария также прошёл с IME/focus/caret.
Следующий отказ: тест читал marker Activity, скрытый открытым modal dialog,
до нажатия «Сравнить сценарии». Снимок `f18f1f2e8699b03d191993c60d91b38496301e2b`
подтверждает открытый диалог. Маркер теперь читается до открытия и после
закрытия; отдельный счётчик реального transport требует ровно один compare POST.
Точные значения A/B, фокус/IME/каретка и оба размера шрифта остаются обязательными.
Локально: 699 CI tests, 3 платформенных пропуска. Backend `39638175484` успешен;
Sonar check `119355693474` и полный inventory `39638164187` — 0 OPEN/CONFIRMED.
Полная матрица нового head ещё не завершена, APK не сохранён.

**Timeweb, F02/F20/F23:** новое указание владельца разрешает серверную работу.
Preflight `39636306165` и свежий повтор inventory `39249141914` /
job `119349484440` подтвердили доступный проект `2941515`, без серверов.
Каталог: 1 vCPU / 1 ГБ / 15 ГБ — 350 ₽/мес. в ru-4/ru-5 без IPv4;
1 vCPU / 2 ГБ / 30 ГБ — 550 ₽/мес. Эти предложения ещё не проверены на ёмкость.
Настройка TELEGRAM_CLIENT_SECRET присутствует. Дополнительная проверка UI
Actions variables нашла TELEGRAM_CLIENT_ID: первоначальный inventory ошибочно
читал его из secrets; workflow исправлен на vars. OWNER_TELEGRAM_SUB отсутствует.
`deploy/install_owner_backend.py` подготовлен для нового Ubuntu24.04: проверка
DNS/локального IP, отказ замены данных, новый Fernet на VM, один owner worker,
Caddy HTTPS, health+anonymous401; 12 локальных boundary tests успешны.
После Sonar-проверки установщик ограничен фиксированным root-owned файлом
с атомарным отказом symlink; health/TLS проверяют только loopback. Внешняя
проверка доступности обязательна отдельно перед подключением APK.
Исправлено ошибочное приравнивание обычного Telegram ID к OIDC `sub`:
установщик сохраняет точный opaque subject длиной до 256 ASCII-символов,
не вычисляет его из `id` и не выбирает первого посетителя. Для привязки нужен
завершённый вход владельца с проверенным подписанным токеном Telegram.
Установщик на Timeweb ещё не запускался. См. `deploy/OWNER_TIMEWEB.md`. Для свежей БД Fernet можно создать на сервере,
но выбирать личность владельца автоматически нельзя. Старый серверный адрес
не подтверждён как действующий и не используется для новых запросов с секретами.
Новая установка пока не выполнена.

**APK по запросу владельца — F01/F22/F23:** готовится совместимый
0.11.0-preview / 35 в приватном draft GitHub после полной проверки.
На `92b121e`, [run `39628105912`](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39628105912)
/ runtime `119325598726`, прошли build/lint и установка/upgrade API37/16КБ.
Spatial runtime выявил повторное открытие закрытой IME при возврате поля в
LazyColumn, из-за чего 3D swatch недоступен в уменьшенном viewport. Снимок
`699b23d832ce79d1ad9d106f359aa5eb730ae71a` подтверждает открытую клавиатуру.
Теперь несохраняемый идентификатор корневой композиции отличает пересоздание
Activity от обычного возвращения lazy item; фокус восстанавливается только
после пересоздания. Реальная видимость IME сохраняется отдельно: открытая
восстанавливается, закрытая остаётся закрытой. Native spatial probe явно
проверяет скрытую IME после смены темы; повороты по-прежнему требуют IME,
точный фокус и UTF-16 каретку. На 6b69ca0 spatial/goal runtime это подтвердил;
полная матрица ещё обязательна.
Backend `39628105913` attempt 2: 1446 tests / 1382 subtests; Sonar check
`119320453790` и полный inventory `39628931980` — 0 OPEN/CONFIRMED в PR.
Cleanup `119327574909` подтвердил verified_absent; APK не сохранён.
Очередь автоматического анализа превысила прежнее ожидание 2–3 минуты.
CI теперь ждёт до 20 минут, а Android компилируется до ожидания Sonar, чтобы
не простаивать. Перед handoff остаётся тот же exact-head zero-issues gate;
отсутствующий, незавершённый или нечистый результат по-прежнему запрещает выдачу.

На `d90b56d`, [run `39622346910`](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39622346910)
/ runtime `119304493162`, прошли build/lint, установка/upgrade API37/16КБ,
Filament, контекст, баланс и полный workflow целей font100/font200. Первый
risk/ready case выявил точную оставшуюся причину: в landscape 640×320 новое
окно 73 содержит видимое enabled EditText с правильным числом, focus=true,
selection=0/0, но keyboard-visible=false. Возврат в portrait прошёл; снимок
`b27bdf877d0e9a56f0ca02d3014d07295da8edf5` показывает открытую клавиатуру и
сохранённый курсор. Текущий кандидат явно вызывает SoftwareKeyboardController.show
после получения native focus в готовом окне; read-only поле не открывает IME.
Это исправление приложения, проверки IME/focus/caret не ослаблены. Основание:
[официальный SoftwareKeyboardController](https://developer.android.com/reference/kotlin/androidx/compose/ui/platform/SoftwareKeyboardController).
Backend `39622346939`: 1446 tests / 1382 subtests; Sonar check `119291666221`
и полный inventory `39623131560` — 0 OPEN/CONFIRMED в PR. Cleanup `119309966258`
успешен. Полная матрица нового кандидата и выдача APK ещё не подтверждены.

На `7f5c72b`, run `39614968981` / runtime `119279154337`, снова прошли
установка/upgrade API37/16КБ, Filament, контекст, баланс и цели обоих шрифтов.
Риск-сценарий прошёл распознавание disabled Button и ввод обоих предположений,
но остановился на восстановлении focused draft/caret после поворота.
Снимок `249107e0d4bf7d5683ac855376121bacab4ded87` показывает сохранённое число 5
без открытой IME. Кадр успешного поворота не создан; finally мог заменить
первоначальную ошибку ошибкой возврата. Теперь обе фазы выводят фактические
window/IME/focus/selection без содержимого полей, сохраняя отказ проверки.
`SpectrumTextField` ждёт RESUMED и фокус нового окна, раскрывает поле через
BringIntoViewRequester, затем восстанавливает фокус. Уход неактивного окна
не перезаписывает сохранённый выбор поля. Текст по-прежнему принадлежит caller;
пароли и token не копируются в saved-state Bundle. Это кандидат исправления,
полный runtime нового кода ещё обязателен. Sonar этого head — 0 OPEN/CONFIRMED,
Backend — 1446 tests / 1382 subtests, Android build/lint успешны; APK не сохранён.

На `b1389fd`, run `39609995259` / runtime `119262375498`, прошли установка,
обновление и запуск API37/16КБ, Filament, контекст, баланс, полный сценарий целей
при font100/font200. Повороты сохраняют IME/каретку, два POST дают одну запись,
удаление подтверждено при обоих шрифтах. Отчёт целей — blob
`873dcf197eaad294f4682c1ed44ca1a8b2c446ce`.
Первый business case `risk/ready;font=1.0` остановился на поиске native Button.
Снимок `9647c54baeb3c7f0b764621ab7f0083e0e72b12e` показывает видимую отключённую
кнопку. AndroidX сохраняет clickable/enabled у родителя View, а Role.Button
для непустого Compose control выносит в отдельный прямой child без OnClick.
Селектор теперь учитывает эту структуру и читает состояние только у владельца
действия; чужая, скрытая, вложенная или подписанная соседняя роль не подходит.
Та же поправка применяется к отправке чата. Источник:
[AndroidX accessibility delegate](https://android.googlesource.com/platform/frameworks/support/+/refs/heads/androidx-main/compose/ui/ui/src/androidMain/kotlin/androidx/compose/ui/platform/AndroidComposeViewAccessibilityDelegateCompat.android.kt).
Sonar/Backend этого head и cleanup `119267722942` успешны; второй профиль ещё не
запускался, APK не сохранён. Новый полный прогон обязателен.

Создание device-test draft привязано к текущему исходному head именованной ветки,
как уже работающий приватный CI handoff. Фактически проверенный merge SHA остаётся
отдельно в теле и квитанции; хеш APK и полная матрица не подменяются. Это устраняет
расхождение с handoff, где создание draft на workflow-коммите без branch/tag ref
ранее получило HTTP403. Права token не расширялись; сохранение нового APK ещё
требует фактического успешного выполнения после runtime.

На `594bc6a`, run `39603718706` / runtime `119240733653`, поворот, ввод,
сохранение и восстановление цели прошли при font100 и font200. После удаления
при font200 пассивное ожидание заголовка пустого состояния не прошло. Снимок
`0783149c9a49dfaf3665c8e2bc6e4c7b2630b450` показывает пустую карточку,
прокрученную ниже заголовка. Теперь сначала обязательны records=0 и прежние
счётчики requests, затем заголовок раскрывается прокруткой вверх.
Cleanup `119245550597` прошёл. APK этим прогоном не сохранён.
Для PR включена отмена устаревшего прогона при новом head. Cleanup с always()
и итоговый строгий check сохранены; production-выпуски и Windows build mutex
сохраняют cancel-in-progress=false. Новый CI должен подтвердить очистку и runtime.

На `512d710` Android run `39593012131`, runtime `119203214666`, подтвердил
установку/обновление API37/16КБ, Filament, контекст, баланс и цель font100.
При font200 тест не дождался фокуса суммы после поворота. Просмотрен снимок
`84170f1b2fefe02aefceebd8561043bf40c3a904`: фокус в названии, клавиатура открыта.
Глобальная геометрия могла измениться до нового содержимого Activity. Проверка
диалога требует нового публичного window ID, видимой IME и точной каретки
при повороте и возврате. Главное окно Android может сохранить: для него вместо
смены ID проверяется ориентация настоящего Compose из существующего debug marker,
а IME/каретка обязательны так же. Это усиление наблюдения, не сброс draft.
[ActivityThread AOSP](https://android.googlesource.com/platform/frameworks/base/+/master/core/java/android/app/ActivityThread.java)
явно поддерживает mPreserveWindow и повторное использование decor view.
Полная матрица API37 / 4 КБ и 16 КБ ещё не пройдена; новый CI обязателен.
`[private-apk]` запрашивает существующий путь сохранения после всех проверок;
файл пока не объявляется доступным, main/Timeweb не обновлены.

Итоговый Android check теперь выполняется для каждого PR в main и не может
завершиться пропуском вслед за зависимостями: preflight, сборка, runtime и очистка
должны быть успешны. На `ea6d1ee` весь этот pipeline успешно выполнен.

[Подробные результаты и ограничения](CI_HOSTING_DECISION_2026-10-21.md).

[Главный план](MASTER_PLAN.md) · [Главная страница](../README.md#development-plan)

<a id="repair-2026-10-21"></a>

## Исправления 21.10.2026 — F01 / F22 / F23

Первый Linux-перенос `97227a4` прошёл полную сборку/lint, но повторное создание
черновика после продвижения ветки получило HTTP 403. Runtime ещё не запускался;
cleanup прошёл. Теперь preflight сохраняет один проверенный пустой draft до
конца прогона, а upload не создаёт новый release. Подробности — в решении CI.

Штатный Android CI переводится на отдельные сборку/подпись и бесплатный Linux
runtime. Итоговый обязательный job требует успешных preflight, сборки, полной
матрицы и очистки; сборка сама по себе больше не может дать зелёный итоговый
статус. Экспериментальные дубли workflows удалены. Итоговый runtime ещё ожидается.

**Ёмкость CI и стоимость.** По указанию владельца сравниваются доступные
регионы без привязки к стране, включая бесплатные стандартные GitHub runners.
Ubuntu прошёл фактические KVM/диск/SDK-проверки (4 CPU, около 16 ГБ RAM,
85,8 ГиБ свободно; API37 и оба системных образа). Пробная Timeweb VM удалена,
оставшихся IP по полной проверке нет. Передача через S3 не прошла проверку
подписи; оба пустых бакета больше не видны. Подготовлен временный private draft
handoff с проверкой анонимного отказа и очистки до полной матрицы 3D.
[Решение, цена, run/job и точные ограничения](CI_HOSTING_DECISION_2026-10-21.md).

На `97227a4` Sonar: 0 новых, 0 принятых замечаний, 0 security hotspots.
Приватный synthetic handoff и его очистка прошли в run `39565256916`;
началась сборка подписанных APK. Локально прошли
52 проверки оставшихся Timeweb/архивных правил, 8 Node-проверок приватного handoff и 682 CI tests
(3 платформенных skip). Проверка реального runtime ещё не объявлена успешной.

Последние Android runs `e6056bf` / `0e2015e` прошли сборку/lint и очистку,
но до запуска эмулятора измерили 2 853 695 488 / 3 055 665 152 свободных байта
при требовании 6 442 450 944. Это подтверждает необходимость ёмкости CI.

Владелец повторно потребовал настоящий 3D-интерфейс и исправление ошибок main
и рабочих веток. Рабочая линия остаётся `codex/spectrum-3d-100` / PR #880.

Уточнение владельца и повторное чтение GitHub 21.10.2026 подтверждают:
репозиторий **public** (`private=false`). Это видимость исходников, а не
разрешение расширять доступ к личному приложению. PR #884 слит в main как
`973f294`; Backend CI и offline Timeweb preflight этого SHA успешны, live
Timeweb запрос был пропущен существующим условием. Диагностика
[39550813783](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39550813783)
получила все 79 открытых замечаний main и сверила их с точным SHA. Исправления
находятся в [PR #885](https://github.com/MishaGameHacking/omni-cio-gateway/pull/885)
(`0e2015e`): его Backend CI, Sonar и Android build/lint успешны. Контроль
временного userdata и очистка intermediates перенесены; оставшегося диска
по-прежнему недостаточно. Итоговая runtime-проверка остаётся обязательной.
Нулевой список всего main требует отдельной проверки после merge.

Дублирующие draft PR #882 и #883 закрыты без merge и без удаления веток:
ограничитель и строгий JSON parser уже присутствуют в main и здесь. Файлы
ограничителя и 12 тестов #882 совпадают с main; дополнительные 15 тестов
/ 17 subtests #883 прошли на коде `479a639` и сохранены в этой ветке.

Эта ветка переносит исправления SQLite commit/rollback/close, AI-политики,
агрегации портфеля, обработчиков UI и неоднозначных тестов исключений.
Сохранены особенности 0.11.0: Filament/GLB, состояния выбора, проверка валюты
и наличия количества, ограничения маршрута и бюджета модели. Изолированный
AST-тест теперь загружает реальную извлечённую функцию валидации сообщений.
Локально: **1446 backend tests / 1382 subtests, 682 CI tests (3 skip),
15 GLB tests**; каталог и все 90 моделей совпадают байт в байт.

Аннотации предыдущего `cb218232` подтверждают потерю связи self-hosted runner
для Android и Backend; диагностический job превысил шесть минут. Это не
доказательство сбоя приложения. После синхронизации с main `9b1cf57` прошёл
Android build/lint, затем остановился при `lstat` длинного Windows-пути
в очистке intermediates, до запуска AVD. Исправление `f33a92a` переводит
проверенный корень в extended Win32 path; проверки APK, ссылок, исходников
и границ удаления сохранены. Backend CI и Sonar `f33a92a` успешны. Android
[39552381267](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39552381267)
прошёл build/lint и очистку с неизменными SHA-256 всех четырёх APK: свободное
место выросло с 2 581 491 712 до 3 012 976 640 байт. Перед запуском AVD
доступно 3 012 681 728 байт при необходимых 6 442 450 944. Эмулятор не запущен;
остаточная нехватка диска runner остаётся блокером. Успешный runtime нового
APK не заявлен, требования ёмкости не уменьшались.

- На `0d5d406` сборка всех Android-вариантов и lint успешны, Backend CI и
  Sonar успешны (0 новых / 0 принятых замечаний). Но runtime не стартовал:
  [Android CI 39418067371](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39418067371)
  обнаружил 2 072 121 344 свободных байта при требовании 6 442 450 944 байта.
  Это отказ ёмкости runner до запуска AVD, не подтверждённый краш Filament.
- [Повтор 39547771650](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39547771650)
  выявил дополнительный дефект теста: `truncate(DATA_BYTES + 1)` создавал
  временный файл больше 4 ГБ и на Windows завершался `ENOSPC`. Тест теперь
  задаёт измеренный размер на границе I/O и выполняет реальную проверку
  округления, места и записи конфигурации. Добавлена проверка отказа при
  нехватке одного байта. Требования к настоящему AVD не уменьшены.
- После сборки и проверки APK удаляются только `intermediates` / `tmp`
  модулей app и ci-ui-driver текущего checkout. Все четыре APK хэшируются
  до и после; outputs, отчёты, mapping, SDK, общие кэши и чужие checkout
  не являются целями очистки. Отсутствующий APK, tracked source или ссылка
  в любой цели останавливает очистку до удаления. Остаточный дефицит диска
  по-прежнему блокирует runtime. Поддержка длинных путей Git добавлена в Backend CI.
- До последующего переноса ремонта качества: **678 CI-тестов,
  3 платформенных пропуска; 15 тестов GLB**.
  Все 90 моделей генератора совпадают с исходным каталогом. Это не новая
  успешная проверка APK на эмуляторе и не проверка физического Samsung.
- `main` на `5b5d1f2` имеет 79 новых замечаний Sonar при формально прошедшем
  Quality Gate. Их устранение не подтверждено. Timeweb preflight
  [39532595104](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39532595104)
  прошёл 37 локальных тестов, но получил HTTP 403 от projects / servers / S3.
  Экспорт исходников [39481290499](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39481290499)
  остановлен квотой GitHub Artifacts. Эти два ограничения не исправляются
  ослаблением тестов. Исторические артефакты и секреты не удалялись.

Приватный APK 0.11.0 и production-выпуск не подтверждены. Сервер, Timeweb,
торговые действия и канал обновлений этим исправлением не изменяются.

**Обновлено: 18.10.2026.** Начальная сверка кода:
[`f1f234a`](https://github.com/MishaGameHacking/omni-cio-gateway/commit/f1f234a5baa516a439cc745993bd5782dd9c5f5f).
Владелец утвердил реализацию всего плана последовательными готовыми обновлениями.
Сохранение плана не означает, что перечисленные функции уже разработаны.

**В работе: единое обновление [3D100 / 0.11.0 / 35](3D100.md), [PR #880](https://github.com/MishaGameHacking/omni-cio-gateway/pull/880).** Ветка `codex/spectrum-3d-100` включает настоящий 3D-интерфейс и серверные сценарии. Реестр 100 пунктов связывает поведение, исходники и проверки. Сводка F01–F23 ниже сохраняет оценку опубликованной базы; её более широкие критерии не закрываются наличием новых экранов.

**Последняя подтверждённая публикация: 0.10.0-preview / 34**,
[`0a894dd`](https://github.com/MishaGameHacking/omni-cio-gateway/commit/0a894dddfa858efe6c7be60aea78935adec84c1b).
Доставка — [PR #878](https://github.com/MishaGameHacking/omni-cio-gateway/pull/878),
[успешный workflow](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39048187540).
Публичный манифест и полный APK независимо проверены 17.10.2026, 19:14 МСК;
точные результаты и границы приёмки записаны в F01.4 / F22 ниже.
Указатель актуальных и исторических документов: [docs/README](README.md).

## Аудит 18.10.2026 — F01/F02–F09/F15/F20/F22/F23

[Полный аудит, 30 направлений и применение идей Грэма](AUDIT_0.11.0_2026-10-18.md).
Новые каталог и проверка покупки реализованы в рабочей ветке; полный конвейер
индивидуальных рекомендаций остаётся незавершённым. Исходные данные и результат
новой проверки хранятся зашифрованно, с версиями и проверкой владения.

- Локально: **927 backend tests / 337 subtests**, **20 целевых 3D-script tests**.
  Это синтетические проверки, не live-брокер и не физический телефон.
- [`24bef48`](https://github.com/MishaGameHacking/omni-cio-gateway/commit/24bef4817fb1efe06655606b2f10425a7240d1cc):
  [Backend CI success](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39125146574);
  [Android CI](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39125146599)
  прошёл сборку/lint/upgrade/launch API35, но visual gate обнаружил обрезанную
  область light mesh высотой 21 px. Эти результаты не являются полным runtime pass.
- [`b5fae83`](https://github.com/MishaGameHacking/omni-cio-gateway/commit/b5fae83aeac296e4f9eed920ababbc1a3d97c8fd)
  добавляет lookup transform по стабильному entity и обязательные размеры области
  захвата. [Backend CI success](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39126425885).
  [Android CI](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39126425892)
  прошёл сборку/lint, upgrade/launch API35 и строгие dark/light mesh, dialog,
  clipping, long-scroll проверки. Реальный light PNG просмотрен. Затем runtime
  остановился на rotation: тест послал scroll до пересоздания app root.
  Добавлено ожидание фактической landscape-конфигурации приложения; запрет
  действий в чужом окне сохранён. API36 ещё не подтверждена.
  Новый backend/каталог и исправление rotation требуют CI
  окончательного коммита; старые проверки не подменяют его.
- Artifact storage quota остаётся исчерпанной; реальные synthetic screenshots
  и отчёты доступны через записанные в CI Git blob refs. Исторические артефакты
  не удалялись. Это ограничение хранения, не успешная публикация APK.
- `61efad0`: [Backend CI](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39128137551)
  прошёл: 920 passed, 2 платформенных skip, 337 subtests; health/OpenAPI success.
  Sonar Quality Gate success, но 8 замечаний к сложности и оформлению тестов
  потребовали исправления. Они исправлены в следующем срезе, без снятия ограничений.
- Новый Android-каталог получает 4 явных synthetic сценария × 2 font scales:
  поиск/проверка/сброс результата, отказ из-за резерва, пустой каталог, ошибка/retry.
  Полная обязательная business-матрица увеличена с 52 до **60 case/font ID**;
  portfolio-матрица сохраняет 14. Старый receipt не удовлетворяет новой матрице.
  Локально дополнительно прошли 47 проверок business/installation/emulator contract.
- `d8896bd`: Backend CI success (920 passed, 2 платформенных skip, 337 subtests),
  Sonar Quality Gate success и полная выгрузка **0 открытых замечаний всех типов**.
  Все Android-варианты/lint прошли; runtime ещё выполняется. Это не полный UI pass.
- Последняя поправка срока покупки ограничивает `expires_at` самым ранним
  истечением портфеля, стакана и цикла брокерских чтений. В транзакции истёкший
  положительный результат отклоняется. Два новых regression tests проходят.

Установленной версией остаётся **0.10.0 / 34**. Статусы прежних срезов ниже —
исторические доказательства. Они не закрывают непроверенные сценарии нового кода.

- `d8896bd`: ожидание нового app root устранило прежний сбой соединения, но
  [Android CI](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39128668974)
  остановился на поиске «Нажатий: 1» после поворота. До него пройдены сборка/lint,
  upgrade/launch API35, dark/light mesh, dialog, clipping и long-scroll. Новый
  тест выбирает стабильную нативную цель вкладки, подтверждает состояние ДО
  поворота и сохраняет оба кадра. Потеря состояния пока не доказана: прежде
  текстовая цель могла переместиться после горизонтальной прокрутки. API36 и
  business-матрица этим запуском не подтверждены.

## Исторический прогон 3D100 на 81b0101

- Реализация: [PR #880](https://github.com/MishaGameHacking/omni-cio-gateway/pull/880), версия `35 / 0.11.0`; preview package, сертификат и baseline `0.10.0 / 34` сохранены.
- Последний завершённый GitHub SHA: [`81b0101`](https://github.com/MishaGameHacking/omni-cio-gateway/commit/81b01017a1be73c5ba4d0ebe39e1e7f86002654f). [Backend CI](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39099562510) — **846 passed, 2 skipped, 337 subtests passed за 43,51 с**, health/OpenAPI успешны; **Sonar Quality Gate passed**. Windows-исправление импорта подтверждено.
- [Android CI](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39099562552) прошёл JVM/debug/preview/release/lint за **8 минут 51 секунду**, canonical LF checkout, 11 native-alignment тестов и строгую побайтную проверку **91 ресурса готового APK**. Developer README перенесён из assets в [SPECTRUM_3D_ASSETS](SPECTRUM_3D_ASSETS.md); source-tree ZIP regression и реальная упаковка подтверждают исправление.
- Runtime того же SHA подтвердил API 35 / **getconf PAGE_SIZE=16384**, установку 34 и upgrade до 35. Первый запуск завершился `SIGABRT` при компиляции встроенного Filament `blitLow` на legacy GLES SwiftShader 4.0.0.1. Попытка заменить FXAA на MSAA не устранила общий дефект компилятора. **Android CI FAILURE; успешных UI-кадров, полного receipt v2 и API 36 пока нет.**
- Для следующего CI восстановлен исходный FXAA; среда переведена на **гостевой ANGLE + Vulkan / Lavapipe**. Запуск требует фактический Filament-контекст свежего UID/PID, системная графика не заменяет его. **55 целевых локальных тестов прошли, включая 14 новых**; независимый review не выявил блокирующих дефектов. Полный новый runtime пока не подтверждён.
- Локальный Android-срез: **28 JVM**, debug APK, UI-driver и lint debug за **2 минуты 51 секунду**. Последний полный локальный Python-набор Android/релизных сценариев: **435 passed, 1 skipped**; mesh-набор — **15 passed** локально, **14 passed / 1 предусмотренный пропуск POSIX symlink** в Windows. Все исходные 100 критериев, код и границы проверок сохранены в [3D100_EVIDENCE](3D100_EVIDENCE.md). Новый SHA должен пройти применимые проверки заново.
- Следующий runtime сохраняет API 35 ps16k, API 36 / 4096, обновление с `0.10.0 / 34`, реальные кадры Filament и receipt v2 с **52 business + 14 portfolio case/font IDs на каждой API**.
- Публичные health и update-policy повторно прочитаны **18.10.2026, 07:55 МСК**: сервер отвечает `ok`, канал по-прежнему выдаёт `0.10.0-preview / 34`, ожидаемые SHA256, размер и сертификат. Это чтение манифеста; полный APK в этот момент повторно не скачивался.
- Backend, APK и канал `0.11.0` ещё не объявляются установленными. Физический телефон, TalkBack, нагрев и расход батареи фиксируются отдельно.

## Исправление качества 18.10.2026 — F01 / F22 / F23

Последний завершённый срез [`4822c71`](https://github.com/MishaGameHacking/omni-cio-gateway/commit/4822c7152f22f72d32ecdfb6f324cd9b1555a998): полная выгрузка Sonar содержит **1 новое замечание / 0 принятых**, `all_types=true, complete=true`: цепочка `if` в статусе точки посещения. Она заменена на `when`. [Backend CI](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39120854626) — **SUCCESS**. [Android CI](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39120854625) успешно прочитал GitHub check-runs, но завершился ошибкой lint `ContextCastToActivity` в новом debug-сценарии целей. Теперь он использует `LocalActivity`. Runtime не запускался; полного API35/API36 pass и новых кадров нет.

Локальная проверка следующих исправлений: debug/release Kotlin и Java UI-driver компилируются, 54 JVM-теста прошли. `lintDebug` и `lintRelease` завершились без ошибок; предупреждения lint не объявляются устранёнными. Временная локальная подстановка отсутствующего изображения логотипа удалена и в GitHub не передаётся.

При разборе 3D025 исправлена ложная подпись успешного сохранения точки сравнения при ошибке encrypted storage. Успех теперь зависит от фактически прочитанного ID записи; ошибка чтения/сохранения имеет явный повтор. ID посещения переживает rotation, повтор не сдвигает baseline второй раз и не заменяет более позднюю точку, уже сохранившую эту как предыдущую. Локальная компиляция и 54 JVM-теста прошли; отдельный device-case отказа записи ещё не пройден.

Disk preflight теперь поддерживает оба официальных формата исходных данных: userdata.img и каталог data/, из которого сам эмулятор создаёт ext4. Сохраняются 4 ГБ minimum, размер большего исходного образа, запас места, RAM 4096 MB, официальные API35 ps16k/API36 и очистка только остановленного AVD своей попытки. Восемь регрессий проверяют размер, источник и безопасную очистку. SDK остаётся неизменным.

Ручной разбор 3D029 выявил восстановление удалённой цели устаревшим редактором. Теперь сервер атомарно требует существующий ID владельца и отвергает пустое после trim название. Неизвестный результат сохранения фиксирует поля открытого редактора и request_id; повтор использует тот же payload. Добавлен device-case production-редактора: native draft/focus/caret, pending rotation, потерянный ответ, одна цель после повторного запроса и удаление; font100/200. Он компилируется, но на устройстве ещё не пройден. Offline reader сохраняет запрос открытия во время повторной проверки версии после rotation; чтение разрешается только после допустимого offline-результата.

Сохраняются исправления черновика стратегии, приватного прогресса цели, стабильной вложенности SpatialField и очереди переходов сеанса. Предыдущий кадр 94d3307 содержит полосы на 3D-поверхностях; контрольный снимок без теней ещё не получен. Обычная сцена сохраняет PBR/FXAA/тени.

Локально: **890 backend Python-тестов / 616 subtests**, **475 Android/релизных тестов (1 предусмотренный пропуск)**, **54 JVM-теста**, debug/release Kotlin и Java UI-driver — без ошибок. Synthetic device-cases не подтверждают настоящий Telegram login. Общая приёмка 100 пунктов остаётся открытой; карта — [3D100_EVIDENCE](3D100_EVIDENCE.md). Все результаты ниже исторические.

Полная выгрузка Sonar для `b280a02` содержит **142 открытых замечания всех типов**;
прошедший Quality Gate не означает их устранение. Android CI этого SHA собрал все
варианты и прошёл lint, но после загрузки API35 / 16 КБ зависла установка baseline
APK 0.10.0: последующие shell/logcat также перестали отвечать, хотя ADB сохранял
состояние `device`. Ветка остаётся в разработке, приёмка 100 пунктов открыта.

Проверка доступности теперь требует отдельного ответа гостевого shell, сохраняя
прежний предел двух полных запусков одноразового AVD и отказ при ошибках UI.
На `d01dcd8` все варианты APK и lint снова прошли; Backend CI успешен.
[Android run 39107888813](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39107888813)
показал, что API35 не завершает загрузку с гостевым ANGLE поверх программного
Vulkan SwiftShader. Следующий запуск использует Vulkan-драйвер Windows-хоста;
фактический ANGLE/Vulkan-контекст свежего PID, кадры и полный UI receipt остаются
обязательными. Успех runtime пока не подтверждён.

По полной выгрузке 142 замечаний подготовлен рефакторинг Python и Kotlin:
разделены получение/проверка фактов, сценарии UI, маршрутизация, компоненты экранов
и стадии 3D-рендерера; повторяемые значения вынесены в константы; исправлены
условия, объявления зависимостей и проверки исключений. Неправильные списки
действий/подсветок в ответе модели теперь дают контролируемый отказ, а неизвестная
стоимость позиции не используется для расчёта плана. Добавлены регрессионные тесты.
Полное устранение замечаний будет подтверждено только новой выгрузкой Sonar.

Локально: **883 теста и 616 подпроверок** backend/ELF/GLB, отдельно **451 тест
CI-скриптов, 1 пропуск**; все 90 GLB генератора совпадают с исходными побайтно.
Синтаксис изменённого Kotlin разобран Kotlin-парсером ktfmt 0.64 без ошибок.
Проверки компиляции и поведения нового SHA, а также приёмка 100 пунктов ещё открыты.

## Правила статуса

| Статус | Что он означает |
| --- | --- |
| Основа есть | В коде найдена полезная часть. Все требования пункта ещё не выполнены. |
| Не реализовано | Законченного пользовательского сценария нет. Отдельные заготовки не меняют статус. |
| Не подтверждено | Нужна проверка работающего сервера, источника или устройства; наличие инструкции не является доказательством. |
| В работе | Указать конкретную ветку или PR и оставшуюся работу. |
| Проверено в коде | Все критерии пункта выполнены и применимые проверки точного SHA успешны; выпуск ещё не подтверждён. |
| Выпущено | Код проверен, необходимые серверные изменения установлены, новый APK опубликован и доступен в канале обновления. Приведены ссылки и ограничения. |

Отдельно фиксировать проверку на физическом телефоне. Эмулятор, публикация APK
и установка владельцем — разные факты. Процент готовности по числу файлов или
экранов не вычислять. Пункт закрывать только после всех его критериев приёмки.
Если часть готова, дробить её на проверяемые подзадачи, сохраняя остаток работы.

## Что уже разработано как основа

- [x] Kotlin и Compose, Workspace / Spectrum, пять основных вкладок и столбчатая история стоимости в опубликованном 0.10.0. Текущая линия 0.11.0 требует Android 17 / API37 (`minSdk/compileSdk/targetSdk = 37`); прежние Android 15+ относятся только к историческому выпуску.
- [x] Чтение реального портфеля, счетов, позиций, операций, купонов и дивидендов через T-Invest; история собственных снимков.
- [x] Telegram-вход, серверные сеансы, зашифрованное серверное хранение T-Invest токена и защищённое локальное хранение сеанса Android.
- [x] Серверные задания, структурированная AI-аналитика, уровни моделей и учёт бюджета в коде.
- [x] Сборка подписанного preview APK, проверка установки и обновления, GitHub Releases и механизм канала обновлений.

Эти галочки подтверждают перечисленную основу, а не выполнение всех новых
требований. Например, ограничение в пять аккаунтов ещё не заменяет приглашения,
планировщик заданий ещё не гарантирует независимый риск-контроль, а наличие
AI-клиента ещё не подтверждает подключение платных моделей в рабочей установке.

## Полный реестр работ

Идентификаторы `F01–F23` постоянны: их указывают в PR и описаниях выпусков.
Номер § ведёт к разделу главного плана; критерии относятся ко всему пункту.

| ID и статус | Область / источник в коде | Что требуется для завершения |
| --- | --- | --- |
| **F01 — основа есть; F01.2–F01.4 реализованы** | [Android и Spectrum, §29](MASTER_PLAN.md#plan-29). `app/build.gradle.kts`, `ui/spectrum`, основные экраны | Сохранять Android 17 / API37, package и сертификат; завершать полную матрицу с измеренными страницами 4096 и 16384 байта, крупным шрифтом, узким и большим экраном, возвратом из браузера/брокера, разрешениями и отключённой анимацией. 0.10.0 / 34 опубликован и доставлен как историческая база обновления; физическая приёмка остаётся отдельной. |
| **F02 — основа есть** | [Реальный портфель, §02, 13](MASTER_PLAN.md#plan-02). `backend/app.py`, Android repository | Полные данные всех счетов без смешивания пользователей; блокировки и неизвестная оценка показаны явно; поток обновлений и сверка операций согласованы с F08/F11; доходность не подменяется оборотом или пополнениями. |
| **F03 — основа есть** | [Закрытый доступ и сеансы, §04–06](MASTER_PLAN.md#plan-06). `app.py`, `telegram_browser_app.py`, `AuthSessionStore`, `MainActivity`, `BootstrapActivity` | Приглашения максимум для пяти аккаунтов; атомарный одноразовый обмен кода; защищённый возврат; продление и серверный отзыв сеансов/устройств; ротация ключей; обновление APK и временная сеть не теряют действующий вход. Проверить конкуренцию и чужой Telegram ID. |
| **F04 — основа есть** | [Четыре рейтинговых агентства, §08–09](MASTER_PLAN.md#plan-08). `credit_evidence.py`, `research_store.py` | Актуальные разрешённые источники АКРА, Эксперт РА, НКР, НРА; точные национальные шкалы и все десять ступеней AAA–BBB-; отдельные рейтинги эмитента/выпуска; история, отзывы, конфликты и дата проверки. В текущем разборе найдены только АКРА/Эксперт РА и импорт проверенных сведений. |
| **F05 — не реализовано** | [Допустимый рынок и права, §07](MASTER_PLAN.md#plan-07). Реестр инструментов / T-Invest adapters | Полный каталог с пагинацией; Мосбиржа по умолчанию, вне Мосбиржи только подтверждённые доступные активы; квалификация и тесты у брокера; настройки могут только ужесточить доступ. Исключение заблокированных, недоступных и запрещённых сложных инструментов до глубокого анализа. |
| **F06 — основа есть** | [Компании и связанные группы, §10](MASTER_PLAN.md#plan-10). `portfolio_research.py`, `portfolio_risk.py`, `research_store.py` | Все выпуски облигаций и акции одного эмитента на всех счетах складываются в одну долю; отдельно учитываются группа, отрасль и валюта. Прозрачный учёт фондов; неизвестная связь/оценка не превращается в ноль. Суверенный долг не получает выдуманный рейтинг компании. |
| **F07 — не реализовано** | [«Мои стратегии», §11](MASTER_PLAN.md#plan-11). `analysis_profiles`, `ProfileUpdate`, будущий модуль правил | Версии стратегий сохранения/накопления/выплат, горизонт, резерв, пополнения и допустимый риск; ступени рейтингов и лимиты компании/группы/отрасли; preview изменения и подтверждение. Стартовые доли из плана — проверяемые параметры, а не неизменная универсальная оптимальная формула. |
| **F08 — основа есть** | [Деньги, доход и валюта, §12–13](MASTER_PLAN.md#plan-13). `portfolio_risk.py`, операции и календарь | Единая точная денежная арифметика: лоты, НКД, амортизация, комиссии, резервы, доступный остаток, валютные условия выпуска, налоги по актуальным правилам. Отдельно капитал/пополнения/доход; TWR/MWR только при достаточной истории. Полная стоимость сверяется независимым расчётом. |
| **F09 — не реализовано** | [Покупка и докупка, §14](MASTER_PLAN.md#plan-14). Отдельные функции предварительного расчёта есть, общего планировщика нет | Проверенный общий каталог → фильтры → компания → выпуски → целые лоты → стоимость и риски → один выполнимый план. Учёт уже имеющихся позиций и лимитов. При отсутствии денег — наблюдение без бесполезного дорогого поиска; допустим результат «ничего не менять». |
| **F10 — основа есть** | [Ребалансировка и изменения рейтинга, §09, 15](MASTER_PLAN.md#plan-15). `portfolio_risk.py` | Выход при падении ниже BBB- с учётом возможности сделки; уменьшение доли при снижении допустимого рейтинга; коридоры, комиссии, налоги и ликвидность. Не продавать только ради финансирования новой покупки. Замена оплачивается только фактически доступными средствами после исполнения. |
| **F11 — основа есть; F11.1 выпущен** | [Наблюдение 24/7, §16](MASTER_PLAN.md#plan-16). `autonomous_ai.py`, `ai_jobs.py`, `monitoring_access.py` | F11.1: независимость от версии APK/Android-сеанса и проверка отключения подключения выпущены в 0.7.5. Осталось: общий сбор по эмитенту, разная глубина по риску, устранение среза первых 100 позиций и восстановление после сбоя. Проверить 2000 позиций и нагрузку пяти пользователей. |
| **F12 — основа есть** | [Отчётность компаний, §17](MASTER_PLAN.md#plan-17). `research_store.py`, `portfolio_research.py` | Законные актуальные адаптеры публикаций, история версий и первоисточники; проверка периода, валюты, единиц, МСФО/РСБУ и консолидации; отраслевые показатели. Расписание отчётов не выдаётся за саму отчётность. AI-извлечение сверяется кодом и источником. |
| **F13 — не реализовано** | [Новости, политика и интернет, §19](MASTER_PLAN.md#plan-19) | Общий по компаниям сбор, первичные факты и проверяемая связь события с риском конкретных активов; разрешённый веб-поиск через Timeweb; фильтр повторов. Интернет-текст не выполняет команды и не меняет правила/секреты. Проверить стоимость, доступность и права источников. |
| **F14 — основа есть** | [Математика и прогнозы риска, §18](MASTER_PLAN.md#plan-18). `portfolio_risk.py`, сценарные расчёты | Концентрации, длительность, ликвидность и совместные стресс-сценарии; вероятности дефолта только при подходящих данных и калибровке. Проверка на будущих для модели периодах, без знания будущего и исключения дефолтных компаний. Не показывать точную дату дефолта или гарантию сохранности. |
| **F15 — основа есть** | [ИИ, модели и бюджет, §20–21, 27–28](MASTER_PLAN.md#plan-21). `analysis_engine.py`, `ai_policy.py`, `ai_guarded_client.py`, `ai_budget.py` | Раздельные фоновые/диалоговые задачи; выбранные и проверенные модели через Timeweb; общие кеши и лимиты, резервирование и сверка расходов, контроль неопределённых таймаутов. Нет автоматического дорогого переключения. Критические расчёты/сигналы работают без LLM. Подключение моделей в рабочей среде не подтверждено. |
| **F16 — не реализовано** | [Полноценный чат, §22](MASTER_PLAN.md#plan-22) | Обычный разговор, объяснение реального портфеля, выбор темы, предпочтения и настройки через разрешённые инструменты; важные изменения стратегии подтверждаются. Месячный пост — черновик для пользователя. Нет чужих счетов, произвольного SQL/shell, токенов в запросах и вымышленных чисел. |
| **F17 — не реализовано** | [«Действия» и их исполнение, §14–15, 23](MASTER_PLAN.md#plan-23). `insight_cards` — только исходная основа | Одна конкретная инструкция с количеством, причиной, временем данных и переходом к нужному выпуску. Состояния: рассчитано / открыт брокер / ожидается сверка / частично / выполнено / устарело. Открытие ссылки не считается сделкой; устаревший план пересчитывается. |
| **F18 — основа есть** | [Компактные риски и этап портфеля, §23](MASTER_PLAN.md#plan-23). Экран рисков и Spectrum | Понятные показатели реальной концентрации, кредитного, валютного, процентного и ликвидного риска; стадия формирования и уместный прогресс. Не выдумывать «процент защищённости» и не загружать экран лентой писем. Детали доступны по запросу. |
| **F19 — не реализовано** | [Центр уведомлений, §24](MASTER_PLAN.md#plan-24). Лента сообщений не равна надёжной доставке | Сохранение уведомления вместе с событием, повторная безопасная доставка, отсутствие дублей, тихие часы и приватность, переход к действию. Только нужные действия. При составе «приложение + Timeweb» фоновая доставка Android может задерживаться; не обещать мгновенный push или фактическое SMS без отдельного канала. |
| **F20 — не подтверждено** | [Эксплуатация и восстановление, §25–26, 28](MASTER_PLAN.md#plan-25). Существующий Timeweb | Инвентаризация рабочего сервера; минимально достаточная конфигурация с измеряемым запасом на пики пяти пользователей; мониторинг задержек и бюджета. Резервная копия БД и защищённых ключей отдельно от сервера; проверенное восстановление, целевые RPO/RTO и регулярная проверка. Покупка ресурсов требует отдельного разрешения. |
| **F21 — основа есть** | [Качество и происхождение данных, §26](MASTER_PLAN.md#plan-26). `research_store.py`, проверки research snapshot | Время получения и действия, источник, версия, срок свежести и разрешение использования каждого факта; воспроизводимый снимок для решения. Конфликт/устаревание останавливает новую покупку, но не мониторинг. Подтверждённый оператором импорт не заменяет проверку достоверности самого факта. |
| **F22 — основа есть** | [Промежуточные выпуски, §29, 31–32](MASTER_PLAN.md#plan-31). `.github/workflows/android-apk.yml`, обновления backend | Для каждого готового функционального блока — новая версия APK, полный цикл проверок, установка совместимого сервера, публикация тех же проверенных байтов в канале и содержательные русские release notes с ID плана. Сохранять доказательства доставки. Исключить повторный versionCode новых байтов; повторная доставка использует исходный release asset. |
| **F23 — не реализовано** | [Сквозная проверка итогового продукта, §31–34](MASTER_PLAN.md#plan-32) | Все сценарии ниже, теневой режим планировщика, один пользователь → пять приглашённых, проверка на телефоне и при отказах. Статусы кода/сервера/APK соответствуют друг другу. Доступность источников и правомерность использования данных/персональных инструкций проверены до расширения установки. |

## Выпущенный визуальный подэтап F01.2 — Workspace

Указание OWNER 17.10.2026 разрешает полный редизайн; [карта экранов и границы](WORKSPACE_UI.md).
**0.8.0-preview / 32 опубликован и доставлен на Timeweb 17.10.2026.** Это визуальный этап, не закрытие расчётов F04–F18.

- [x] Новые общие поверхности, навигация, иконки, движение и оформление Android 16+.
- [x] Перестроены главный экран, портфель и карточка инструмента; фильтры и группировка позиций.
- [x] Отдельные поверхности действий, обзора рисков, уведомлений и подробностей события.
- [x] Экраны оформления, ассистента, обзора рынка и черновика стратегии.
- [x] Сохранение настроек внешнего вида; действующий профиль сервера отделён от будущей стратегии. Черновик переживает смену окна/конфигурации.
- [x] Проверки точного SHA #870: сборка всех вариантов, lint, установка/обновление, Android 16, навигация, темы, крупный шрифт и Sonar. [CI](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39013319049).
- [x] Публикация нового APK 0.8.0, обратное скачивание и совпадение SHA-256. [Release](https://github.com/MishaGameHacking/omni-cio-gateway/releases/tag/android-preview-7fe22f35b07bd2fc92b5860e23418214333b8a21) · [публикация](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39014361622).
- [x] Доставка тех же байтов APK 0.8.0 на Timeweb: health, локальный/публичный манифест, версия 32, размер и SHA-256 совпали. [Доставка](https://github.com/MishaGameHacking/omni-cio-gateway/pull/871) · [проверка](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39016326972).
- [x] Прежняя подпись и данные сервера сохранены. Принудительный барьер обновления не включён.
- [ ] Проверка владельцем на физическом телефоне.

## История F01.1 — компактная главная

Исторический подэтап **0.7.6-preview / versionCode 31**, опубликован в GitHub. Его результат включён в Workspace 0.8.0; отдельная доставка 0.7.6 заменена новым выпуском.
Основание: прямое уточнение владельца от 17.10.2026, главный план §23.

- [x] Удалены панель «Живые возможности», её технический текст, бейдж Android
  и каталог демонстрационных карточек. После быстрых переходов идёт ассистент.
- [x] Сохранены четыре перехода, нативные иконки, адаптивная раскладка и реальные
  данные. Неиспользуемый компонент удалён из исходников.
- [x] Уточнение записано в главный план, правила разработчиков и визуальный контракт.
  Прежняя проверка обязательного каталога удалена вместе с отменённым требованием;
  остальные проверки интерфейса, анимаций, сборки и установки сохранены.
- [x] Все применимые проверки точного SHA #868 в GitHub: Android 16 и Sonar успешны.
  [APK опубликован](https://github.com/MishaGameHacking/omni-cio-gateway/releases/tag/android-preview-feb08a704e889644772c38808eebbc2d1edbb81f); отдельная доставка 0.7.6 заменена выпуском 0.8.0.
- [x] Результат этого изменения доставлен в составе 0.8.0. Отдельный APK 0.7.6 в канале не устанавливался; #869 заменён выпуском #870.
- [ ] Установка и работа на физическом телефоне владельца.

Для версии 0.7.6 проверялось обновление с опубликованной 0.7.5-preview / 30.
Этот подэтап не закрывает весь F01, подбор активов, стратегии, чат и остальные
открытые пункты плана. Описание результата: [0.7.6](releases/0.7.6.md).

## Выпущенный подэтап F11.1 — независимое серверное наблюдение

**0.7.5-preview / versionCode 30 — выпущено 16.10.2026.**
Это завершённый подэтап; полный F11 остаётся открытым.

- [x] Сбор портфеля, история и базовые риск-проверки независимы от открытого
  приложения, срока Android-сеанса, версии APK и доступности канала обновлений.
- [x] Фоновая задача привязана к действующему брокерскому подключению.
  Отключение/замена повторно проверяются перед обработкой, обращением к модели
  и в транзакциях записи. Уже отправленный запрос нельзя отозвать из сети,
  но его результат после отключения не публикуется как новый снимок или карточка.
- [x] Android показывает наблюдаемое состояние и время последнего снимка.
  Настройка ИИ не выдаётся за доказательство успешного получения данных.
- [x] Проверки клиентского API, бюджета и разрешений обработки ИИ сохранены.
- [x] CI проверил устаревший/закрытый клиент, отсутствующий/истёкший сеанс,
  смену релиза во время сбора, недоступный APK-канал, отключение/замену токена,
  изоляцию пяти пользователей и состояния свежести.
- [x] Backend CI: 703 теста, один предусмотренный пропуск; health/OpenAPI.
  Проверки скриптов: 359 тестов, три предусмотренных пропуска. SonarCloud успешен.
  Android 16: чистая установка, обновление с 0.7.4-preview, запуск и полный UI-прогон,
  включая крупный шрифт. Первые два прогона потеряли транспорт эмулятора;
  неполные результаты не засчитывались.
- [x] Новый APK опубликован и скачан обратно для проверки; backend установлен,
  локальный и публичный канал Timeweb вернули версию 30 и те же байты APK.
- [ ] Установка и работа на физическом телефоне владельца.

Доказательства: [код #865](https://github.com/MishaGameHacking/omni-cio-gateway/pull/865),
[Android CI](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/38958194212),
[Backend CI](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/38958194108),
[Release](https://github.com/MishaGameHacking/omni-cio-gateway/releases/tag/android-preview-bb6638fab2188c718ccad4d8dd7b3ed76b34fdc8),
[публикация APK](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/38959935233),
[доставка #866](https://github.com/MishaGameHacking/omni-cio-gateway/pull/866),
[сервер и канал](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/38963563889).

APK SHA-256: `739fb8b16865a742118ca1930bc2488a28c3cf807a23c20628df9ebb7ca75bcb`; размер 4167540 байт.
Прежние package и сертификат preview сохранены. Новые платные ресурсы не создавались.

Остаются открытыми F03 (приглашения, новый протокол сеансов), полный охват
исследования 2000 позиций, новые источники, отдельные расписания по риску,
измерение нагрузки и остальные требования F11. Полную A09 и итоговую приёмку
системы этот подэтап не закрывает. Конфигурация/ответы платных моделей и длительная
работа с реальными портфелями пяти пользователей этим выпуском не подтверждаются.

## Остатки, уточнённые при сверке 17.10.2026

Эти наблюдения относятся к исходникам опубликованной линии 0.10.0. Они не
закрываются обновлением документации и не являются новыми платными интеграциями.

| ID | Подтверждённый остаток | Источник / следующий результат |
| --- | --- | --- |
| F01 / F17 | Fallback-карточка `CASH_CHANGED` ещё использует старое название «Что купить» | `backend/autonomous_ai.py::_fallback_report`; в следующем функциональном выпуске согласовать подпись с «Действия → Анализ», не выдавая обзор за готовый план лотов. |
| F11 / F15 | Утренний/вечерний сигнал принудительно помечает digest изменившимся; расписание исключает выходные, но не использует биржевой календарь | `autonomous_ai.py::_signals`; экономия плановых обзоров при отсутствии существенных новых данных пока не выполнена полностью. |
| F15 | Critical выбирает premium по квоте до вызова; каскада по неуверенности дешёвой модели нет | `ai_policy.py`; фактическая политика и бюджет описаны в [AI_ORCHESTRATION](AI_ORCHESTRATION.md). Не приписывать коду несуществующее многоступенчатое обсуждение моделей. |
| F15 / F17 | Валидация ответа проверяет схему, длины, source IDs и даты, но не каждое утверждение свободного текста | `analysis_engine.py`; денежные действия должны опираться на независимые расчёты и проверенные факты. |
| F20 / F22 | Rollback repair возвращает backend/env, но не прежний `current.json`; публичный read-back выполняется после remote trap | [Контракт обновлений](UPDATES_AND_PORTFOLIO_RESEARCH.md); при ошибке после переключения отдельно проверять действующую policy и APK, не объявлять автоматический полный откат. |

## Очередность готовых обновлений

Порядок внутри независимых работ можно менять. Зависимые части нельзя объявлять
завершёнными без достоверных данных и проверенных расчётов. Номера версий назначаются
при подготовке выпуска, а не заранее на весь проект.

| Блок | Состав | Условие выпуска |
| --- | --- | --- |
| A. Доступ и непрерывное наблюдение | F03, F11, необходимая часть F20/F21/F22 | Закрытый доступ, сохранный вход, независимое наблюдение и восстановление проверены; новый APK совместим с сервером. |
| B. Достоверные компании и инструменты | F04–F06, F12, F21 | Все позиции, четыре рейтинговые шкалы, история и подтверждённые источники. Нельзя подменить отсутствующий лицензированный источник модельной догадкой. |
| C. Стратегии и деньги | F07–F08, нужные F02/F14 | Настройки связаны с фактическими ограничениями, компанией и расходами; малый и большой капитал рассчитаны корректно. |
| D. Конкретные инвестиционные действия | F09–F10, F17 | Теневой режим и сквозная сверка покупки, докупки, продажи и частичного исполнения; готовые действия опираются на реальные доступные деньги. |
| E. Чат и удобная работа | F13, F15–F16, F18–F19 | Ассистент использует только разрешённые инструменты и проверенные факты, бюджет ограничен, уведомления ведут к актуальному действию. |
| F. Итоговая приёмка | Все остатки F01–F23 | Нет скрытых незавершённых обязательных пунктов; ограничения честно показаны, физический телефон и эксплуатация проверены. |

В каждом блоке допустимы меньшие самостоятельные выпуски. Отделив готовую часть,
оставлять остальные требования открытыми. «Обучение» в этом плане не расширять.
Фоновая система не зависит от присутствия владельца в приложении; ведение этого
реестра само по себе не запускает разработку или обслуживание вне рабочего сеанса.

## Сквозная приёмка

Чекбоксы пока открыты: наличие похожего unit-теста не доказывает весь сценарий.
При закрытии добавить ссылку на тест/отчёт, SHA и выпуск.

- [ ] **A01:** четыре агентства и десять разрешённых ступеней; BB+ и отключённая ступень не проходят.
- [ ] **A02:** три выпуска компании на двух счетах учитываются в одной доле; связанная группа проверяется отдельно.
- [ ] **A03:** отзыв одного рейтинга при другом действующем не возвращает старую благоприятную оценку.
- [ ] **A04:** BBB- → BB+: новые покупки закрыты, один приоритетный выход, без сделки нет статуса «продано».
- [ ] **A05:** капитал 0 и свободные деньги 0: нет неверного деления и необеспеченных покупок; портфель продолжает наблюдаться.
- [ ] **A06:** частичная продажа: замена использует только подтверждённый доступный остаток, доли пересчитаны.
- [ ] **A07:** комиссия, НКД, амортизация, валюта и округление сходятся с независимым расчётом; резерв сохранён.
- [ ] **A08:** 2000 позиций, пять пользователей: нет обрезания, утечек данных и потерянных заданий; проверен разумный пиковый запас.
- [ ] **A09:** закрытое/устаревшее приложение и истёкший Android-сеанс не останавливают обязательное наблюдение.
- [ ] **A10:** временная сеть не удаляет действующий вход; отозванный сеанс не принимается.
- [ ] **A11:** два обмена одного кода дают только один сеанс; неприглашённый Telegram ID отклонён даже при свободном месте.
- [ ] **A12:** выдуманные ИИ число/ссылка не попадают в действие; применяется проверенный расчёт либо честный отказ.
- [ ] **A13:** таймаут ИИ и исчерпанный бюджет не вызывают бесконтрольные повторы/дорогой переход; обязательный риск-контроль работает.
- [ ] **A14:** уведомления повторного события не спамят; переход открывает нужное актуальное действие после авторизации.
- [ ] **A15:** обновление APK сохраняет вход и данные; отключение/отзыв брокерского токена прекращает работу с ним и требует переподключения.
- [ ] **A16:** восстановление БД и ключей действительно проверено; токены и история не потеряны.
- [ ] **A17:** инструкции не являются торговыми поручениями; переход к точному выпуску проверен на физическом Android 15+.

## Контракт каждого функционального выпуска

1. Связать изменения с ID этого реестра и главного плана. Указать, какая часть
   завершена, что пользователь увидит и что остаётся. Обновить README и этот файл.
2. Зафиксировать проверяемые критерии и совместимость с действующим сервером.
   Пройти все применимые проверки последнего SHA, включая Sonar и проверки APK
   для изменений приложения. Не ослаблять проверки ради выпуска.
3. Для готового функционального обновления повысить `versionName` и `versionCode`
   относительно последнего опубликованного APK, включая выпуск серверной функции
   с совместимым клиентом. Сохранить `ru.omnicio.app.debug`, сертификат и данные
   установленной preview-линии. Новые байты не публикуются под прежним кодом версии.
4. Выпустить через существующий GitHub-процесс. Сейчас публикация GitHub Release
   включается маркером `[publish-apk]` в коммите `main` или ручным запуском
   `Android APK`; изменённые пути должны попадать под фильтры workflow.
   Простой merge документации не выпускает приложение.
5. Проверить чистую установку и обновление, подпись, SHA-256 и
   `apk-verification.json`. После загрузки скачать APK обратно и сверить байты.
   Для обновления тестировать последнюю доступную пользователю версию; в 0.7.5 проверен
   переход с 0.7.4. В 0.8.0 проверено обновление с опубликованной 0.7.6, в 0.9.0 — с 0.8.0, в 0.10.0 — с 0.9.0 на API 36 и чистая установка на API 35. Для следующего функционального выпуска эталон — опубликованный 0.10.0 / 34 на API 35 и 36.
6. Установить необходимые серверные изменения с совместимыми миграциями и планом
   возврата. Разместить **тот же APK** в канале обновления приложения на Timeweb,
   проверить версию, манифест, публичное HTTPS-чтение и SHA-256. GitHub Release
   сам по себе не подтверждает доступность через приложение.
7. Опубликовать понятные русские release notes: версия и ID плана, что разработано,
   где открыть, как обновиться, ограничения, оставшиеся части и способ восстановления.
   В итоговом сообщении владельцу дать ссылки. Не выдавать сборку за публикацию,
   а эмулятор — за успешную установку на его телефоне.

Текущий `repair-moscow-update-channel.yml` закреплён за конкретным APK 0.10.0 / 34.
Следующий выпуск должен явно обновить проверенные идентификаторы канала либо
использовать проверенный общий механизм публикации; нельзя считать, что старый
repair автоматически переключится на новый файл. Серверный отказ устаревшим
клиентам не включать до выполнения действующих условий проверки установленного
клиента. `ANDROID_UPDATES_ENABLED=false` отключает именно серверный enforcement;
Android продолжает проверять policy и его `minimum_version_code`.

Изменение только плана/документации фиксируется в GitHub без нового номера APK и
без заявления о новой функции. Это не отменяет обязательный новый APK для готового
функционального обновления. Не создавать фиктивный выпуск из прежнего файла.

Источники правил версий и выпусков:
[Android versioning](https://developer.android.com/studio/publish/versioning),
[GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).

## Журнал выпусков и решений

| Дата / версия | Что подтверждено | Доказательство / остаток |
| --- | --- | --- |
| 17.10.2026 · **0.10.0-preview / 34** | F01.4 / F22: столбчатая история сохранённой стоимости, выбор интервала, статистика потоков и Android 15+. APK опубликован, те же байты доставлены и независимо скачаны с Timeweb. | [Release](https://github.com/MishaGameHacking/omni-cio-gateway/releases/tag/android-preview-0a894dddfa858efe6c7be60aea78935adec84c1b), [проверка APK](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39042091615), [доставка #878](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39048187540). Установка/запуск preview и отдельный debug UI fixture проверены на API 35/36, обновление с 0.9.0 — на API 36. Физический телефон, установка через UI updater и новые инвестиционные алгоритмы не объявляются проверенными. |
| 17.10.2026 · **0.9.0-preview / 33** | F01.3: интерфейсная часть 100 UX-пунктов, локальные взаимодействия и явные состояния отсутствующих расчётов. Код, APK и доставка подтверждены. | [#873](https://github.com/MishaGameHacking/omni-cio-gateway/pull/873), [Release](https://github.com/MishaGameHacking/omni-cio-gateway/releases/tag/android-preview-a957e62dbf41af06be4a8f9c399e8f3745188344), [Timeweb](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39029899747). Шрифт 200%, темы, график, поиск и черновик проверены на эмуляторе Android 16. Физический телефон и новые инвестиционные алгоритмы остаются отдельными этапами. |
| 17.10.2026 · **0.8.0-preview / 32** | F01.2: новый визуальный каркас, навигация, оформление и отдельные рабочие пространства. Код и APK проверены. | [#870](https://github.com/MishaGameHacking/omni-cio-gateway/pull/870), [Release](https://github.com/MishaGameHacking/omni-cio-gateway/releases/tag/android-preview-7fe22f35b07bd2fc92b5860e23418214333b8a21). [Timeweb проверен](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39016326972); физический телефон не проверен. Инвестиционные алгоритмы и свободный чат остаются открытыми. |
| 16.10.2026 · **0.7.5-preview / 30** | F11.1: независимость фонового наблюдения от Android-сеанса/версии, проверка отключения подключения, фактическая свежесть данных в Android. Код, новый APK, сервер и канал подтверждены. | [#865](https://github.com/MishaGameHacking/omni-cio-gateway/pull/865), [Release](https://github.com/MishaGameHacking/omni-cio-gateway/releases/tag/android-preview-bb6638fab2188c718ccad4d8dd7b3ed76b34fdc8), [доставка](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/38963563889). Физический телефон не проверен; весь F11/F03 не закрыт. |
| 16.10.2026 · **0.7.4-preview / 29** | Опубликованный APK текущей исходной линии; Android 16+, проверка эмуляторной установки/обновления и восстановление канала завершились успешно. Это не выпуск новых инвестиционных возможностей данного плана. | [GitHub Release](https://github.com/MishaGameHacking/omni-cio-gateway/releases/tag/android-preview-ce5cbc190d2c875364716a6454f774bf543c2a08), [успешный запуск канала](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/38941112501). Рабочие настройки сервера, модели и телефон в этой сверке не обследованы. |
| 16.10.2026 · **план 1.0** | Владелец утвердил весь план как цель разработки; полный текст и исходный PDF сохранены, введены постоянные ID и открытые критерии, README и инструкции приведены к новой договорённости. | Изменение документации. Функции не добавлялись, APK остаётся 0.7.4-preview / 29. |

Для каждого следующего выпуска добавлять строку с PR/коммитом, версией APK,
ссылкой на Release и подтверждением канала/сервера. Закрытые пункты сохраняют
доказательства; новые прямые указания владельца записываются с датой и причиной.
Не поддерживать второй конкурирующий план в отдельной ветке или чате.


## F01.3 / UX100 — выпущен и доставлен 0.9.0 / 33

Интерфейсная часть 100 пунктов реализована: [карта и зависимости](UX100.md), [PR #873](https://github.com/MishaGameHacking/omni-cio-gateway/pull/873). [Release 0.9.0-preview / 33](https://github.com/MishaGameHacking/omni-cio-gateway/releases/tag/android-preview-a957e62dbf41af06be4a8f9c399e8f3745188344) опубликован 17.10.2026. [Проверка и публикация APK](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39027844102) прошла: установка, обновление с 0.8.0, запуск и UI на Android 16. [CI интерфейса](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39026729076): 365 Python gates, 24 UX-проверки debug probe, темы, черновик, график, поиск, возврат и крупный шрифт.

APK SHA-256: `32be82e640498010a0b61e073a6d82ec2237e766fac660058c447096445a1076`; размер 4331384 байт. Те же байты доставлены на Timeweb: health, локальный/публичный манифест, версия 33, размер и SHA-256 совпали. [Доставка #874](https://github.com/MishaGameHacking/omni-cio-gateway/pull/874), [проверка](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39029899747). [APK](https://176.98.178.81.sslip.io/client/apk/Analyst-AI-33-32be82e640498010a0b61e073a6d82ec2237e766fac660058c447096445a1076.apk?package_name=ru.omnicio.app.debug). Новые инвестиционные расчёты и чат остаются открытыми; физический телефон не проверен.


## F01.4 / F22 — 0.10.0 / 34 выпущен и доставлен

**0.10.0-preview / 34** опубликован 17.10.2026, 18:18 МСК, из
[`0a894dd`](https://github.com/MishaGameHacking/omni-cio-gateway/commit/0a894dddfa858efe6c7be60aea78935adec84c1b).
[Release](https://github.com/MishaGameHacking/omni-cio-gateway/releases/tag/android-preview-0a894dddfa858efe6c7be60aea78935adec84c1b) ·
[Проверка и публикация APK](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39042091615).
Android APK и SonarCloud этого точного SHA успешны. Исправлена ошибка проверки
сброса выбора графика, из-за которой предыдущая сборка main была красной.

- Нативные календарные столбцы, касание/горизонтальный выбор, точная подсказка, предыдущий/следующий столбец и сброс.
- Дневные, недельные, месячные и годовые интервалы по глубине истории; единственный снимок доступен сразу. Пропуски остаются пустыми.
- Минимум/максимум и изменение стоимости выбранного интервала; пополнения, выводы, купоны/дивиденды из существующего API, второстепенные операции под раскрытием.
- minSdk 35; compile/target 36. Опубликованный preview прошёл чистую установку и запуск на API 35 и 36, обновление с 0.9.0 и запуск после него на API 36. Предыдущий APK не поддерживал API 35, поэтому обновление с него на Android 15 не заявляется.
- Подтверждены подпись и прежний package `ru.omnicio.app.debug`, размер 4 347 764 байта,
  SHA-256 `3a31c602ec885a0d8cac8d76f43369cfb6ed3bdaa928f1cd7429582b0d5a40a3`.
- UI на API 35 и 36 проверен отдельным debug fixture с синтетическими данными;
  он не входит в опубликованный preview. Отчёт установки через ADB
  не подтверждает самостоятельную установку через экран обновления приложения.
- Доставка завершена: [PR #878](https://github.com/MishaGameHacking/omni-cio-gateway/pull/878),
  коммит [`c69bb1d`](https://github.com/MishaGameHacking/omni-cio-gateway/commit/c69bb1dfa083fc688eca4ae9d9955ff95f9c1602),
  [workflow](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39048187540).
  Перед слиянием прошли [Android CI](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39046210753)
  и SonarCloud точного PR SHA `21c25a45144bf1afc697c8ff748f3de0154e9d2c`.
  Workflow и launcher закреплены за опубликованными APK/report; обе контрольные
  суммы проверены до облачного доступа.
- Независимая публичная проверка 17.10.2026, 19:14:17 МСК: `/health` — `ok`,
  [манифест](https://176.98.178.81.sslip.io/client/update-policy?package_name=ru.omnicio.app.debug)
  — `0.10.0-preview`, версия/минимальная версия `34 / 34`, `min_sdk 35`, прежний сертификат.
  [Полный APK](https://176.98.178.81.sslip.io/client/apk/Analyst-AI-34-3a31c602ec885a0d8cac8d76f43369cfb6ed3bdaa928f1cd7429582b0d5a40a3.apk?package_name=ru.omnicio.app.debug)
  скачан по HTTPS: 4 347 764 байта и SHA-256 выше точно совпадают с GitHub Release.
  Подтверждён выпуск этого подэтапа F01.4 / F22.
- Физический телефон не проверен. Новые инвестиционные алгоритмы и чат остаются
  отдельными этапами; завершение графика не закрывает весь F01.

## Проверка на Timeweb 24.10.2026 — сборка 690811a5

F01/F16/F22/F23. На сервере Timeweb 9408159 завершены JVM (143 tests, 0 failures/errors/skips), lintDebug/lintPreview, assembleDebug/assembleRelease/assemblePreview и отдельный UI driver. Проверены meshes и native/ZIP alignment 16 KB, подпись исходным сертификатом, API37 и portrait обеих production-активностей. Preview APK SHA256: 71feb07dd0379a56ec25513194535a145bd5663dadc77611c50cdc442fccd27d. Проверка: GitHub transport run 40075308670, выполнение Gradle и verifier только на Timeweb. APK сохранён приватно на Timeweb; не опубликован. Полная runtime-матрица API37 4/16 KB, совместимое обновление и live backend/Telegram остаются открытыми. Сборка не является доказательством готовности приложения или зелёной ветки.

### Перенос первого облачного сервера в Санкт-Петербург — фактическая проверка 24.10.2026

Проверено 7 минимальных доступных в каталоге тарифов (1–2 vCPU, 1–2 GB RAM) во всех пяти зонах spb-1…spb-5: 35 отказов создания, коды no_free_node, preset_not_found и servers_is_run_out_error. Результат: новый сервер не создан, DNS не переключён, исходный сервер 9408159 и данные сохранены. Это внешний отказ ёмкости, не PASS развёртывания. Последняя проверка выделенного заказа 121673: installing, IP отсутствует; SSH/KVM и полная Android-матрица на нём ещё не проверены.

AI Gateway: одна новая запись ключа с лимитами 10 RUB/day и 30 RUB/month; оплачиваемые inference-запросы не выполнялись. Фактический GET /v1/models с сохранённым значением вернул HTTP401: выдано замаскированное значение вместо рабочего виртуального ключа. Авторизация ИИ и production-конфигурация остаются открытыми; секреты не публикуются.

## OWNER 24.10.2026 — Санкт-Петербург, последовательный подбор

Последнее прямое указание: конечное размещение приложения — Санкт-Петербург; начинать с минимального сервера и увеличивать конфигурацию только после отказа размещения. Оплата почасовая. Московский облачный сервер 9413003 создан до этого уточнения, данные туда не перенесены; после подготовки замены лишний пустой ресурс подлежит удалению. Все исходники, ключ подписи и проверенный APK сохраняются до проверки переноса. Предупреждение со скриншота относится к PHP; наличие проблемы проверяется по фактическому составу ПО, а исчезновение общего уведомления панели не объявляется результатом исправления сервера. Работа и проверки приложения остаются на Timeweb; GitHub — резервная копия и ранее разрешённый транспорт API/SSH.

## OWNER 24.10.2026 — окончательное размещение в Москве

Последнее указание владельца заменяет промежуточный выбор Санкт-Петербурга: подготовить нормальный минимально достаточный сервер приложения в Москве. Для первой попытки был выделен облачный сервер 9413003; актуальный рабочий сервер подготовки — 9413105 (см. результаты ниже). Исходная конфигурация: 1 vCPU / 1 ГБ RAM / 15 ГБ NVMe, 1 Гбит/с; тариф 1720 руб./месяц плюс публичный IPv4 с почасовыми списаниями. Минимальная классическая московская конфигурация ранее отклонена no_free_node. Запуск приложения не подтверждается одним созданием VM: требуются SSH, проверка фактических ресурсов, PHP/служб, защищённый перенос исходников и ключа подписи, затем живые проверки. Старый сервер 9408159 сохраняется до полной проверки переноса. Разработка остаётся на Timeweb, GitHub — резервная копия и разрешённый API/SSH-транспорт. Петербургские заказы прекращены; новых физических серверов не заказывать по предыдущему указанию.

## TIMEWEB 24.10.2026 — проверенный перенос в Москву

Текущий сервер приложения — 9413105, analyst-ai-msk-app-20261024-b, Москва (ru-3/msk-1), 201.24.52.66, 1 vCPU / 1 ГБ RAM / 15 ГБ NVMe. Выбран доступный минимальный профиль; базовый тариф 1720 руб./месяц плюс IPv4. Более дешёвый preset 4795 отклонён провайдером no_free_node. Исходники, APK и прежний ключ подписи перенесены: 1984 файлов, все SHA-256 совпали; секреты и расшифрование оставались на Timeweb. В архиве отсутствовали пустые каталоги refs Git; структура восстановлена, оба HEAD подтверждены. Проверки backend выполнялись в Москве на SHA 79be182168e21ae8248e0e0dfa6deb0abfbacbcf: 3034 тестов, 0 failures, 0 errors; syntax, compile, pip check, health/OpenAPI и проверка конфигурации установщика прошли. Это проверка изолированного backend, не запущенное личное приложение. Живая привязка владельца Telegram, DNS/TLS, рабочий AI-ключ, полный Android runtime 4/16 КиБ и выпуск остаются отдельными незавершёнными проверками. Из Москвы Telegram JWKS прошёл 4 из 6 прямых IPv4-проверок, со старого сервера — 6 из 6; неподтверждённая настройка gai.conf возвращена. Сервер 9413003 пуст и не является рабочим: его DELETE отклонён Timeweb HTTP 403, удаление не подтверждено. Старый 9408159 сохраняет исходные файлы и среду Android до завершения переноса среды сборки/готовности заказанного физического сервера. Новые серверы по предыдущим указаниям о Петербурге не заказывать. Разработка и проверки остаются в Timeweb; GitHub используется как резервная копия и ранее разрешённый API/SSH-транспорт. Приложение строго вертикальное; текущий APK не объявляется готовым к выпуску по одним unit-тестам.

## TIMEWEB 24.10.2026 — заключительная сверка DNS и ресурсов

Повторная полная инвентаризация: сервер 9413003 не подтверждён как удалённый: отсутствует в списке доступных VM, но отдельный GET ранее отклонён HTTP 403. Ранее DELETE получил 403; отсутствие в списке не доказывает удаление при запрете отдельного GET. Старый публичный IPv4 ещё присутствует. Текущая A-запись приложения: 201.34.146.244. DNS указывает на Москву: False. Backend и HTTPS не запускаются без штатной привязки реального владельца Telegram; проверки сети Telegram остаются 4/6, полный живой запуск не подтверждён.

## TIMEWEB 24.10.2026 — результат замены A-записи

Обновление существующей DNS-записи через документированный PATCH v2 вернуло HTTP 500. Выполнена попытка замены через POST новой A-записи; удаление прежней записи разрешено только после подтверждения новой. Фактические HTTP-результаты: POST=201, DELETE=204. Остальные DNS-записи сохранены. Только московский IP в DNS: True; резолвер московского сервера подтверждает новый IP: False. Старый адрес 81.200.158.176 проверен как свободный (resource_id=null); его наличие после отдельного запроса освобождения: False. Проверка старой VM 9413003 ранее запрещена HTTP 403 и не повторялась; этот результат не подменяется подтверждением удаления VM. Backend ещё не запущен, привязка владельца и HTTPS остаются за штатной интерактивной установкой.

## TIMEWEB 24.10.2026 — итог проверки DNS после смены адреса

После смены A-записи и очистки только локального DNS-кэша фактическое разрешение домена из Москвы: 201.34.146.244. Совпадение с 201.24.52.66: False. Это подтверждение DNS, не подтверждение HTTPS, привязки владельца или рабочего приложения.

## TIMEWEB 24.10.2026 — исправлен устаревший системный DNS

После смены A-записи Google DNS over HTTPS подтверждал 201.24.52.66, но системный resolver после очистки кэша продолжал возвращать 201.34.146.244. /etc/hosts не содержал переопределения. Оба рекурсивных DNS 8.8.8.8 и 8.8.4.4 предварительно проверены прямыми запросами с VM и вернули новый адрес. Постоянная настройка systemd-resolved перенесена в /etc/systemd/resolved.conf.d/80-analyst-working-dns.conf; старые файлы сохранены. Фактическое системное разрешение домена теперь 201.24.52.66; pypi.org, api.timeweb.cloud и oauth.telegram.org также разрешаются, resolved активен. Изменения DNSSEC/TLS-политик не вносились. Это не исправляет и не отменяет ранее подтверждённые TCP-тайм-ауты Telegram. Backend/HTTPS и привязка владельца пока не запущены.

## TIMEWEB 24.10.2026 — финальная настройка DNS

DNS изменился до применения дополнительной настройки resolver: это зафиксировано полем system_before=201.24.52.66 предыдущего отчёта, поэтому нельзя приписывать распространение записи только переключению DNS. Оба штатных DNS Timeweb проверены прямыми запросами: [{"server": "85.193.93.193", "answers": [{"address": "201.24.52.66", "ttl": 58}], "current": true}, {"server": "85.193.93.194", "answers": [{"address": "201.24.52.66", "ttl": 300}], "current": true}]. Возврат к штатным настройкам подтверждён: True. Итоговое системное разрешение: 201.24.52.66. Дополнительный override существует: False. Рабочий backend/HTTPS и реальная привязка владельца этим не подменяются.

## OWNER 24.10.2026 — очистка ресурсов и фактический статус обновления

Владелец потребовал оставить только ресурсы для разработки и запуска; вся разработка, сборка и проверки выполняются на Timeweb, GitHub используется для резервного копирования и ранее разрешённого API/SSH-транспорта. Постоянный сервер приложения: Москва, 9413105, 201.24.52.66, 1 CPU / 1 ГБ / 15 ГБ.

После проверки переноса исходников, исходного ключа подписи и APK дополнительно перенесены 103 файла Android outputs/test reports, 255205115 байт; все размеры и SHA-256 совпали. Старый NL сервер 9408159 удалён HTTP204, его IP 201.34.146.244 освобождён; оба отсутствуют в полных перечнях API. Оставлен заказ московского сервера 121673 для обязательных Android/KVM проверок; последняя проверка API: installing, IP ещё не назначен. Готовность оборудования и KVM не объявляется.

Установленный 0.10.0 /34 содержит прежний адрес 176.98.178.81.sslip.io; удаление прежнего сервера разорвало путь самостоятельного обновления. Нужен совместимый APK с проверенным новым origin, прежними package и подписью, установленный поверх существующей версии. Эталонный APK 0.10.0 сохранён на Timeweb для проверки обновления, SHA-256 3a31c602ec885a0d8cac8d76f43369cfb6ed3bdaa928f1cd7429582b0d5a40a3.

0.11.0-preview /35 собран на Timeweb, но не выпущен и пока содержит backend-not-configured.invalid. Не выдавать его за рабочее приложение. На head690811a5 Sonar и backend checks успешны; Android runtime run39993098373 завершился ошибкой Native cursor did not move within the unsent question в strategy/ready/font200. Сообщение общего helper относится здесь к полю горизонта стратегии. Без воспроизведения и полной матрицы API37/4096/16384 ошибка не считается исправленной. Реальный вход владельца, HTTPS, рабочий ключ AI Gateway и проверка телефона также не подтверждены.

В ходе инвентаризации диагностический run40088233675 ошибочно вывел приватные SSH-поля API Timeweb. Журнал удалён; SSH host keys обеих затронутых машин заменены, соединения с новыми закреплёнными ключами проверены, пароль root заблокирован и password/kbdinteractive login отключены. Ключ подписи APK не выводился и сохранён. Старый сервер затем удалён. Не выводить полные ответы projects/resources или servers: только явный список безопасных полей.

Актуальная проверка DNS/предварительной установки и Telegram: {"dns_ipv4": ["201.24.52.66"], "enrollment_preflight_passed": true, "telegram_jwks_probes": [{"attempt": 1, "curl_exit": 0, "valid_jwks": false}, {"attempt": 2, "curl_exit": 28, "valid_jwks": false}, {"attempt": 3, "curl_exit": 0, "valid_jwks": false}, {"attempt": 4, "curl_exit": 28, "valid_jwks": false}, {"attempt": 5, "curl_exit": 0, "valid_jwks": false}, {"attempt": 6, "curl_exit": 0, "valid_jwks": false}]}.

Сверка диагностики JWKS 24.10.2026: проверка принимает HTTP compression и ищет пригодный RSA/RS256 ключ среди опубликованных ключей, а не требует RSA у каждого элемента. Прежнее valid_jwks=false при успешном curl не доказывало отказ Telegram. Уточнённый результат: {"server_id": 9413105, "checked_at_utc": "2026-10-24T11:23:28.193701+00:00", "probes": [{"attempt": 1, "curl_exit": 28, "tls_http_ok": false, "usable_rs256_key": false}, {"attempt": 2, "curl_exit": 28, "tls_http_ok": false, "usable_rs256_key": false}, {"attempt": 3, "curl_exit": 0, "tls_http_ok": true, "usable_rs256_key": true, "key_types": ["EC", "OKP", "RSA"]}, {"attempt": 4, "curl_exit": 0, "tls_http_ok": true, "usable_rs256_key": true, "key_types": ["EC", "OKP", "RSA"]}, {"attempt": 5, "curl_exit": 28, "tls_http_ok": false, "usable_rs256_key": false}, {"attempt": 6, "curl_exit": 28, "tls_http_ok": false, "usable_rs256_key": false}], "successes": 2, "attempts": 6, "owner_login_tested": false}. Серверный код и проверки авторизации не ослаблялись.

Итог очистки и контроль маршрута 24.10.2026: {"checked_at_utc": "2026-10-24T11:34:10.892931+00:00", "cloud_server_ids": [9413105], "floating_ip_ids": ["40e88e4d-7807-4c99-80a3-f384db68e93a"], "builder": {"id": 121673, "name": "analyst-ai-msk-20261024", "status": "installing", "location": "ru-3", "ip": null, "autoinstall_ready": 0}, "project_resource_counts": {"mailboxes": 0, "routers": 0, "monitoring_alerts": 0, "dedicated_servers": 1, "apps": 0, "knowledgebases": 0, "buckets": 0, "databases": 0, "registries": 0, "monitorings": 0, "cdn": 0, "balancers": 0, "agents": 0, "floating_ips": 1, "clusters": 0, "domains": 1, "servers": 1, "network_drives": 0}, "temporary_addresses_removed_from_linux": true, "source_ip_change_fixed_telegram": false, "telegram_original_successes": 3, "telegram_alternative_successes": 2, "telegram_attempts_per_source": 6, "application_started": false, "working_apk_published": false}. Пробные IPv4 200.165.233.11 и 5.42.112.49 освобождены в Timeweb; второй был реально настроен в Linux для парного сравнения и затем удалён из ОС. Первое наблюдение без настройки ОС не было проверкой маршрута. Новые DNS/маршрут/платные адреса по неподтверждённой гипотезе не оставлены. Данные об ошибке курсора и необходимости реального входа владельца сохраняются; рабочий выпуск не объявляется.

Продолжение F01/F23 24.10.2026: на Timeweb 9413105 устранён недостаток диагностики подтверждённого Android-сбоя run39993098373 (strategy/ready;font=2.0, курсор до поворота). В рабочем дереве 690811a5 ожидание курсора использует существующую ограниченную диагностику без текста; исходный отказ не подавляется, ввод/ожидаемая позиция/портретная проверка не изменены. Два отрицательных сценария не проходили до исправления и проходят после. Общий запуск обнаружил отсутствие Node; на Timeweb установлены Node и JDK для существующих host-проверок. Результат: 962 тестов, 0 failures, 0 errors, 2 skips (реальные SDK-smoke требуют Android SDK; это не успех этих проверок). Журнал и хеши /root/analyst-caret-diagnostic-20261024/verification.json. Android runtime не запускался, сбой курсора ещё не исправлен и выпуск не разрешён результатом unit-тестов. APK не изменён. Полная матрица требует готовности Timeweb 121673; живой Telegram owner binding, доступный AI-ключ и новый Trusted Origin остаются незавершёнными.

Дополнение F01/F23 24.10.2026: на Timeweb 9413105 установлен минимальный SDK (platforms/android-37.0, build-tools/37.0.0, platform-tools; без emulator/system-images). Архив CLI проверен по SHA256 4e4c464f145a7512b57d088ac6c278c03c9eea610886b35a5e0804e74eedf583. Повторный полный запуск Python host-проверок: 962 тестов, failures=0, errors=0, skips=0; ранее пропущенные проверки настоящей криптографической подписи тестового APK и изолированного ADB выполнены. Подтверждение /root/analyst-caret-diagnostic-20261024/verification.json, all_scripts_with_sdk. Это не Android runtime матрица 4KB/16KB и не выпуск APK; контрольная версия 0.11 не изменена, реальный сбой strategy/ready;font=2.0 остаётся открытым.

F02/F23, 24.10.2026: OWNER прислал подтверждение нового Trusted Origin https://analyst-ai-2941515.twc1.net/ в BotFather (скриншот 15:22 МСК); этот шаг завершён. Частичная свежая установка на 9413105 остановилась до регистрации OWNER: enrollment_tls_probe_failed. Реальный журнал Caddy выявил HTTP 429 Let's Encrypt: общая квота 50 сертификатов на twc1.net за 168 часов, retry-after 2026-10-24 13:02:52 UTC (16:02:52 МСК). ZeroSSL также отказал на предварительной регистрации аккаунта. Дополнительные домены/серверы не покупались; настроена ограниченная повторная попытка после Retry-After. OWNER, backend.env, backend unit и пользовательская БД ещё не созданы. Подпись/JWKS и зависимости установленного backend проверены отдельно: {"reviewed_files": 66, "pip_check": 0, "pinned_keys_current": true}. APK не менялся; патч диагностики совпадает с резервной копией GitHub. Полный протокол root-private /root/analyst-owner-login-relay-20261024/auth-prerequisites.json. Эти проверки не подтверждают живой вход, работу ИИ или выпуск APK.

F01/F02/F22/F23, 24.10.2026, проверка обновления 0.10.0 → 0.11.0 на Timeweb (2026-10-24T13:36:47.370661+00:00). Подлинные APK 0.10.0-preview/34 и кандидат 0.11.0-preview/35 имеют одинаковый package ru.omnicio.app.debug и сертификат SHA256 bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1; обе подписи проверены apksigner из build-tools37. Это не результат runtime-обновления: текущий кандидат 71feb07dd0379a56ec25513194535a145bd5663dadc77611c50cdc442fccd27d по-прежнему содержит backend-not-configured.invalid, полная матрица текущих байтов не пройдена и APK не опубликован. HTTPS analyst-ai-2941515.twc1.net успешно выпущен и проверен внешне (run40096676667); прежний TLS rate limit устранён. Первый живой Telegram-вход прошёл проверку подписи и claims, но срок истёк до подтверждения OWNER; база/env/unit не были созданы. Пустая незавершённая установка сохранена в root-private архиве, сертификат не удалялся. Новый приватный вход проверяет совпадение с ранее верифицированным opaque subject; другой аккаунт не допускается. Текущее состояние контроллера: {"bound": false, "checked_at_utc": "2026-10-24T13:32:33.933388+00:00", "phase": "waiting_for_explicit_login_handoff", "server_id": 9413105}. Отдельный Московский Android-сервер121673 при последней API-проверке остаётся installing без IP; отсутствие его готовности не объявляется дефектом приложения или успешной матрицей. Правило строго вертикального интерфейса сохраняется. Секреты, ссылки входа и Telegram-идентификаторы не включены в эту резервную копию.

F01/F02/F22/F23, 24.10.2026: живой вход владельца завершён. На Timeweb9413105 сохранена root-only конфигурация подтверждённого Telegram OIDC subject, создана новая БД и запущен один analyst-ai-owner service под отдельным пользователем. Проверены локальные и внешние HTTPS-запросы: health200, workspace/me401 без сессии, прежний одноразовый owner callback410. Обычная страница Telegram-входа200 отдаёт no-store, same-origin-allow-popups и новый completion origin. Внешняя проверка run40100066145 и повторная проверка текущего запуска. Чувствительные идентификаторы и ссылки входа не публикуются. В Android-исходниках на Timeweb адрес backend-not-configured.invalid заменён на analyst-ai-2941515.twc1.net; старый хост и чужие origins не становятся fallback. Три Kotlin/JUnit проверки прошли после двух отказов с исходной заглушкой (run40101013444, Kotlin2.4.10/JDK17, ограниченный MemoryMax448MiB). Прямые Maven endpoints дали TLS timeout; те же JUnit4.13.2/Hamcrest1.3 загружены с документированного Google Cloud mirror и проверены по checksum. DiffSHA256 9a5cd88b474118a675c8c98f845d10ad665b5769e5f6ccb4ed2c0b93c58d6f02. Компиляция всего Android, обе runtime-матрицы, исправление курсора при font200, выпуск и установка нового APK остаются незавершёнными: прежний файл 71feb07d не пересобран и содержит старую заглушку. Подпись/package/versionCode35 и строгая вертикальная ориентация сохранены. Московский Android-сервер121673 всё ещё устанавливается провайдером без IP; в актуальном каталоге RU не нашлось preinstalled предложения, дополнительных заказов не делалось. AI credential configured=False: успешные health/авторизация не означают подключение ИИ или проверку портфеля. Прежние записи выше/ниже сохраняют историческое состояние на свои даты.

## OWNER 24.10.2026 — мощность по фактической потребности

Для всех ресурсов Timeweb выбирать необходимую производительность по измеренной
нагрузке и требованиям приложения, без избыточного запаса. Не выбирать тариф
только по минимальной цене и не заказывать более мощный без подтвержденной причины.
Это уточнение отменяет прежние ограничения региона: страна, город и тип ресурса
не фиксированы; выбирать их по доступности зависимостей, задержкам, надежности
и полной стоимости. Разработка и сборка остаются на Timeweb; GitHub — резервная
копия и уже разрешенный административный транспорт.

Последнее уточнение OWNER: запрещено создавать временные и дублирующие серверы.
Разработка, сборки, проверки и запуск выполняются на основных серверах проекта,
с изменениями существующих основных исходников. Уже созданные лишние машины
удалять после сохранения исходников, подписи, данных и проверенного результата.
При подтвержденной нехватке ресурсов менять конфигурацию основного сервера,
проверяя возможность обратного изменения, необходимость перезагрузки и полную
цену. Увеличение диска не считать обратимым. Запрет на новые серверы также
распространяется на скрытое создание VM, кластера или дублирующего окружения.

Разделять внутри основной инфраструктуры backend, данные и резервные копии,
сборки/проверки и оплачиваемые по запросам AI-вызовы. Для каждой платной сущности
нужны назначение, измерение потребности и условие завершения использования.
Проверять фактическое прекращение списаний; выключение не равно удалению.
100% постоянной загрузки не является целью: нужны приемлемые задержки,
отсутствие OOM/ошибок и мощность, обоснованная реальными измерениями.
Не обещать оплату VPS за фактический процент CPU при тарификации ресурсов
по времени. Менять размер после выявления узкого места; отдельные K8s,
балансировщик и БД добавлять только при доказанной необходимости.
Backend применять после проверки на основной установке; нативные изменения
Android доставлять новым APK. Правка исходника не меняет установленный APK.

## Ручная доставка APK 0.11.0 — 24.10.2026

По прямому уточнению OWNER APK собран и передан для самостоятельной установки.
0.11.0-preview /35, ru.omnicio.app.debug, Android17/API37, portrait.
SHA-256: bc2ca96b41a14433ff3f0bf085066728ec7ed6de904cb27ac5b960df515dbccc; размер 29869786 байт.
Сертификат: bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1.
Исходник 690811a5a376181990a64f37d914c87eb6c919b7, diff SHA-256 9a5cd88b474118a675c8c98f845d10ad665b5769e5f6ccb4ed2c0b93c58d6f02.
143 JVM-теста без ошибок/пропусков, lintPreview, 3D-ассеты, apksig,
zipalign -P16, ELF-выравнивание и portrait manifest прошли.
Новый адрес analyst-ai-2941515.twc1.net находится в DEX; заглушка отсутствует.
Публичный файл полностью скачан и сверен по SHA-256; /health=200,
/workspace без авторизации=401. Установка владельцем не подтверждена.
Полная UI-матрица 4KB/16KB, ошибка курсора при font200 и рабочий AI-ключ
остаются открытыми. Этот ручной preview не закрывает эти проверки.
URL: https://analyst-ai-2941515.twc1.net/client/apk/Analyst-AI-35-bc2ca96b41a14433ff3f0bf085066728ec7ed6de904cb27ac5b960df515dbccc.apk

## Ресурсы после доставки APK — 24.10.2026

Осталась основная VM 9413105: 1 vCPU / 1 GB RAM / 15 GB NVMe, один публичный IPv4.
Временная VM 9414007 и её отдельный IP удалены; отсутствие проверено в полном списке API.
Выделенный заказ 121673 отсутствует в API.
APK, подпись, исходники, доказательства сборки и 1 035 552 850 байт Gradle-кэша
сохранены на основной VM. Новые временные и дублирующие серверы запрещены OWNER.
Backend, данные, разработка и последующие сборки остаются в основной инфраструктуре.
Включён локальный сбор CPU/RAM/диска, состояния служб, OOM и health каждые 5 минут;
история ограничена 14 днями, отдельная платная служба мониторинга не заказана.
Текущие показатели — базовая нагрузка, а не доказательство прохождения 5-user пика.
При нехватке ресурсов для очередной сборки сначала проверить измерения и возможность
изменения существующей VM, обратимость, перезагрузку и полную стоимость; новые VM не создавать.
Нативные изменения Android требуют сборки и установки нового APK. Server-side изменения
применять после реальных проверок. Скачанный APK сам по себе не меняется от правки исходника.
