package ru.omnicio.app.ui.updates

import ru.omnicio.app.data.updates.ReleaseDecision
import ru.omnicio.app.data.updates.ReleaseDescriptor

/** Presentation only: neither renderer may unlock content or invoke an installer directly. */
data class UpdateGateUi(
    val release: ReleaseDescriptor?,
    val decision: ReleaseDecision?,
    val installedVersion: String,
    val checking: Boolean,
    val busy: Boolean,
    val progress: Int,
    val error: String?,
    val installationStatus: String?,
) {
    val canUpdate: Boolean get() = release != null && decision == ReleaseDecision.UPDATE_REQUIRED && !busy && !checking
    val canRetry: Boolean get() = !busy && !checking
    val title: String get() = if (decision == ReleaseDecision.UPDATE_REQUIRED) "Требуется обновление" else "Проверка версии"
    val progressPercent: Int get() = progress.coerceIn(0, 100)
    val explanation: String get() = when (decision) {
        ReleaseDecision.UNSUPPORTED_ANDROID -> "Для этой версии нужен более новый Android. Установка неподходящего APK остановлена."
        ReleaseDecision.SERVER_NOT_READY -> "Сервер ещё не подтвердил эту сборку. Устанавливать более старую версию не нужно."
        ReleaseDecision.WRONG_CHANNEL -> "Сервер вернул другую линию приложения. Установка остановлена."
        else -> "Для работы нужна актуальная версия. Ваши данные сохранены. APK загружается с сервера Analyst AI; Android может попросить разрешение и подтверждение установки."
    }
}

data class UpdateGateActions(val update: () -> Unit, val retry: () -> Unit, val close: () -> Unit)
