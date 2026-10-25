# Подготовка ноутбука — 25.10.2026

Область N00/F23. Это настройка машины разработки, не релиз приложения.

## Проверено

25.10.2026, 23:09 МСК: Git, Python launcher, Node, Java, PowerShell и WSL доступны. Под служебной учётной записью есть Ubuntu-24.04. Общий Android SDK содержит adb, emulator, android-37.0 и build-tools/37.0.0. Четыре runner-службы Running/Auto под NETWORK SERVICE. Свободно около 78,5 ГБ; сон и гибернация от сети уже отключены. Административного токена у службы нет; задачи AnalystAI для перезагрузки ещё не было.

[Проверка окружения](https://github.com/MishaGameHacking/omni-cio-gateway/commit/09403aabe557b634d852131ae89a3175906562dd/checks).

Новых обязательных программ для этой настройки не обнаружено. Наличие инструментов не означает прохождение всех тестов. Полный WSL-прогон 40227746918 завершился ошибкой; это отдельная работа N00, этим сценарием она не исправлялась.

## Сценарий и проверка

[Точный исходник](https://github.com/MishaGameHacking/omni-cio-gateway/blob/bac1328435456a325d62f1e874a8c2194caafb4a/tools/AnalystAI-Maintenance.ps1).

Файл на ноутбуке: `C:\actions-runner-2\_work\_tool\AnalystMaintenanceSetup\AnalystAI-Maintenance.ps1`

SHA-256: `0efccb08d194981184cc2b6760f1b9b6cd34674e587112b9077ff9dc6f6cc7e3`

[Windows-проверка](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40229831864) прошла: 10 случаев границы/занятости/паузы/повтора/ошибочного времени; реальный счётчик времени; определение задачи; чтение питания; получение существующей блокировки сборок. SYSTEM проверяется по SID независимо от языка Windows.

Проверка не регистрировала задачу, не меняла питание и не перезагружала ноутбук.

## Один запуск от администратора

Открыть **Windows PowerShell → Запуск от имени администратора**, вставить весь блок:

~~~powershell
$p = 'C:\actions-runner-2\_work\_tool\AnalystMaintenanceSetup\AnalystAI-Maintenance.ps1'
if ((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash -ne '0efccb08d194981184cc2b6760f1b9b6cd34674e587112b9077ff9dc6f6cc7e3') { throw 'Файл изменился: установка остановлена.' }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $p -Mode Install -KeepAwakeOnAc
~~~

ExecutionPolicy Bypass действует только для этого процесса, системная политика не меняется. Сценарий копируется в защищённый от записи обычными пользователями каталог ProgramData. Runner не получает административных прав. Пароли и токены не требуются.

Успешное завершение выводит `INSTALLED: AnalystAI-RestartAfter12Hours`. Установщик не вызывает немедленный перезапуск. Плановая проверка начнётся примерно через минуту; перезапуск возможен после 12 часов бодрствования ОС. Если при установке порог уже превышен, он может быть запрошен после ближайшей проверки и предупреждения.

Опция `-KeepAwakeOnAc` отключает сон, гибернацию и сон при закрытии крышки только от сети. Исходные значения сохраняются в `C:\ProgramData\AnalystAI-Maintenance\original-ac-power.json`; батарейные настройки не меняются. Ноутбук нужно держать подключённым к питанию и интернету, с открытыми вентиляционными отверстиями.

## Поведение

- Задача `AnalystAI-RestartAfter12Hours` работает от SYSTEM при старте и проверяет условия каждую минуту, без входа пользователя и без открытого чата.
- QueryUnbiasedInterruptTime считает время работы, исключая сон/гибернацию; ручная смена часов не сдвигает порог.
- После 12 часов проверяет Runner.Worker, эмулятор, активный Gradle и установку Windows; при занятости откладывается.
- Получает ту же байтовую блокировку android.lock, что сборки проекта, и повторно проверяет процессы.
- Предупреждает вошедших пользователей и ещё минуту проверяет появление работы. Затем вызывает `shutdown /r /t 0` без /f.
- Несохранённое приложение может задержать или отменить перезагрузку. Эта защита не обходится; повторный запрос ограничен одним в час.
- Это перезагрузка, не выключение. Четыре уже настроенные Auto-службы смогут запуститься вновь; новый результат их запуска ещё не проверен.
- Production Timeweb и APK не меняются.

Проверка процессов и блокировка не являются атомарной остановкой всей очереди GitHub. Абсолютную защиту любого задания, поступившего одновременно с перезапуском ОС, этот сценарий не доказывает. Задачи вне общей блокировки проекта требуют отдельного согласования с обслуживанием.

## Проверка и отключение

~~~powershell
Get-ScheduledTask -TaskName 'AnalystAI-RestartAfter12Hours'
Get-Content 'C:\ProgramData\AnalystAI-Maintenance\status.json'
~~~

Отключение из административной PowerShell:

~~~powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'C:\ProgramData\AnalystAI-Maintenance\AnalystAI-Maintenance.ps1' -Mode Disable
~~~

Оно останавливает задачу и дальнейшие автоматические перезапуски. Настройки питания не восстанавливаются; их исходные значения сохранены отдельно.

Официальные основания: [Windows awake-time clock](https://learn.microsoft.com/en-us/windows/win32/api/realtimeapiset/nf-realtimeapiset-queryunbiasedinterrupttime), [shutdown](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/shutdown), [runner as a service](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/configure-the-application?platform=windows). Ненулевой timeout shutdown подразумевает принудительное закрытие, поэтому предупреждение реализовано отдельно.
