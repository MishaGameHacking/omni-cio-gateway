package ru.omnicio.app.data.backend

import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

internal const val MAX_OWNER_RETRY_SECONDS = 86_400

/** Invalid or missing headers never invent a wait. Dates prefer the server clock. */
internal fun ownerRetryAfterSeconds(
    value: String?,
    serverDate: String? = null,
    receivedAtMillis: Long = System.currentTimeMillis(),
): Int? {
    val normalized = value?.trim() ?: return null
    if (normalized.isEmpty() || normalized.length > 128) return null
    if (normalized.all { it in '0'..'9' }) {
        if (normalized.length > 6) return null
        return normalized.toIntOrNull()?.takeIf { it in 1..MAX_OWNER_RETRY_SECONDS }
    }
    val deadline = ownerHttpDateMillis(normalized) ?: return null
    val baseline = ownerHttpDateMillis(serverDate) ?: receivedAtMillis
    val difference = runCatching { Math.subtractExact(deadline, baseline) }.getOrNull() ?: return null
    if (difference !in 1L..MAX_OWNER_RETRY_SECONDS * 1_000L) return null
    return ((difference + 999L) / 1_000L).toInt()
}

private fun ownerHttpDateMillis(value: String?): Long? {
    if (value == null || value.length > 128) return null
    return runCatching {
        ZonedDateTime.parse(value.trim(), DateTimeFormatter.RFC_1123_DATE_TIME).toInstant().toEpochMilli()
    }.getOrNull()
}

internal fun ownerAccessFailure(
    status: Int,
    retryAfter: String?,
    serverDate: String? = null,
    receivedAtMillis: Long = System.currentTimeMillis(),
): BackendResult.Failure = BackendResult.Failure(
    message = when (status) {
        401, 403 -> "Доступ не подтверждён. Проверьте пароль или ключ настройки."
        409 -> "Пароль уже настроен. Войдите с сохранённым паролем."
        422 -> "Пароль должен содержать не менее 10 символов и не более 128 байт."
        429 -> "Слишком много попыток. Подождите перед следующим входом."
        426 -> "Обновите Analyst AI, чтобы продолжить."
        404 -> "Новый вход ещё не доступен на сервере. Требуется обновление серверной системы."
        else -> "Не удалось проверить доступ на сервере. Повторите позже."
    },
    retryable = status == 429 || status >= 500 || status == 404,
    statusCode = status,
    retryAfterSeconds = if (status == 429) ownerRetryAfterSeconds(retryAfter, serverDate, receivedAtMillis) else null,
)
