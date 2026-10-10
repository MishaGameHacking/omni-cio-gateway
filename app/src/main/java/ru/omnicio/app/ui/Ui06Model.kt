package ru.omnicio.app.ui

internal const val CURRENT_LOCAL_SCHEMA_VERSION = 2

internal enum class LocalMigrationStatus(val label: String) {
    CURRENT("Локальные данные актуальны"),
    MIGRATED("Локальные данные обновлены безопасно"),
    FAILED("Локальное обновление не завершено"),
}

internal enum class AppLayoutMode {
    COMPACT,
    STANDARD,
    WIDE,
}

internal fun migrationStatusFor(
    storedVersion: Int,
    persistSucceeded: Boolean,
): LocalMigrationStatus = when {
    storedVersion >= CURRENT_LOCAL_SCHEMA_VERSION -> LocalMigrationStatus.CURRENT
    persistSucceeded -> LocalMigrationStatus.MIGRATED
    else -> LocalMigrationStatus.FAILED
}

internal fun appLayoutMode(widthDp: Int): AppLayoutMode = when {
    widthDp < 360 -> AppLayoutMode.COMPACT
    widthDp < 840 -> AppLayoutMode.STANDARD
    else -> AppLayoutMode.WIDE
}

internal fun effectiveLayoutMode(
    widthDp: Int,
    fontScale: Float,
): AppLayoutMode =
    if (fontScale >= 1.3f && widthDp < 600) {
        AppLayoutMode.COMPACT
    } else {
        appLayoutMode(widthDp)
    }

internal fun shouldStackMetricCards(
    widthDp: Int,
    fontScale: Float,
): Boolean = widthDp < 640 || (fontScale >= 1.3f && widthDp < 840)

internal fun shouldStackDetailLine(fontScale: Float): Boolean = fontScale >= 1.3f

internal fun notificationPermissionRequired(sdkInt: Int): Boolean = sdkInt >= 33

internal fun powerSaverLabel(enabled: Boolean): String =
    if (enabled) "Включён · фоновые обновления могут быть отложены" else "Выключен"

internal fun dataSaverLabel(restricted: Boolean): String =
    if (restricted) "Ограничен · фоновые сетевые задачи могут быть отложены" else "Без ограничения"
