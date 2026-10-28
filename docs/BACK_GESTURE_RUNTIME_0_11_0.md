# Дополнительная проверка системного Back — 0.11.0

Связь: F01 / F22 / F23; PR880, `codex/spectrum-3d-100`.
Владелец 18.10.2026 запросил APK только для ручной проверки. **Timeweb, серверный
APK, backend и канал обновлений не обновлять.** Ветка остаётся draft.

## Наблюдение на 0a8bf27

[Android run 39163505060](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/39163505060)
прошёл 522 host-теста (3 Windows skip), app unit/build/lint, native/signature,
установку/обновление с 0.10.0 и запуск preview на Android15 с PAGE_SIZE=16384.
Повторно пройдены предшествующие spatial UI-сценарии. Новый UiAutomation driver
подтвердил инъекции hold и cleanup cancel, но наблюдаемый progress не появился.
Итог — failure; API36 не достигнута, приватный APK draft не создан.

Backend CI 39163504727: 1089 passed, 2 skipped, 337 subtests; health/OpenAPI passed.
Sonar check117781635834: success, 0 annotations. Это результаты только 0a8bf27.

## Следующее исправление и независимая диагностика

Проверка теперь явно читает device_provisioned и user_setup_complete. AOSP15
`GestureNavigationSettingsObserver.areNavigationButtonForcedVisible()` считает
нулевой USER_SETUP_COMPLETE запретом edge-жестов независимо от navigation_mode.
Только после проверки точного disposable AVD, ro.kernel.qemu и primary user
тест завершает отсутствующую настройку. Прежние значения, включая отсутствие,
восстанавливаются; все записи сверяются обратным чтением. Нельзя утверждать,
что старый AVD имел значение0: предыдущий журнал этих полей не содержал.

AOSP15 может передать onBackStarted после уже обработанных touch-событий и
генерировать progress на стороне приложения. Вместо неподвижного указателя
после короткого начального отрезка тест продолжает тот же pointer/downTime
по ограниченной траектории: до16 дополнительных MOVE, не дальше54% ширины.
Это не повторный жест и не подстановка progress. Реальный положительный progress,
PNG, отмена без навигации, завершение ровно один раз и сброс сцены обязательны.

При отказе сохраняются последние настоящие метрики и ограниченные поля
SystemUI edge/Back-диагностики. Исходная ошибка не заменяется ошибкой диагностики.
Порог и время существующего UI assertion не повышались, рендерер не упрощён.

Локально: 22 Python-теста прошли, включая6 исполняемых Java-сценариев и8 Node
сценариев приватного хранения. Это не проверка эмулятора. Новый runtime должен
подтвердить либо опровергнуть устранение оставшегося отказа.

Источники контракта Android15:
- https://github.com/aosp-mirror/platform_frameworks_base/blob/android-15.0.0_r1/core/java/com/android/internal/policy/GestureNavigationSettingsObserver.java
- https://github.com/aosp-mirror/platform_frameworks_base/blob/android-15.0.0_r1/core/java/android/window/WindowOnBackInvokedDispatcher.java
- https://github.com/aosp-mirror/platform_frameworks_base/blob/android-15.0.0_r1/libs/WindowManager/Shell/src/com/android/wm/shell/back/BackAnimationController.java

Приватное вложение APK остаётся заблокированным до полного API35/API36 validator
и quality gates. Никакой установки на Timeweb или объявления всего0.11.0 готовым.
