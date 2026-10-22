# Выполнение главного плана Analyst AI

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
