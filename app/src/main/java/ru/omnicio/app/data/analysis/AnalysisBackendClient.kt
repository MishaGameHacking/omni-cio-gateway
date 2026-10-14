package ru.omnicio.app.data.analysis

import java.net.HttpURLConnection
import java.net.URI
import javax.net.ssl.HttpsURLConnection
import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.data.backend.BackendConfig
import ru.omnicio.app.data.backend.BackendResult

class AnalysisBackendClient(
    private val baseUrl: String = BackendConfig.BASE_URL,
) {
    fun fetchFeed(accessToken: String): BackendResult<InsightFeed> = parse(
        request("GET", "/analysis/feed", accessToken),
        ::parseFeed,
        "Не удалось прочитать сообщения Analyst AI.",
    )

    fun fetchPulse(accessToken: String): BackendResult<List<InsightCard>> = parse(
        request("GET", "/analysis/pulse", accessToken),
        { json -> parseCards(json.optJSONArray("cards") ?: JSONArray()) },
        "Не удалось прочитать ленту событий.",
    )

    fun fetchIdeas(accessToken: String): BackendResult<IdeasPayload> = parse(
        request("GET", "/analysis/ideas", accessToken),
        ::parseIdeas,
        "Не удалось получить направления диверсификации.",
    )

    fun fetchProfile(accessToken: String): BackendResult<AnalysisProfile> = parse(
        request("GET", "/analysis/profile", accessToken),
        ::parseProfile,
        "Не удалось получить инвестиционный профиль.",
    )

    fun saveProfile(
        accessToken: String,
        profile: AnalysisProfile,
    ): BackendResult<AnalysisProfile> {
        val body = JSONObject()
            .put("risk_level", profile.riskLevel)
            .put("horizon", profile.horizon)
            .put("allowed_markets", JSONArray(profile.allowedMarkets))
            .put("max_position_percent", profile.maxPositionPercent)
            .put("min_cash_percent", profile.minCashPercent)
            .put("notify_critical", profile.notifyCritical)
            .put("notify_briefs", profile.notifyBriefs)
            .toString()
        return parse(
            request("PUT", "/analysis/profile", accessToken, body),
            ::parseProfile,
            "Не удалось сохранить инвестиционный профиль.",
        )
    }

    fun fetchStatus(accessToken: String): BackendResult<AnalysisStatus> = parse(
        request("GET", "/analysis/status", accessToken),
        ::parseStatus,
        "Не удалось получить состояние аналитической системы.",
    )

    fun refresh(accessToken: String): BackendResult<RefreshResult> = parse(
        request(
            "POST",
            "/analysis/refresh",
            accessToken,
            JSONObject().put("reason", "manual").toString(),
        ),
        ::parseRefresh,
        "Не удалось обновить анализ портфеля.",
    )

    fun markRead(accessToken: String, cardId: String): BackendResult<Boolean> {
        return when (val response = request("POST", "/analysis/cards/$cardId/read", accessToken, "{}")) {
            is BackendResult.Success -> BackendResult.Success(true)
            is BackendResult.Failure -> response
        }
    }

    private fun <T> parse(
        response: BackendResult<String>,
        parser: (JSONObject) -> T,
        errorMessage: String,
    ): BackendResult<T> = when (response) {
        is BackendResult.Success -> runCatching {
            parser(JSONObject(response.value))
        }.fold(
            onSuccess = { BackendResult.Success(it) },
            onFailure = { BackendResult.Failure(errorMessage, retryable = true) },
        )
        is BackendResult.Failure -> response
    }

    private fun request(
        method: String,
        path: String,
        bearer: String,
        body: String? = null,
    ): BackendResult<String> {
        val connection = runCatching {
            (URI(baseUrl + path).toURL().openConnection() as HttpsURLConnection).apply {
                requestMethod = method
                connectTimeout = 10_000
                readTimeout = 30_000
                ru.omnicio.app.data.updates.ClientVersion.attach(this)
                setRequestProperty("Accept", "application/json")
                setRequestProperty("Authorization", "Bearer $bearer")
                if (body != null) {
                    doOutput = true
                    setRequestProperty("Content-Type", "application/json")
                }
            }
        }.getOrElse {
            return BackendResult.Failure(
                "Не удалось подготовить защищённое соединение с Analyst AI.",
                retryable = true,
            )
        }

        return try {
            if (body != null) {
                connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
            }
            val status = connection.responseCode
            ru.omnicio.app.data.updates.ClientVersion.observeStatus(status)
            val text = if (status in 200..299) {
                connection.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
            } else {
                connection.errorStream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
            }
            val detail = runCatching { JSONObject(text).optString("detail") }.getOrNull()
            when {
                status in 200..299 -> BackendResult.Success(text)
                status == 426 -> BackendResult.Failure("Обновите Analyst AI, чтобы продолжить.", retryable = true)
                status == HttpURLConnection.HTTP_UNAUTHORIZED ||
                    status == HttpURLConnection.HTTP_FORBIDDEN -> BackendResult.Failure(
                    "Сеанс Analyst AI истёк. Войдите через Telegram заново.",
                    retryable = false,
                )
                status == HttpURLConnection.HTTP_CONFLICT && detail == "tinvest_not_connected" ->
                    BackendResult.Failure("Подключите T‑API в профиле.", retryable = false)
                status == 429 || status >= 500 -> BackendResult.Failure(
                    "Аналитическая система временно недоступна. Попробуйте позже.",
                    retryable = true,
                )
                else -> BackendResult.Failure(
                    detail?.takeIf { it.isNotBlank() } ?: "Сервер отклонил запрос.",
                    retryable = false,
                )
            }
        } catch (_: Exception) {
            BackendResult.Failure(
                "Не удалось связаться с аналитической системой.",
                retryable = true,
            )
        } finally {
            connection.disconnect()
        }
    }

    private fun parseFeed(json: JSONObject): InsightFeed = InsightFeed(
        unreadCount = json.optInt("unread_count"),
        cards = parseCards(json.optJSONArray("cards") ?: JSONArray()),
    )

    private fun parseCards(array: JSONArray): List<InsightCard> = buildList {
        for (index in 0 until array.length()) {
            val item = array.getJSONObject(index)
            add(
                InsightCard(
                    id = item.getString("id"),
                    kind = item.optString("kind"),
                    severity = item.optString("severity", "info"),
                    title = item.getString("title"),
                    summary = item.getString("summary"),
                    actions = item.optJSONArray("actions").toStringList(),
                    evidence = item.optJSONArray("evidence").toEvidenceList(),
                    uncertainties = item.optJSONArray("uncertainties").toStringList(),
                    validUntil = item.optNullableString("valid_until"),
                    isRead = item.optBoolean("is_read"),
                    createdAt = item.optString("created_at"),
                ),
            )
        }
    }

    private fun parseIdeas(json: JSONObject): IdeasPayload {
        val ideasJson = json.optJSONArray("ideas") ?: JSONArray()
        val ideas = buildList {
            for (index in 0 until ideasJson.length()) {
                val item = ideasJson.getJSONObject(index)
                add(
                    AnalysisIdea(
                        assetClass = item.getString("asset_class"),
                        currentPercent = item.optDouble("current_percent"),
                        targetPercent = item.optDouble("target_percent"),
                        gapPercent = item.optDouble("gap_percent"),
                        suggestedMaxPercent = item.optDouble("suggested_max_percent"),
                        explanation = item.optString("explanation"),
                    ),
                )
            }
        }
        return IdeasPayload(
            state = json.optString("state"),
            message = json.optString("message"),
            cashSharePercent = json.optNullableDouble("cash_share_percent"),
            reservePercent = json.optNullableDouble("reserve_percent"),
            ideas = ideas,
        )
    }

    private fun parseProfile(json: JSONObject): AnalysisProfile = AnalysisProfile(
        riskLevel = json.optString("risk_level", "moderate"),
        horizon = json.optString("horizon", "medium"),
        allowedMarkets = json.optJSONArray("allowed_markets").toStringList().ifEmpty { listOf("RU") },
        maxPositionPercent = json.optDouble("max_position_percent", 25.0),
        minCashPercent = json.optDouble("min_cash_percent", 5.0),
        notifyCritical = json.optBoolean("notify_critical", true),
        notifyBriefs = json.optBoolean("notify_briefs", true),
        configured = json.optBoolean("configured"),
    )

    private fun parseStatus(json: JSONObject): AnalysisStatus {
        val last = json.optJSONObject("last_run")?.let { item ->
            AnalysisRunStatus(
                state = item.optString("state"),
                reason = item.optString("reason"),
                tier = item.optString("tier"),
                model = item.optNullableString("model"),
                errorCode = item.optNullableString("error_code"),
                createdAt = item.optString("created_at"),
            )
        }
        return AnalysisStatus(
            schedulerEnabled = json.optBoolean("scheduler_enabled"),
            aiConfigured = json.optBoolean("ai_configured"),
            deterministicMonitoring = json.optBoolean("deterministic_monitoring"),
            unreadCount = json.optInt("unread_count"),
            profileConfigured = json.optBoolean("profile_configured"),
            lastRun = last,
        )
    }

    private fun parseRefresh(json: JSONObject): RefreshResult = RefreshResult(
        state = json.optString("state"),
        reason = json.optString("reason"),
        tier = json.optString("tier"),
        model = json.optNullableString("model"),
        cardId = json.optNullableString("card_id"),
        errorCode = json.optNullableString("error_code"),
    )

    private fun JSONArray?.toStringList(): List<String> {
        if (this == null) return emptyList()
        return buildList {
            for (index in 0 until length()) {
                optString(index).takeIf { it.isNotBlank() }?.let(::add)
            }
        }
    }

    private fun JSONArray?.toEvidenceList(): List<AnalysisEvidence> {
        if (this == null) return emptyList()
        return buildList {
            for (index in 0 until length()) {
                val item = optJSONObject(index) ?: continue
                add(
                    AnalysisEvidence(
                        fact = item.optString("fact"),
                        sourceId = item.optString("source_id"),
                        asOf = item.optString("as_of"),
                    ),
                )
            }
        }
    }

    private fun JSONObject.optNullableString(key: String): String? {
        if (!has(key) || isNull(key)) return null
        return optString(key).takeIf { it.isNotBlank() }
    }

    private fun JSONObject.optNullableDouble(key: String): Double? {
        if (!has(key) || isNull(key)) return null
        return optDouble(key)
    }
}
