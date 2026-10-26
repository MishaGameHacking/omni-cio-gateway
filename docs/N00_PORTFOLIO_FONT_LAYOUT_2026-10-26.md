# N00 — исправление портфеля при увеличенном шрифте

N00 открыт. N01–N11 не реализованы. Опубликованный канал APK38 сохранён.
Кандидат42 /0.13.4-preview пока не опубликован; физический телефон не проверен.
Этот checkpoint продолжает [проверки досье и истории](N00_RATING_FOLDS_2026-10-26.md).

## Исходные проверки кандидата42 и измеренная навигация

На исходниках c2d572e992516ed3080a22582e926754fb61262d, inventory
cd798608db48de57f6a01e15293fda8fe093984054edfeeea0e0e210936c8f2e,
использованы точные APK42 из успешного build40266100999.
Оригинальный focused [40267647899](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40267647899)
наomni-cio-ci завершился FAILED после install/upgrade38→42/clean/launch:
discovery/ready/font100 — Native action geometry or enabled state did not settle:
«Сравнить (2/3)». Runtime04:10:42.213011Z–04:13:49.417434Z.
Архив32files /276421bytes SHA256
7b5b786851cc14ed423b450fd80c27623ff9bd7a6b5a866bd464618bb7d16c79
принят9417611 в04:15:09.9951721Z. Evidence40268183002:
artifact12627172643 /81675bytes SHA256
fd68caeee8bc1ae3cf02647389b63683a8cb46eaf1f19b9f588ba05c8f5a6a40,
проверены5 identities, PNG просмотрен. ВыбранаSYN-B, tray сравнения выше списка.

Затем диагностический [40268185222](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40268185222)
наomni-cio-ci-4, измеренные16384-byte pages, завершил все14 исходных
независимых сценариев:6 PASS/8 FAIL. Runtime04:16:41.321333Z–04:24:35.355537Z.
Обработчики и assertions исходные; продолжение после каждой ошибки
НЕ является PASS исходного fail-fast suite. release_gate_pass=false,
portfolio_cases_complete=false. Архив110files /3141426bytes SHA256
8e28dad8a6d3ebf5d509ea9f7687391b89a44f5981f1fdc5c0f902556fc62996
получен9417611 в04:26:12.2926267Z. Все job завершены, cleanup PASS.

| Сценарий42 | Font100 | Font200 |
| --- | --- | --- |
| discovery/ready | «Сравнить (2/3)» вне текущего viewport | действие первойSYN-A ниже длинной карточки |
| dossier/ready | PASS | возврат к«Как менялся рейтинг» не завершён |
| history/ready | выбранная901,75₽ выше графика | «Движение денег» ниже текущего раздела |
| history/partial | PASS | PASS |
| quotes/ready | «Предыдущая» выше позиции после сброса | та же ошибка направления |
| markets/ready | PASS | PASS |
| appearance/ready | PASS | сброс ниже длинного списка настроек |

[Evidence40269082850](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40269082850):
artifact12626659272 /598674bytes SHA256
445f6faeb59e4e6e68dff141a0b46a3b7f83ffd9022e2f964633ad97f92ad235,
проверены23 identities, все8 failure PNG просмотрены.
Клавиатура отсутствовала во всех8 отказах.
Приfont200 видимые viewport: discovery215px, dossier/quotes236px,
history157px, appearance401px. Они не заменяют проверку целей и точных данных.

Отдельная неизменная история [40270073435](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40270073435)
наomni-cio-ci-2 сохранила исходный отказ901,75₽ и до/после кадры.
Runtime04:38:41.618387Z–04:41:47.357530Z, источник/APK не менялись.
Нативный tooltip«Выбранный интервал:2026-10-22—2026-10-22» имел лишь
[62,198][286,206] —8px у верхней границы. Число находилось выше viewport.
При обратной прокрутке тот же tooltip стал[62,324][286,374], его дочернее
число901,75₽ —[74,347][138,366]. Исходная ошибка не заменялась этим наблюдением.
Архив54files /777152bytes SHA256
8f419bc3b4b08a1e6909464f0176adaefb0684d314d02a2288c4391991892295
принят9417611 в04:43:07.9235876Z.
[Evidence40270560034](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40270560034):
artifact12628496006 /280077bytes SHA256
c8d2aa7994d11e3a10839011f076363b9d733d47e5abb965df4dc6b74622523b;
проверены14 identities, исходный clipped и восстановленный tooltip PNG просмотрены.

Подготовлен ремонт только Python-проверок; APK42 не меняется.
Выбор сравнения привязан к account+UID и тикеру конкретной карточки; возврат
проходит через те же записи и видимый scope поиска. История рейтинга возвращается
через точные датированные записи. Настройки и cashflow проходят через реальные
заголовки. «Предыдущая» после сброса ищется назад. Tooltip истории ищется выше
графика, а сумма дополнительно проверяется внутри единственного выбранного
интервала; совпадение суммы в постороннем узле не принимается.
48px, font100/font200, IDs, значения, даты, источники и исходные сценарии сохранены.

Первый Windows [40270824697](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40270824697)
наomni-cio-ci-4 применил6 файлов, inventory
76aef6e3aba2f5299763688515b6db3cf2420a000f852bfc7ed8f0dfd3603b64,
patch5820015948b7e8cbe1d7613702e1b021142065349a9ff7a9264e8afbe4dff475.
Все4 отдельные регрессии воспроизвели исходные ошибки — по2 условных варианта;
diff-check PASS. Общий host suite:1081 tests /69.149s,
5 failures (прежние3 skips), finished04:49:04.383954Z.
Четыре отказа — старая модель test_history_chart_traversal размещала число
соседом tooltip, хотя измеренный Android вкладывает его внутрь semantic parent.
Пятый — условная модель сравнения уже показывала«Снять выбор», но требовала
дополнительную прокрутку. Нативные guards не ослаблялись; Android не запускался.
Архив14files /78961bytes SHA256
93310bc00b1e10484f363d8eb88f0a0c7d7d4d23dad5c18395a8351ec6f78066
принят9417611 в04:50:10.7363505Z.

Условные модели исправлены по измеренной структуре и заданному сценарию:
число дочернее точному интервалу; кнопка очистки в модели действительно
начинается вне viewport. Прежние assertions выбора/даты/тапа сохранены.
Семифайловый patchd1a42af907aadb5a64b9a6a12465ee0d9e60f2940b7712beb555525b095907d1
проверен на Windows в [40271124381](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40271124381),
triggerd8663f0fdfa01346ff6b5efdba12771de06d04d7, runneromni-cio-ci-3.
Все4 исходные регрессии вновь доказаны по2 условных варианта.
Все1081 host tests прошли за75.171s (прежние3 skips), diff-check PASS,
finished04:52:42.533399Z. Новый source inventory
5d2cd2b6f8c8d7fbec7276835634ed4cb701d2e80809cc67a59c066a692cc76b.
Все7 применённых файлов сверены поSHA с точным проверенным transport.
Исходные14 portfolio cases выполняются; их PASS пока не заявляется.
Изменён только harness, APK42 и подпись сохранены.



## Продолжение после ремонта навигации42

Run40271124381 завершился FAILED только после успешных1081 host tests.
Runtime04:52:45.540706Z–04:58:23.456834Z; Android37, фактические16384-byte pages.
Install/upgrade38→42/clean/launch PASS. Исходные discovery/ready, dossier/ready,
history/ready и history/partial приfont100 прошли; quotes/ready остановился на
«Candle interval did not acquire its actual native selected state».
Остальные случаи исходного fail-fast suite не выполнялись.
Архив62files /1846818bytes SHA256
b8566a2fc08797b709ea172d89032cf02174bc6b42c6846a93bfd3f16654b264
принят9417611 в04:59:07.4702487Z, cleanup PASS.

[Evidence40271951745](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40271951745):
artifact12628393679 /865571bytes SHA256
44553a7fc0955cfc04af62f163e2b5208d3e27a30b401a843016a9099976b8d5,
все22 identities проверены; failure PNG и XML просмотрены.
На экране выбранная«Неделя» и точная ошибка недельного источника.
Native quotes-intervals-item-2:[137,319][210,371], selected=true,
clickable=false, enabled=true. Это успешный выбор: текущий detector ошибочно
требуетclickable=true и после нажатия. checked/checkable здесьfalse;
не подменять выбранное состояние только подписью или checked.

Подготовленный двухфайловый ремонт разделяет action и selected observation:
перед тапом остаётсяclickable=true, после —selected=true внутри того же rail,
с прежними48px, видимостью и дополнительным enabled guard. Новые условные тесты
требуют один тап и отклоняют отсутствующее/постороннее/disabled selected state.
Patch02737e718f6d48d0487a94267ebd232e1af739afc481ac3eee104be1495f85a9
пока НЕ проверен и не входит в рабочие исходники; отправлен Windows trigger
5579a4b6ef7b1c15138a5e7de74ed66980264378. Тяжёлые этапы ждут общей lease.

Диагностический [40271927516](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40271927516)
на исходниках14153157fb21456fe9edc8597d4cf2256fe116a4 /inventory5d2cd2b6…
выполняет все14 независимых оригинальных случаев с семифайловым проверенным
ремонтом; ошибки собираются отдельно, release_gate_pass=false неизменно.
Не выдавать этот run за исходную полную приёмку. Полный wrapper3bee07c1…
подготовлен с этой же версией harness, но НЕ запущен; после следующего
проверенного изменения harness его source pin потребуется обновить.

## Что установлено на точном APK41

Диагностика [40262170820](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40262170820)
выполнена на LAPTOP-NPSGA016 /omni-cio-ci-2, Android37 с измеренными16384-byte pages,
с исходниками d5a5763fbd85ab2d2c1a9f1734ce24a5083a739e,
inventory dd762dde5a301bf972cc72794171ea3e3f0e04a3751ddaf833d0a0f003ed2066.
Применялись неизменные APK41 из build40252011635 и baseline38.
Время:2026-10-26T03:04:18.762887Z–03:11:48.380102Z.

Выполнены все14 исходных независимых portfolio cases:6 прошли,8 не прошли.
Диагностическая административная оболочка сохраняла исходные обработчики,
нативные проверки, размеры целей, font scale и assertions, но продолжала
после ошибки каждого случая. Это НЕ PASS исходного fail-fast suite:
release_gate_pass=false, portfolio_cases_complete=false,
original_fail_fast_suite_passed=false. Копия исходной функции закреплена SHA256
b75af4a166b2a446150e14516bc067ca2345f67b4b7869d4651e426fa78c080c.

| Сценарий | Font100 | Font200 |
| --- | --- | --- |
| discovery/ready | PASS | profile-tabs отсутствуют в видимой раскладке |
| dossier/ready | PASS | instrument-context-events недостижим |
| history/ready | PASS | точное наблюдение по ссылке недостижимо |
| history/partial | PASS | точное наблюдение по ссылке недостижимо |
| quotes/ready | кнопка «Следующая» недостижима | profile-tabs отсутствуют в видимой раскладке |
| markets/ready | PASS | обновление расписания недостижимо |
| appearance/ready | PASS | сброс оформления недостижим |

PASS досье включает рейтинги, отчёты, факт→компанию→точную позицию счёта B
и неотправленный вопрос по событию. PASS истории включает настоящий checked/
checkable выбранной закрывающей строки, точные дату/сумму, zero/negative/missing,
две нативные перетяжки периода и контекст ассистента.

Архив100files /3138163bytes SHA256
778cb69fe23a240d6fc9a759b4593276107b210dd91fed8504910719e61d58ab
получен runtime9417611 в03:13:07.6298805Z.
[Evidence40262990495](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40262990495):
artifact12624992698 /750535bytes SHA256
8db9d6c466847835b2170b3a4584200b0f260eb86c2f9915f740fac69e2b9455;
проверены все26 identities. Все восемь failure PNG просмотрены.
Приfont200 фиксированные заголовки поиска/бумаги занимали высоту вкладок,
название счёта переносилось на четыре строки; в истории для списка оставалось
52px ([0,434][320,486]). Панель действий открывалась частично с y320.

## Дополнительные измерения

[40263933755](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40263933755)
повторил исходный quotes/ready/font100 на том же source/APK41, затем выполнил
ограниченную обратную инспекцию без подмены ошибки. SHA wrapper
8e5d25802edabba5d0d41376fb225b90761b8c225afb26e375101a555c4a28ab;
hook88965b0c6dd8df920501c9b5a2f59e8fc53e7cefe66d1be490510e2df0b93a3b.
Два первых click owner имели ширины128/84px и частично обрезанную высоту15px;
отдельная нативная цель «Следующая» не найдена. PNG показывает третью кнопку
в узкой вертикальной полосе. Полная ширина её native owner не измерена.
Архив26files /318089bytes SHA256
67b67b9085bbf203696e4172238597897609ff4d1bc32ca2078c57e2edaa637c
получен9417611 в03:29:10.7226948Z.
[Evidence40265363270](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40265363270):
artifact12625858324 /119271bytes SHA256
b48b32385db81a3a384a70962cb88d495152d5d86bb6a78511f1d860db203708;
все6 identities проверены, оба PNG просмотрены.
Первый read-only collector40265246681 честно FAILED: ожидал отсутствующий
portfolio-verification.json после аварийного завершения случая. Исправлена
только выборка существующих failure evidence.

Предыдущий40261499076 прошёл1075 host tests, но Android остановился до истории
на переходе к эмитенту. Evidence40262204269 /artifact12624956375 проверено:
на вкладке компании окно было всего101px, issuer находился НИЖЕ, тогда как
проверка ошибочно искала его только обратной прокруткой. Нативная команда
прокрутки не доказывает физическое перетаскивание самой панели.
Последующий полный диагностический scan доказал history repair наfont100.

## Кандидат42

Подготовлены15 файлов от d5a5763; все изменения применяются и исполняются
только в отдельном checkout на Windows-ноутбуке:

- Поиск, рынки и оформление используют существующий компактный режим при
  недостатке высоты; полный заголовок перенесён внутрь прокручиваемой области.
- Каталог и сравнение в поиске находятся в LazyColumn, освобождая вкладки.
- Приfont200 переключатель счёта допускает горизонтальную прокрутку полного
  имени; кнопка возврата получила иконку с прежней accessibility-меткой.
- Экран бумаги сохраняет полный контекст счёта/компании в списке и использует
  компактную боковую кнопку возврата; безопасные insets учитываются один раз.
- Панели действий/факта сразу открываются полностью.
- Кнопки котировок используют перенос строк без сжатия текста/целей.
- Проверка перехода к эмитенту сначала находит общий заголовок, затем ищет
  эмитента вперёд. Новый тест воспроизводит короткие окна101/140px и точный
  переход к позиции счёта B.
- Версия42 /0.13.4 и две проверки версии обновлены согласованно.

Порог48px, font scale, синтетический banner, ограничения прокрутки, exact-ID/
account/date/value, owner/session/broker contracts и канонический lease не
ослаблялись. Изменения приложения не исполнялись на Timeweb или cloud Linux.

### Проверки сборки42

Повторный40265186363 наomni-cio-ci-4 применил15 файлов и получил inventory
6025e9bf286b253361d894fc421bbefcfa0b40c7fd1364be470d11a68ce3589d.
1076 host tests прошли за50.694s (прежние3 skips); WSL Ubuntu24.04:
1684 tests +1515 subtests passed за122.12s. Сборка FAILED на отсутствующем
импорте SpectrumIconButton вPortfolioScreen.kt:254 (debug/preview Kotlin).
Ошибки не заменены PASS. Архив950files /7664721bytes SHA256
fe913dfcc4a581ba9c757303165d5045f19cfb399606d65e3a6fba3dea1f0dcd
сохранён9417611; read-only40266255098 проверил SHA архива и identities
оригинальных журналов, не исполняя исходники. Artifact12625994205 /
81912bytes SHA256298f5cf9f7ae4222c9877eaf279647f14f4d074fa3313b819655a1ba6a4d585b.

Импорт добавлен в подготовленный15-file пакет. PortfolioScreen.kt теперь
25385bytes SHA25682c1d47e88c51e7e529a76ba69c97ae3f0496ee747b42351b0dd2a720a5a21b1.
Patch SHA2566dd954f226dd3b906cd2c16498f2395cf84f786d2ec68af8f6fbfc84a6a3ec0b.
Повторный полный Windows/WSL/Android run
[40266100999](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40266100999)
успешно завершён наomni-cio-ci-3, inventory
cd798608db48de57f6a01e15293fda8fe093984054edfeeea0e0e210936c8f2e.
Check/build SUCCESS, finished2026-10-26T04:06:14.197032Z.
1076 host tests /50.286s (прежние3 skips), tools/Node/source-audit/dependencies/diff
PASS. WSL1684 tests +1515 subtests /124.44s; реальныйJUnit3199 cases,
0 failures/errors/skips. Health/OpenAPI PASS.
Gradle10m3s /197 executed tasks: debug unit tests, debug/preview lint,
debug/release/preview assemble, driver lint/assemble, assets/native alignment PASS.
Независимый Windows [proof40267432826](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40267432826)
пересчитал полный inventory и19 identities (15 файлов и4 APK).
Реальные Android XML:174 tests /30 suites,0 failures/errors/skips.
Ключ не менялся; certificate SHA256
bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1.
Owned worker processes после завершения:0.
External quality gate: not_run_by_this_bootstrap.

| APK | Bytes | SHA256 |
| --- | ---: | --- |
| preview42 | 29771254 | b0b18508e80f763edb0d54dc9aa077462fca0163168d8f5c4ca6a5e7c2f91a0c |
| debug42 | 63292529 | b7a883b22c5fd3f53178862733c92b6dbcebbca10aecde6f2d4bbba15deb551b |
| unsigned release42 | 29763042 | 3785d8b22b22a462867b4581762dee17500be7aa32d8c74a9e033d4a2beff998 |
| test driver | 2683192 | 7fb9ad4121c2a1e981cacc611522941122c9fe3178e2eeb3849683200f3c7705 |

Архив1036files /68845185bytes SHA256
c7456f981f618f900906b05d26c6c78552b69a8563bfcefd77625225b58ec185
принят9417611 в04:07:15.8875303Z.
Отдельный build artifact12626721909 /85489bytes SHA256
fbc0126caa3cb59c51af525e0a20e58da6e3df43d3777cb858fe14f3ed0d8570
скачан и проверен; все15 применённых SHA совпали с transport.
Proof artifact12627071833 /3638bytes SHA256
57edffec486ea811ba9296974ff65ede9f30f75e09f1cdde490949ea088d5598.

Старые read-only40265885163/первый proof не смогли прочитать уже очищенный
runner temp. Для нового build добавлено сохранение ограниченного набора
синтетических JSON/host/WSL/Gradle журналов до очистки; archive transfer и
контроль исходников сохранены. Полные сведения прошлой ошибки восстановлены
из точного архива, а не пересозданы.

Первый [40265060473](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40265060473)
остановился ДО применения файлов: transport содержал base_commit вместо
обязательного reference_commit. Строгий guard wrong_patch_base сохранён;
исправлен ключ пакета, добавлена административная проверка перед упаковкой.
Источник остался dd762dde…. Архив919files /7455656bytes SHA256
17bad0c7c9ff864f9d09de8abb2fffee679aed8321f1a3cc4fe6907c3e6e0c90
получен9417611 в03:40:11.6669457Z.

Исправленный patch SHA256
15432c90bd814b076cefea6c03232f196d4e71ea5a4353517d3a41d299171760.
Неизменный bootstrap SHA256
986cebe48cf4d499aa71d12a491a595bfcaa279adf2cc191b38cd994636bf02d.
Canonical emulator lease blob c9626f3bf90b612a71b9bbf2954d0c134aa29b22,
ожидание1200s, общий lock не удаляется.

## Продолжение по порядку

Сборка42 и новый Python-harness подтверждены; исходные14 portfolio cases
в40271124381 остановились на selected-state котировок после4 PASS/font100.
All14 diagnostic40271927516 выполняется; новый quote-state patch ожидает проверки.
Полная15-stage матрица4096/16384 для42
пока НЕ пройдена. После исходных14 PASS подготовить новый full wrapper с
проверенным harness/inventory5d2cd2b6…, сохранив точные APK42 и baseline38.

1. На точном подписанном APK42 пройти исходные14 portfolio cases,
   затем полную исходную15-stage матрицу Android37 на4096/16384.
   Старые wrappers дляAPK40/41 нельзя использовать как доказательство42.
2. Завершить перенос normal backend/android CI на ноутбук без потери required
   checks; baseline должен оставаться точным опубликованным38.
3. Получить внешний exact-head Sonar и остальные обязательные подтверждения N00.
4. Только после закрытия N00 переходить кN01, затемN02–N11 в порядке исходного
   [плана](AUTONOMOUS_PORTFOLIO_2026-10-25.md).
   N10 требует минимум30 торговых сессий теневого режима; код/симуляция их не заменяют.

Нет PR/merge/main update, публикации42 или заявления о полном завершении.
