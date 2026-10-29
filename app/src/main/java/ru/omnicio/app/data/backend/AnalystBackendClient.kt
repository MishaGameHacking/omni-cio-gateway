package ru.omnicio.app.data.backend

import java.net.HttpURLConnection
import java.net.URI
import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.data.portfolio.ApiDecimal
import ru.omnicio.app.data.portfolio.MoneyAmount
import ru.omnicio.app.data.portfolio.PortfolioAccount
import ru.omnicio.app.data.portfolio.PortfolioAllocation
import ru.omnicio.app.data.portfolio.PortfolioCurrency
import ru.omnicio.app.data.portfolio.PortfolioPosition
import ru.omnicio.app.data.portfolio.PortfolioSnapshot

class AnalystBackendClient(
    private val baseUrl: String = BackendConfig.BASE_URL,
) {
    fun ownerAccessStatus(): BackendResult<OwnerAccessStatus> = when (val response = request("GET", "/auth/owner/status")) {
        is BackendResult.Failure -> response
        is BackendResult.Success -> runCatching {
            val json = JSONObject(response.value)
            require(json.getString("method") == "password")
            val minimum = json.getInt("min_password_length")
            val maximum = json.getInt("max_password_bytes")
            require(minimum in 10..128 && maximum in minimum..1024)
            OwnerAccessStatus(json.getBoolean("configured"), minimum, maximum)
        }.fold({ BackendResult.Success(it) }, {
            BackendResult.Failure("Сервер пока не подтвердил новый способ входа.", retryable = true)
        })
    }

    fun loginOwner(password: String, accessToken: String? = null): BackendResult<AnalystSession> = ownerSessionRequest(
        "/auth/owner/login", password, accessToken)

    fun setupOwnerPassword(password: String, accessToken: String?, bootstrap: String): BackendResult<AnalystSession> =
        ownerSessionRequest("/auth/owner/setup", password, accessToken, bootstrap.takeIf(String::isNotBlank))

    private fun ownerSessionRequest(path: String, password: String, bearer: String? = null,
        bootstrap: String? = null): BackendResult<AnalystSession> {
        val body = JSONObject().put("password", password)
            .put("device_name", "${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL}".take(100)).toString()
        return when (val response = request("POST", path, bearer, body, bootstrap)) {
            is BackendResult.Failure -> response
            is BackendResult.Success -> runCatching { parseSession(JSONObject(response.value)) }.fold(
                { BackendResult.Success(it) },
                { BackendResult.Failure("Не удалось проверить ответ входа. Повторите попытку.", retryable = true) })
        }
    }

    fun exchangeTelegramCode(code: String): BackendResult<AnalystSession> {
        val response = request(
            method = "POST",
            path = "/auth/session",
            body = JSONObject().put("code", code.trim())
                .put("device_name", "${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL}".take(100)).toString(),
        )
        return when (response) {
            is BackendResult.Success -> runCatching {
                parseSession(JSONObject(response.value))
            }.fold(
                onSuccess = { BackendResult.Success(it) },
                onFailure = {
                    BackendResult.Failure(
                        "Сервер вернул некорректный ответ авторизации.",
                        retryable = false,
                    )
                },
            )
            is BackendResult.Failure -> response
        }
    }

    fun fetchMe(accessToken: String): BackendResult<AnalystUser> {
        val response = request(
            method = "GET",
            path = "/me",
            bearer = accessToken,
        )
        return when (response) {
            is BackendResult.Success -> runCatching {
                parseUser(JSONObject(response.value))
            }.fold(
                onSuccess = { BackendResult.Success(it) },
                onFailure = {
                    BackendResult.Failure(
                        "Сервер вернул некорректные данные профиля.",
                        retryable = false,
                    )
                },
            )
            is BackendResult.Failure -> response
        }
    }

    fun fetchTInvestStatus(accessToken: String): BackendResult<Boolean> {
        val response = request(
            method = "GET",
            path = "/tinvest/status",
            bearer = accessToken,
        )
        return when (response) {
            is BackendResult.Success -> runCatching {
                JSONObject(response.value).getBoolean("connected")
            }.fold(
                onSuccess = { BackendResult.Success(it) },
                onFailure = {
                    BackendResult.Failure(
                        "Не удалось прочитать состояние T‑API.",
                        retryable = false,
                    )
                },
            )
            is BackendResult.Failure -> response
        }
    }

    fun fetchPortfolio(
        accessToken: String,
        currency: PortfolioCurrency,
    ): BackendResult<PortfolioSnapshot> {
        val response = request(
            method = "GET",
            path = "/tinvest/portfolio?currency=${currency.name}",
            bearer = accessToken,
        )
        return when (response) {
            is BackendResult.Success -> runCatching {
                parsePortfolio(JSONObject(response.value))
            }.fold(
                onSuccess = { BackendResult.Success(it) },
                onFailure = {
                    BackendResult.Failure(
                        "T-Invest вернул некорректные данные портфеля.",
                        retryable = true,
                    )
                },
            )
            is BackendResult.Failure -> response
        }
    }

    fun saveTInvestToken(
        accessToken: String,
        token: String,
    ): BackendResult<Boolean> {
        val response = request(
            method = "POST",
            path = "/tinvest/token",
            bearer = accessToken,
            body = JSONObject().put("token", token.trim()).toString(),
        )
        return when (response) {
            is BackendResult.Success -> BackendResult.Success(true)
            is BackendResult.Failure -> response
        }
    }

    fun deleteTInvestToken(accessToken: String): BackendResult<Boolean> {
        val response = request(
            method = "DELETE",
            path = "/tinvest/token",
            bearer = accessToken,
        )
        return when (response) {
            is BackendResult.Success -> BackendResult.Success(false)
            is BackendResult.Failure -> response
        }
    }

    private fun request(
        method: String,
        path: String,
        bearer: String? = null,
        body: String? = null,
        bootstrap: String? = null,
    ): BackendResult<String> {
        val connection = runCatching {
            BackendConfig.openConnection(URI(baseUrl + path)).apply {
                requestMethod = method
                connectTimeout = CONNECT_TIMEOUT_MS
                readTimeout = READ_TIMEOUT_MS
                ru.omnicio.app.data.updates.ClientVersion.attach(this)
                setRequestProperty("Accept", "application/json")
                if (bearer != null) {
                    setRequestProperty("Authorization", "Bearer $bearer")
                }
                if (bootstrap != null) setRequestProperty("X-Owner-Bootstrap", bootstrap)
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
                connection.outputStream.use { stream ->
                    stream.write(body.toByteArray(Charsets.UTF_8))
                }
            }
            val status = connection.responseCode
            ru.omnicio.app.data.updates.ClientVersion.observeStatus(status)
            ru.omnicio.app.data.backend.SessionExpiry.observe(status, bearer)
            val responseBody = if (status in 200..299) {
                connection.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
            } else {
                connection.errorStream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
            }

            responseResult(path, status, responseBody)
        } catch (_: Exception) {
            BackendResult.Failure(
                "Не удалось связаться с сервером Analyst AI.",
                retryable = true,
            )
        } finally {
            connection.disconnect()
        }
    }

    private fun responseResult(path: String, status: Int, responseBody: String): BackendResult<String> {
        val detail = if (status in 200..299) null else runCatching {
            JSONObject(responseBody).optString("detail")
        }.getOrNull()
        return when {
            status in 200..299 -> BackendResult.Success(responseBody)
            path.startsWith("/auth/owner/") -> ownerAccessFailure(status)
            status == 426 -> BackendResult.Failure("Обновите Analyst AI, чтобы продолжить.", retryable = true)
            status == HttpURLConnection.HTTP_UNAUTHORIZED ||
                status == HttpURLConnection.HTTP_FORBIDDEN -> BackendResult.Failure(
                    "Сеанс Analyst AI истёк или недействителен. Войдите с паролем заново.",
                    retryable = false,
                    statusCode = status,
                )
            path.startsWith("/tinvest/") -> tinvestFailure(detail, status)
            status == 429 || status >= 500 -> BackendResult.Failure(
                "Сервис временно недоступен. Попробуйте ещё раз.", retryable = true,
            )
            else -> BackendResult.Failure(
                detail?.takeIf { it.isNotBlank() } ?: "Сервер отклонил запрос.", retryable = false,
            )
        }
    }

    private fun ownerAccessFailure(status: Int): BackendResult.Failure = BackendResult.Failure(
        message = when (status) {
            401, 403 -> "Доступ не подтверждён. Проверьте пароль или ключ настройки."
            409 -> "Пароль уже настроен. Войдите с сохранённым паролем."
            422 -> "Пароль должен содержать не менее 10 символов и не более 128 байт."
            429 -> "Слишком много попыток. Подождите перед следующим входом."
            426 -> "Обновите Analyst AI, чтобы продолжить."
            404 -> "Новый вход ещё не доступен на сервере. Требуется обновление серверной системы."
            else -> "Не удалось проверить доступ на сервере. Повторите позже."
        }, retryable = status == 429 || status >= 500 || status == 404, statusCode = status,
    )

    private fun tinvestFailure(detail: String?, status: Int): BackendResult.Failure {
        val message = when (detail) {
            "invalid_tinvest_token" ->
                "T-Invest отклонил токен. Проверьте срок действия, права доступа и правильность копирования."
            "tinvest_tls_error" ->
                "Сервер не смог проверить сертификат T-Invest. Ошибка защищённого соединения, а не токена."
            "tinvest_connection_failed" ->
                "Сервер Analyst AI не может подключиться к T-Invest. Проверьте соединение позже."
            "tinvest_timeout" ->
                "T-Invest не ответил вовремя. Попробуйте ещё раз."
            "tinvest_rate_limited" ->
                "T-Invest ограничил частоту запросов. Подождите и повторите попытку."
            "tinvest_upstream_unavailable" ->
                "Сервис T-Invest временно недоступен. Попробуйте позже."
            "tinvest_unexpected_status", "tinvest_invalid_response" ->
                "T-Invest вернул неожиданный ответ. Не удалось подтвердить токен."
            "empty_tinvest_token" ->
                "Вставьте токен доступа T-Invest."
            "tinvest_not_connected" ->
                "Подключите T-API в профиле, чтобы загрузить портфель."
            "unsupported_portfolio_currency" ->
                "Эта валюта отображения не поддерживается."
            "tinvest_token_unreadable" ->
                "Сохранённый токен T-Invest повреждён. Подключите T-API заново."
            else -> when (status) {
                502 -> "Ошибка ответа T-Invest. Подключение не завершено."
                503, 504 -> "Связь с T-Invest временно недоступна. Попробуйте позже."
                else -> "Не удалось подтвердить токен T-Invest."
            }
        }
        return BackendResult.Failure(
            message = message,
            retryable = status == 429 || status >= 500,
        )
    }

    private fun parsePortfolio(json: JSONObject): PortfolioSnapshot {
        val accountsJson = json.optJSONArray("accounts") ?: JSONArray()
        val accounts = buildList {
            for (index in 0 until accountsJson.length()) {
                val account = accountsJson.getJSONObject(index)
                val positionsJson = account.optJSONArray("positions") ?: JSONArray()
                val positions = buildList {
                    for (positionIndex in 0 until positionsJson.length()) {
                        val position = positionsJson.getJSONObject(positionIndex)
                        add(
                            PortfolioPosition(
                                id = position.getString("id"),
                                title = position.getString("title"),
                                ticker = position.optNullableString("ticker"),
                                quantity = position.optNullableObject("quantity")?.let(::parseDecimal),
                                currentValue = position.optNullableObject("currentValue")?.let(::parseMoney),
                                expectedYieldPercent = position
                                    .optNullableObject("expectedYieldPercent")
                                    ?.let(::parseDecimal),
                            ),
                        )
                    }
                }
                add(
                    PortfolioAccount(
                        id = account.getString("id"),
                        name = account.getString("name"),
                        totalValue = parseMoney(account.getJSONObject("totalValue")),
                        expectedYieldPercent = account
                            .optNullableObject("expectedYieldPercent")
                            ?.let(::parseDecimal),
                        positions = positions,
                    ),
                )
            }
        }

        val allocationsJson = json.optJSONArray("allocations") ?: JSONArray()
        val allocations = buildList {
            for (index in 0 until allocationsJson.length()) {
                val allocation = allocationsJson.getJSONObject(index)
                add(
                    PortfolioAllocation(
                        title = allocation.getString("title"),
                        sharePercent = parseDecimal(allocation.getJSONObject("sharePercent")),
                    ),
                )
            }
        }

        return PortfolioSnapshot(
            totalValue = parseMoney(json.getJSONObject("totalValue")),
            expectedYieldAmount = json.optNullableObject("expectedYieldAmount")?.let(::parseMoney),
            expectedYieldPercent = json
                .optNullableObject("expectedYieldPercent")
                ?.let(::parseDecimal),
            accounts = accounts,
            allocations = allocations,
        )
    }

    private fun parseMoney(json: JSONObject): MoneyAmount = MoneyAmount(
        value = parseDecimal(json.getJSONObject("value")),
        currency = json.getString("currency"),
    )

    private fun parseDecimal(json: JSONObject): ApiDecimal = ApiDecimal(
        units = json.get("units").toString().toLong(),
        nano = json.optInt("nano"),
    )

    private fun JSONObject.optNullableObject(key: String): JSONObject? {
        if (!has(key) || isNull(key)) {
            return null
        }
        return getJSONObject(key)
    }

    private fun parseSession(json: JSONObject): AnalystSession {
        return AnalystSession(
            accessToken = json.getString("access_token"),
            expiresInSeconds = json.getLong("expires_in"),
            user = parseUser(json.getJSONObject("user")),
        )
    }

    private fun parseUser(json: JSONObject): AnalystUser {
        return AnalystUser(
            telegramId = json.get("telegram_id").toString(),
            name = json.optNullableString("name"),
            username = json.optNullableString("username"),
            pictureUrl = json.optNullableString("picture"),
        )
    }

    private fun JSONObject.optNullableString(key: String): String? {
        if (isNull(key)) {
            return null
        }
        return optString(key).takeIf { it.isNotBlank() }
    }

    private companion object {
        const val CONNECT_TIMEOUT_MS = 10_000
        const val READ_TIMEOUT_MS = 15_000
    }
}

