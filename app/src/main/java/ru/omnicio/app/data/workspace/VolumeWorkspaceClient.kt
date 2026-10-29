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
        require(WorkspaceEndpointPolicy.permits(path))
        require(method in setOf("GET", "POST", "PUT", "PATCH", "DELETE"))
        // Search punctuation is query data; traversal checks belong to the
        // decoded path so escaped dot segments cannot evade the same guard.
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
        val policyMessage = if (status in setOf(422, 409, 503)) chatPolicyMessage(code) else null
        val message = policyMessage ?: when (status) {
            401, 403 -> "Войдите в приложение заново с паролем владельца. Рабочий контекст сохранён."
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
            "timeweb_ai_key_missing", "ai_model_identifier_missing_or_invalid",
            "ai_no_approved_route_for_task" ->
                "ИИ ещё не подключён на сервере. Вопрос не отправлен модели; текст можно сохранить и повторить после настройки."
            "ai_prices_missing_stale_or_invalid", "ai_model_price_binding_required" ->
                "Стоимость ответа сейчас не подтверждена. Запрос не отправлен модели; повторите после обновления тарифов сервиса."
            "ai_processing_approval_required", "ai_processing_region_not_approved" ->
                "Обработка данных для этого маршрута ещё не настроена. Вопрос не отправлен модели."

            "ai_broker_connection_required", "tinvest_not_connected" ->
                "Подключите T‑Invest в настройках и дождитесь загрузки данных портфеля. Без подключения вопрос не отправляется модели."
            "ai_broker_binding_unavailable", "ai_broker_connection_changed", "monitoring_connection_changed" ->
                "Подключение T‑Invest изменилось или ещё не готово. Проверьте подключение в настройках и обновите данные портфеля."
            "workspace_refresh_required" ->
                "Данные портфеля ещё не загружены. Обновите их на главном экране и дождитесь завершения загрузки, затем отправьте вопрос."
            "ai_workspace_reconciliation_required", "ai_worker_reconciliation_required",
            "ai_budget_reconciliation_required", "ai_usage_requires_reconciliation" ->
                "Расход предыдущего запроса ещё не подтверждён. Новые платные запросы приостановлены до сверки; смена ключа ИИ сама по себе её не завершает."
            "ai_route_cooling_down" ->
                "После ошибки провайдера ИИ действует короткая пауза. Сохраните вопрос и повторите отправку немного позже."
            "ai_route_in_flight" ->
                "Предыдущий запрос к этой модели ещё выполняется. Дождитесь его завершения и повторите отправку."
            "ai_user_budget_exhausted", "ai_project_budget_exhausted" ->
                "Дневной бюджет ИИ исчерпан. Новый запрос можно отправить после начала следующего расчётного дня."
            "ai_user_monthly_budget_exhausted", "ai_project_monthly_budget_exhausted" ->
                "Месячный бюджет ИИ исчерпан. Новые платные запросы приостановлены до следующего расчётного месяца."
            "ai_ruble_budget_not_enabled", "ai_budget_disabled_or_invalid", "ai_monthly_budget_disabled_or_invalid" ->
                "Лимиты расходов ИИ ещё не настроены на сервере. Платные запросы приостановлены."
            "chat_context_too_large", "ai_context_too_large", "ai_context_size_invalid",
            "ai_no_route_with_context_capacity" ->
                "Для выбранной модели слишком много данных. Выберите конкретный актив или более короткий период и отправьте вопрос заново."

            "chat_outside_investment_scope" -> "Analyst AI отвечает только об инвестициях, активах и мировой финансовой политике. Этот вопрос не отправлен модели."
            "chat_investment_scope_unclear", "chat_text_invalid" -> "Уточните инвестиционный вопрос: укажите актив, портфель или влияние события на финансовые рынки."
            "chat_tier_insufficient", "chat_tier_invalid" -> "Для этого вопроса нужен более глубокий анализ. Выберите «Авто» или подходящую глубину."
            "chat_cost_estimate_required", "chat_cost_or_route_changed" -> "Стоимость или маршрут требуют повторной проверки. Запрос модели не отправлен."
            "chat_premium_confirmation_required" -> "Подтвердите стоимость глубокого запроса перед отправкой."
            "chat_explanation_risk_unavailable", "chat_explanation_candidate_unavailable" -> "Данные выбранного объекта обновились. Откройте его снова и повторите вопрос."
            "chat_explanation_notification_unavailable", "chat_explanation_analysis_facts_unavailable",
            "chat_explanation_event_unavailable", "chat_explanation_evidence_unavailable",
            "chat_explanation_document_unavailable" -> "Сохранённые основания для этого объяснения пока недоступны. Выберите другой объект или задайте общий инвестиционный вопрос."
            "chat_explanation_scope_invalid", "chat_explanation_target_invalid" -> "Контекст вопроса устарел. Откройте объяснение из карточки ещё раз."
            else -> null
        }
        /** Fixed diagnostics only: never show upstream bodies, credentials or model output. */
        fun jobFailureMessage(code: String?): String = when (code) {
            "workspace_paid_outcome_unknown", "ai_transport_outcome_unknown",
            "ai_usage_missing", "ai_usage_invalid", "ai_usage_inconsistent",
            "ai_usage_outside_reserved_bounds" ->
                "Итог запроса и его расход ещё не подтверждены. Нужна сверка; автоматического повторного платного запроса нет."
            "ai_http_401", "ai_http_403" ->
                "Провайдер отклонил серверный ключ ИИ. Ответ не получен; требуется проверить подключение ИИ на сервере."
            "ai_http_429" ->
                "Провайдер ИИ отклонил запрос из-за своего лимита. Проверьте состояние задания перед новой отправкой."
            "ai_incomplete_response" ->
                "Модель не завершила ответ в установленном лимите. Неполный ответ не опубликован; автоматического повторного запроса нет."
            "ai_content_not_json", "ai_content_not_object", "ai_content_invalid",
            "ai_response_not_json", "ai_choices_invalid", "ai_chat_response_invalid",
            "ai_chat_claims_invalid", "ai_chat_evidence_not_in_context", "ai_chat_uncertainty_invalid",
            "ai_chat_highlight_not_in_context", "ai_chat_action_not_allowed", "ai_chat_action_not_in_context",
            "ai_duplicate_json_field", "ai_nonfinite_json",
            "ai_numeric_underflow", "ai_json_nesting_exceeded", "ai_response_too_large" ->
                "Ответ модели не прошёл проверку формата или оснований. Он не опубликован; автоматического повторного запроса нет."
            else -> chatPolicyMessage(code) ?:
                "Задание завершилось без подтверждённого результата. Проверьте его состояние; автоматического повторного запроса нет."
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
