package ru.omnicio.app.data.workspace

import java.net.URI
import java.net.URLEncoder
import javax.net.ssl.HttpsURLConnection
import org.json.JSONObject
import ru.omnicio.app.data.backend.BackendConfig
import ru.omnicio.app.data.updates.ClientVersion

/** Authenticated, bounded transport. Only user actions/data effects call this; never the renderer. */
class VolumeWorkspaceClient(private val baseUrl: String = BackendConfig.BASE_URL) : WorkspaceTransport {
    override fun request(token: String, path: String, method: String, body: JSONObject?): VolumeReply {
        require(path == "/workspace" || path.startsWith("/workspace/") || path.startsWith("/workspace?"))
        require(method in setOf("GET", "POST", "PUT", "PATCH", "DELETE"))
        require(!path.contains("..") && !path.contains('#'))
        val encoded = body?.toString()?.toByteArray(Charsets.UTF_8)
        require(encoded == null || encoded.size <= REQUEST_LIMIT)
        var connection: HttpsURLConnection? = null
        var dispatched = false
        return try {
            connection = BackendConfig.openConnection(URI(baseUrl + path))
            connection.requestMethod = method
            connection.instanceFollowRedirects = false
            connection.connectTimeout = 10_000
            connection.readTimeout = 25_000
            connection.setRequestProperty("Authorization", "Bearer $token")
            connection.setRequestProperty("Accept", "application/json")
            ClientVersion.attach(connection)
            if (encoded != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.setFixedLengthStreamingMode(encoded.size)
                dispatched = true
                connection.outputStream.use { it.write(encoded) }
            }
            readResponse(connection, token, dispatched)
        } catch (_: Exception) {
            VolumeReply(error = if (dispatched) "Не получено подтверждение сервера. Проверьте сохранённое задание перед повтором." else "Нет связи с сервером. Попробуйте позже.",
                code = "network_unavailable", ambiguous = dispatched, retryable = !dispatched)
        } finally { connection?.disconnect() }
    }

    private fun readResponse(connection: HttpsURLConnection, token: String, dispatched: Boolean): VolumeReply {
        val status = connection.responseCode
        ClientVersion.observeStatus(status)
        ru.omnicio.app.data.backend.SessionExpiry.observe(status, token)
        val stream = if (status in 200..299) connection.inputStream else connection.errorStream
        val bytes = stream?.use { it.readNBytes(RESPONSE_LIMIT + 1) } ?: byteArrayOf()
        if (bytes.size > RESPONSE_LIMIT) return VolumeReply(error = "Ответ слишком велик. Сузьте выбранный период.", code = "response_too_large", status = status,
            ambiguous = dispatched, retryable = !dispatched)
        val data = if (bytes.isEmpty()) JSONObject() else runCatching { JSONObject(String(bytes, Charsets.UTF_8)) }.getOrNull()
        if (status in 200..299 && data != null) return VolumeReply(data = data, status = status)
        val failed = failure(status, data)
        return if (dispatched && (status >= 500 || status in 200..299)) failed.copy(ambiguous = true, retryable = false) else failed
    }

    private fun failure(status: Int, json: JSONObject?): VolumeReply {
        val detail = json?.opt("detail")
        val code = when (detail) { is JSONObject -> detail.optString("code", "request_failed"); is String -> detail; else -> "invalid_response" }
        val policyMessage = if (status == 422 || status == 409) chatPolicyMessage(code) else null
        val message = policyMessage ?: when (status) {
            401, 403 -> "Войдите через Telegram заново. Рабочий контекст сохранён для вашего аккаунта."
            404 -> "Данные пока недоступны. Проверьте выбранный объект или обновите сведения."
            409 -> "Исходные данные изменились. Обновите их и подготовьте действие заново."
            422, 400 -> "Проверьте параметры и диапазон значений."
            426 -> "Для продолжения установите обновление Analyst AI."
            429 -> "Достигнут лимит запросов или бюджета. Дождитесь следующего доступного периода."
            503 -> "Источник или модель сейчас недоступны. Сохранённые данные остаются доступны."
            else -> "Сервер не подтвердил действие. Проверьте его состояние."
        }
        return VolumeReply(error = message, code = code, status = status, retryable = status == 429 || status >= 500)
    }

    companion object {
        private const val REQUEST_LIMIT = 100_000
        private const val RESPONSE_LIMIT = 2_000_000
        fun chatPolicyMessage(code: String?): String? = when (code) {
            "chat_outside_investment_scope" -> "Analyst AI отвечает только об инвестициях, активах и мировой финансовой политике. Этот вопрос не отправлен модели."
            "chat_investment_scope_unclear", "chat_text_invalid" -> "Уточните инвестиционный вопрос: укажите актив, портфель или влияние события на финансовые рынки."
            "chat_tier_insufficient", "chat_tier_invalid" -> "Для этого вопроса нужен более глубокий анализ. Выберите «Авто» или подходящую глубину."
            "chat_cost_estimate_required", "chat_cost_or_route_changed" -> "Стоимость или маршрут требуют повторной проверки. Запрос модели не отправлен."
            "chat_premium_confirmation_required" -> "Подтвердите стоимость глубокого запроса перед отправкой."
            else -> null
        }
        fun encode(value: String): String = URLEncoder.encode(value, "UTF-8")
    }
}

data class VolumeReply(
    val data: JSONObject? = null,
    val error: String? = null,
    val code: String? = null,
    val status: Int = 0,
    val ambiguous: Boolean = false,
    val retryable: Boolean = false,
) {
    val signedOut: Boolean get() = status == 401 || status == 403
}
