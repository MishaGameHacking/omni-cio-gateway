# Очистка Timeweb — 25 октября 2026

Владелец поручил: «Наведи порядок в Timeweb удали лишние сервера!».
Перенос и удаление завершены 25.10.2026 в 17:15:24 UTC (20:15:24 МСК). В аккаунте подтверждены ровно
один облачный сервер и один публичный IP. Выделенных серверов в проекте нет.

## Действующая инфраструктура

| Объект | Подтверждённое состояние |
|---|---|
| Проект | 2941515 |
| Сервер | 9417611, Analyst AI runtime 20261025 |
| Регион | Амстердам, ams-1 |
| Ресурсы | 2 vCPU, 4096 MB RAM, 30720 MB NVMe |
| Публичный IPv4 | 83.217.195.29 |
| Floating IP | b77b2b7c-cd0e-4434-b096-27ef94ddcc86 |
| HTTPS | https://analyst-ai-2941515.twc1.net |
| Удалённый сервер | 9415007, Analyst AI PRO, 4 vCPU / 6144 MB RAM |
| Удалённый лишний IP | 31.130.128.55, fa1ee0ae-0d98-42cc-92c6-e4bda4ff88d0 |

Доменные записи и рабочий IP сохранены. Технический домен не привязан к
удалённому серверу; A-запись 95092009 указывает на83.217.195.29.
Точный конечный состав ресурсов записан в deletion-receipt.json и логе
[конечной проверки](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40215474406).

На9417611 analyst-ai-owner.service, analyst-ai-updates.service и caddy.service
работают и включены для запуска после перезагрузки. Восстановлены исходные
эффективные флаги: ANALYSIS_SCHEDULER_ENABLED=true,
AI_EXTERNAL_PROCESSING_APPROVED=false; SANDBOX_WORKER_ENABLED не задан.
Флаги совпадают с исходным сервером. Платные AI-вызовы и реальные сделки
для переноса не выполнялись. В момент активации доступно3 477 782 528байт RAM.

После удаления проверены TLS, /health200, /workspace401 без сессии, policy38
и полное скачивание APK с точным размером и SHA-256. Отказ401 подтверждает
защиту приватного маршрута, но не вход владельца или работу приложения на телефоне.
SQLite quick_check и foreign_key_check повторно завершились успешно.

При переносе был перерыв доступности: после переключения IP службы нового
сервера оказались остановлены и выключены из автозапуска. Их состояние
исправлено, службы запущены, затем внешние проверки прошли. Нулевой простой
не заявляется. Первые попытки удаления остановились на тайм-аутах чтения API
до DELETE; затем сервер удалён с ответом204. Контрольное чтение отдельного
удалённого ресурса вернуло403, поэтому отсутствие сервера
подтверждено через полный список; повторный DELETE сервера не отправлялся.
Для временных сбоев чтения API добавлены ограниченные повторы GET.

## Сохранённые данные и доказательства

Перед удалением старого сервера создан и полностью сверён закрытый архив:

- Путь: /var/backups/analyst-ai-retired-9415007-20261025/preservation.tar.gz.
- Размер706 187 073байта; 16 521запись; исходный payload1 450 055 743байта.
- SHA-256: `8b29d3c1e790281f99f9ed824c7d8d6b1c183df43c0e4e6af0ec810f8f518ec9`.
- SHA-256 manifest: `6546a1299cbb1109262a8d840a775abd5c777661bd6850bb24b88b0694f9c92f`.
- Проверены все пути, типы, метаданные и хеши файлов на сервере назначения.
- Сохранены /srv/analyst-ai с рабочими исходниками и Git-историей,
  /var/lib/analyst-ai-build с Windows-архивами и ключом подписи,
  /var/backups/analyst-ai и служебные файлы владельца/подготовки.
- Android SDK12,8ГБ не переносился: разработка, сборки и проверки остаются
  на ноутбуке Windows, установленный там SDK переиспользуется.
- Архив и receipts доступны только root; публичных ссылок на секреты нет.
- Ключ подписи: исходный debug.keystore2602байта,
  SHA-256 `bf4443e8ed6cb10b4ea4c9c0f46751e5955560e8c5f1bbb928b70febfc9e8ef2`.
- Точный Windows-экспорт:68 595 628байт,
  SHA-256 `e4dde847b35e6f97fc6c398355b71c8c0da0a146474128dd525c901c159cd477`.

Свежая согласованная копия runtime сделана после остановки старых служб,
перед переключением. Сохранены актуальная БД44таблицы, owner/session binding,
Fernet/конфигурация и OTA38. SQLite backup и quick/foreign-key checks прошли.
После переноса исходный backend.env совпал по SHA-256.

Runtime-архив на новом сервере:
`/root/.analyst-runtime-stage-runtime-final-20261025-40213299556/runtime.tar`,
241 582 080байт,5980записей,
SHA-256 `20483d197c6df336e1eec721e0e5caa37a420b5e2aefe7ca0d3bdbb4bac2264f`.
Manifest SHA-256:
`fe46e134c4cbac7c358336efaa1ffbadc4f28d6e684eaa417eac3e308fd38f9b`.

На9417611 сохранены preservation-receipt.json и deletion-receipt.json
рядом с preservation.tar.gz. В runtime-stage находятся protected-start.json,
active-runtime-receipt.json и cutover-complete.json. Эти файлы описывают
состояние в момент операции; живая БД после запуска продолжает изменяться.
Повторно накатывать прежние snapshot/runtime.tar поверх неё нельзя.

## Приложение и следующие действия

Текущий APK остаётся0.13.0-preview /38, ru.omnicio.app.debug,
29 754 870байт, SHA-256
`058e307855cad135a30bccc8a4a5bafc96638fd8400ba31fda0af07f255d0bef`.
Сертификат:
`bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1`.
[Тот же тестовый APK](https://analyst-ai-2941515.twc1.net/client/apk/Analyst-AI-38-058e307855cad135a30bccc8a4a5bafc96638fd8400ba31fda0af07f255d0bef.apk).

Выдача38 разрешена владельцем для ручной проверки до полной runtime-матрицы.
Три Linux-only collection errors Windows-прогона остаются; Android
API37/4096/16384, установка и интерфейс физического телефона не подтверждены.
Очистка серверов не даёт этим этапам PASS. При переносе не запускались новые
сборки или тесты приложения на Timeweb. main и код приложения не менялись.

Каноническая точка продолжения:
[CONTINUATION_2026-10-25.md](CONTINUATION_2026-10-25.md).
Разработка и проверки — LAPTOP-NPSGA016; Timeweb — runtime и хранение
подтверждённых архивов. Ключ подписи не заменять; enrollment не повторять.

Для следующего Windows-прогона подготовлен commit
`012610d64c21193505400020d7757de38ecff487` в
`codex/runtime-9417611-transport-2026-10-25`:
исправленная диагностика и возврат архива уже указывают на9417611 с прежним
IP и новым закреплённым SSH host key. Перед следующим запуском перенести
этот workflow в рабочую административную ветку: старый Windows collector
там ещё содержит удалённый9415007. Подготовительная ветка не запускает
новую сборку и не является подтверждением прохождения тестов.

Новый SSH host key:
`ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILN7hxzg6D6GjaE9OYQ19wH86tSm10pTnv+s81eqOfIU runner@runnervmtai0g`.
Для будущих Windows-архивов проверен каталог /var/lib/analyst-ai-build,
uid995/gid986,0750. Не запускать исторические сценарии создания,
восстановления или удаления9415007.

## Операционные запуски

- [Инвентаризация](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40212362169).
- [Сохранение и сверка исходников, подписи и отчётов](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40212805385).
- [Свежая копия runtime и переключение IP; первоначальная внешняя проверка failed](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40213299556).
- [Активация и внешняя проверка нового runtime — success](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40214160094).
- [Удаление старого сервера — DELETE204; последующий контрольный GET остановил запуск](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40215155470).
- [Удаление лишнего IP и конечная проверка](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40215474406).
