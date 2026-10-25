# Реальные проверки Android и выпуск через Timeweb — 25.10.2026

Все времена ниже — UTC. Основное рабочее место: Timeweb 9415007,
каталог /srv/analyst-ai/workspace, пользователь analyst-build.

## Требование владельца

Проверять работу приложения и его внешний вид в Android-эмуляторе на нашем
сервере; исправлять воспроизведённые проблемы, повторно проверять исправленный
APK и доставлять на телефон именно этот APK через сервер. Подтверждать
результаты журналами, настоящими снимками экрана и контрольными суммами.
Не считать успешную сборку, работающий backend или принятую версию клиента
результатом визуальной проверки.

Обычный выпуск сохраняет обязательные check, build и обе runtime-конфигурации
API37: 4096 и 16384 байт. Полный UI-контракт включает основные сценарии,
native input/caret, прокрутку, шрифт 100/200%, доступность и измерения ресурсов.
Новые native/UI изменения требуют подписанного APK. Серверные данные и
завершённые результаты передаются подключённому приложению существующим
live-механизмом.

## Проверенный фактический статус

| Часть | Результат |
| --- | --- |
| Личный backend, OTA и Caddy | Работают; HTTPS health и policy возвращают 200 |
| Подключение клиента | В 08:04:10 есть 1 действующая owner session; последний принятый запрос с versionCode 37 — 08:03:12 |
| Канал телефона | 0.12.1-preview / 37, APK 29 820 366 байт |
| Новый check после исправления pipeline | passed, 08:06:09–08:07:38 |
| API37/4096 с APK37 и предыдущим APK36 | Тайм-аут загрузки Android до установки APK |
| Новые Android screenshots | 0; внешний вид этим запуском не проверен |
| Полная Android-матрица для текущего нового source SHA | Не пройдена |
| Новый выпуск 38 или иной APK | Не собирался и не публиковался |

Принятая сервером версия — свидетельство авторизованного запроса с заголовками
package/version. Сервер не измеряет байты APK на физическом телефоне.
Не утверждать, что этим доказаны его установка, все экраны, брокер или AI.

## Неизменные входы реального прогона

- Исходники: aef6bb6dc89131b3c1412cc2b5454fc0aa6df68c6cae7e6abf82b379feb118a7.
- APK37: 1c91b77a8c86453b60ff2340723f3280f64b6e34769ecc984b4663499bb9aa74.
- Предыдущий APK36: c62c7bb9b2c0fd454ec00985f869f3f9fa3023ed555ced9b5e0ae2a107e7f8d2.
- Сертификат: bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1.
- Package: ru.omnicio.app.debug.

До запуска и после него все три SHA-256 совпали. Исходники во время Android
диагностики не менялись. После её завершения изменены только pipeline и его
тесты; source SHA нового check:
f51ca97441b4f2ea47695e1d298a192d7be1e27374944e563b292cc6c1494a64.
Сборочная квитанция прежнего source SHA не считается сборкой нового дерева.

## Реальный прогон 4096

Запуск 07:53:14.747, завершение 08:03:45.374, длительность 630.627 секунды.
Использован неизменённый штатный .github/scripts/test_apk_installation.py
с API37, page-bytes 4096, APK37 и previous36, RUN_PROFILE_UI_TESTS=1.
Отдельный runner держал workspace.lock, штатный harness — emulator lease.
Собственные ADB и процессы запуска не разделялись с production.

Итог: leaf_failed, TimeoutError: Emulator boot deadline exceeded.
Загрузка не уложилась в штатные 600 секунд. Оба install-results.json содержат
пустой список; установка кандидата и UI-сценарии не начались. Оставшихся
процессов этого запуска — 0; его временный AVD удалён штатным cleanup.
Никакой успешный runtime-result.json не создавался и не подменялся.

Каталог оригиналов на Timeweb:
/var/lib/analyst-ai-build/diagnostics/leaf37-4096-20261025T075314Z-8865.

Копии фактических файлов находятся рядом с этим отчётом:
[журналы и замеры](evidence/android-api37-4096-20261025).
Runner сохранён как текст исторического запуска; он не является новой
обычной командой выпуска и не обходит общую матрицу.

[Журнал получения результата](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40175094464).
[Применение исправлений](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40175243720).
[Проверки исправлений](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40175362169).

Предыдущая отдельная диагностика штатного Android API37/16384 тоже не завершила
загрузку за 1800 секунд. Она не устанавливала APK. Старый обычный runtime для
предыдущих исходников также завершался boot timeout на 16384. Эти наблюдения
не являются выполненной матрицей APK37.

## Измерения среды

Сервер: 4 vCPU, MemTotal 6065984 KiB, диск 30 ГБ. /dev/kvm отсутствует;
vmx и svm процессору VM не представлены. emulator -accel-check возвращает 3:
KVM requires a CPU that supports vmx or svm.

Emulator 37.2.12, штатные образы API37 Google APIs x86_64, revision 7.
Headless emulator -no-window -version работает. Отсутствующая libXi.so.6
была предупреждением GUI-вызова emulator -version; непроверенная установка
библиотек не выполнялась.

| Измерение текущего 4096 запуска | Значение |
| --- | --- |
| Число замеров | 66 |
| CPU за 630.624 с наблюдения | 669.001841 с |
| Квотный CPU throttling | 0 с |
| Пик cgroup memory | 5 035 253 760 байт |
| MemoryHigh / MemoryMax | 5 033 164 800 / 5 452 595 200 байт |
| memory.high events | 481, впервые на 480.282 с |
| memory.max / OOM / OOM kill | 0 / 0 / 0 |
| cgroup swap | 0 |
| Приращение memory.pressure some total | 454586 мкс |
| Минимальный MemAvailable хоста | 1 530 884 KiB |

Отсутствие OOM не доказывает достаточность памяти. Измеренное суммарное давление
памяти мало относительно длительности прогона, но эти данные не доказывают,
что увеличение RAM или иной лимит обеспечат загрузку/прохождение UI. Не покупать
ресурсы и не изменять тестовые пороги на основании такого предположения.

В начале очистка только скачанного apt-cache освободила место; свободно стало
10 966 712 320 байт, и штатный runtime capacity guard прошёл. Установленные
пакеты, APK и старые доказательства не удалялись.

Android документирует Linux KVM и процессорные расширения как основу ускорения;
режим -accel off описан как очень медленный и неподдерживаемый.
В этой ограниченной диагностике использовался явный ANDROID_I_WANT_MY_TCG=yes.
Это не превращает TCG в подтверждённое рабочее окружение обычного выпуска.

- [Android: hardware acceleration](https://developer.android.com/studio/run/emulator-acceleration).
- [Android: command-line options](https://developer.android.com/studio/run/emulator-commandline).
- [Linux: nested KVM и передача CPU capabilities](https://docs.kernel.org/virt/kvm/x86/running-nested-guests.html).
- [Timeweb: конфигурация существующего сервера](https://timeweb.cloud/docs/cloud-servers/manage-servers/server-configuration).
- [Официальный Timeweb UpdateServerConfigurator](https://github.com/timeweb-cloud/sdk-go/blob/main/docs/UpdateServerConfigurator.md).

В проверенной документации конфигуратора Timeweb есть cpu/ram/disk/gpu, но нет
поля nested virtualization или CPU passthrough. Не найден документированный
самостоятельный способ включить VMX/SVM для существующей 9415007.
Это не утверждение, что провайдер технически не может помочь. Неизвестным
остаётся, может ли он включить nested/передачу CPU-флагов либо перенести именно
эту VM на подходящий физический узел с сохранением диска, адреса и данных.
Новые VM и обращения к поддержке этим этапом не создавались.

## Подтверждённые исправления pipeline

1. Publisher раньше писал в /var/lib/analyst-ai/releases, а публичная служба
   читала /srv/analyst-ai-ota/releases. Теперь используется один фиксированный
   каталог; тест сверяет его с deploy/public_updates.service.
2. Убран общий chown/chmod 0640 после публикации. Он мог запретить DynamicUser
   analyst-updates читать следующий релиз. Core publisher оставляет собственные
   APK/manifest 0644, private lock 0600; чужие файлы не изменяет.
3. Вместо постоянного previous 0.10.0/34 используется проверенный текущий
   публичный APK. Сертификат, package, actual bytes, SHA и возрастание версии
   проверяются. Перед обоими реальными профилями сверяются bytes baseline.
4. В обеих install-results требуется настоящий успешный previous_clean_install
   с тем же SHA. В runtime receipt сохраняется baseline; смена текущего канала
   до публикации останавливает выпуск.
5. Publisher получил main guard для безопасного тестирования без публикации
   при импорте. Остальные source/build/runtime/signature/monotonic guards
   сохранены.

Временные синтетические файлы используются только в unit regression tests.
Они не являются реальными Android receipts. Отдельно новая проверка прочитала
действительный опубликованный APK37 от analyst-build и сверила публичные
права, версию, SHA и сертификат.

## Выполненные проверки исправлений

Штатный check: **passed**, 08:06:09–08:07:38,
каталог /var/lib/analyst-ai-build/runs/20261025T080609Z-check.

- diff-check и зависимости — passed;
- Python source audit — 345 файлов, ошибок 0;
- workspace/publisher guards — 12 tests passed;
- host tooling — 974 tests passed;
- tools — 52 tests passed;
- Node — 61 tests passed;
- backend — 1584 tests и 1481 subtests passed.

Всего 2683 tests, отдельно 1481 subtests. Одно существующее предупреждение
deprecation в зависимости Starlette/AnyIO; failures нет.
Это проверка pipeline/backend/tooling, не новый Android build и не UI runtime.

## Подключение приложения и текущая доставка

Read-only SQL от 08:04:10 использовал INTEGER Unix epoch и считал sessions
непосредственно, а не исключал их join по device. Результат: одна действующая
owner session, одна device registration, одна принятая запись version37.
Последний принятый запрос — 08:03:12. Owner identifiers/tokens не выгружались.

В раннем мониторинге ISO-строки ошибочно сравнивались с INTEGER timestamp.
Его нулевые session counts нельзя использовать как доказательство отсутствия
подключения. Исправлена только проверка состояния; production БД не правилась.

Policy продолжает возвращать 37 и прежний точный APK SHA. Публикация 37 была
ранее отдельно разрешённым тестовым исключением до полной матрицы. Это не
разрешение следующего непроверенного APK.

[Скачать текущий APK37](https://analyst-ai-2941515.twc1.net/client/apk/Analyst-AI-37-1c91b77a8c86453b60ff2340723f3280f64b6e34769ecc984b4663499bb9aa74.apk?package_name=ru.omnicio.app.debug).

Автоматическая попытка APK-update версии37 происходит при открытом приложении
и разрешённой установке. Android может потребовать действие пользователя;
полностью бесшумное обновление при закрытом приложении не подтверждено.
[Контракт PackageInstaller](https://developer.android.com/reference/android/content/pm/PackageInstaller.SessionParams#setRequireUserAction(int)).

## Оставшийся следующий шаг

Нужно обеспечить фактически работающий Android runtime на этом Timeweb —
подтверждённый KVM/CPU passthrough или другое доказанно подходящее согласованное
окружение. Не повторять те же boot timeouts наугад. После устранения блока:
новый candidate с versionCode >37, свежий check/build, оба настоящих Android
профиля, просмотр фактических PNG и повторная проверка воспроизведённых
дефектов; затем обычная публикация проверенных байтов и серверное наблюдение
версии клиента. До этого новая полностью проверенная версия не заявляется.
