# OMNICIO — план системы Android / Timeweb

Редакция по поручению владельца от 11.10.2026. Старый local-first план и fixtures более не являются целевой архитектурой; Git history сохраняет их историю.

## Данные и authority

Android → HTTPS OMNICIO → существующие session/tenant services → PostgreSQL и официальные provider adapters.

Все финансовые значения, история, цели, события и аналитические результаты хранятся/получаются на сервере. Android содержит только UI и временное состояние отображения. На диске телефона — только оформление. Broker credential не возвращается из API и не передаётся AI. Сервер проверяет read-only права, текущую сессию, контекст профиля и согласия.

## Рабочие направления

| Область | Требование |
|---|---|
| Вход | Existing email registration/login/reset, серверные cookies в памяти клиента |
| Брокер | Existing encrypted credential, preview accounts, explicit consent, prod/read-only |
| Портфель | Existing snapshots, money/quantity precision, missing/freshness/provenance |
| История | Наблюдения сервера, реальное время, partial gaps, отсутствие вымышленной доходности |
| События | Existing server feed, unread state, cursor pagination |
| Цели | Existing server persistence, пользовательский ввод, version checks для будущего редактирования |
| Рыночные источники | Только официальные/отдельно разрешённые adapters с provenance |
| Аналитика | Детерминированные серверные расчёты, неизвестные значения не равны нулю |
| AI | Existing guarded gateway; не изображать недоступный ответ готовой рекомендацией |
| Уведомления | Отдельная будущая Android push-интеграция; текущая версия не обещает фоновой доставки |
| Подписки | Отдельная RuStore интеграция после подтверждённой необходимости; не имитировать покупку |
| Выпуск | Accepted main, CI/Sonar, server readiness/build identity, signed Android/device QA |

## Обновление текущей версии

1. Удалить runtime fixtures и fake states из Android.
2. Добавить memory-only HTTPS client и нативные auth/broker/data screens.
3. Добавить `/api/mobile/workspace` без новой БД и без второй реализации provider adapters.
4. Перед выдачей ответа повторно проверить сессию, connection и account/environment.
5. Передавать источники сохранённого снимка, точные decimal strings, nullable data.
6. Проверить API isolation/precision/failures, Android build/accessibility и real-device critical path.
7. Принять exact PR после обязательных проверок. Развернуть существующим workflow из accepted main.
8. Проверить `/health/live`, `/health/ready`, API release headers и авторизованный сценарий; затем обновить Android на ноутбуке.

Новые provider ресурсы, секреты, миграции и broker write authority не требуются. При непроверенном коде production остаётся на последнем принятом выпуске. Успех разработки, merge, deploy, APK installation и RuStore publication фиксируются раздельно.
