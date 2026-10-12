package ru.omnicio.app.data.backend

import java.net.HttpURLConnection
import java.net.URI
import javax.net.ssl.HttpsURLConnection
import org.json.JSONObject

class AnalystBackendClient(
    private val baseUrl: String = BackendConfig.BASE_URL,
) {
    fun exchangeTelegramCode(code: String): BackendResult<AnalystSession> {
        val response = request(
            method = "POST",
            path = "/auth/session",
            body = JSONObject().put("code", code.trim()).toString(),
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
    ): BackendResult<String> {
        val connection = runCatching {
            (URI(baseUrl + path).toURL().openConnection() as HttpsURLConnection).apply {
                requestMethod = method
                connectTimeout = CONNECT_TIMEOUT_MS
                readTimeout = READ_TIMEOUT_MS
                setRequestProperty("Accept", "application/json")
                if (bearer != null) {
                    setRequestProperty("Authorization", "Bearer $bearer")
                }
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
            val responseBody = if (status in 200..299) {
                connection.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
            } else {
                connection.errorStream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
            }

            when {
                status in 200..299 -> BackendResult.Success(responseBody)
                status == HttpURLConnection.HTTP_UNAUTHORIZED ||
                    status == HttpURLConnection.HTTP_FORBIDDEN -> {
                    BackendResult.Failure(
                        "Сеанс недействителен или доступ отклонён.",
                        retryable = false,
                    )
                }
                status == 429 || status >= 500 -> {
                    BackendResult.Failure(
                        "Сервис временно недоступен. Попробуйте ещё раз.",
                        retryable = true,
                    )
                }
                else -> {
                    val detail = runCatching {
                        JSONObject(responseBody).optString("detail")
                    }.getOrNull()
                    BackendResult.Failure(
                        detail?.takeIf { it.isNotBlank() }
                            ?: "Сервер отклонил запрос.",
                        retryable = false,
                    )
                }
            }
        } catch (_: Exception) {
            BackendResult.Failure(
                "Не удалось связаться с сервером Analyst AI.",
                retryable = true,
            )
        } finally {
            connection.disconnect()
        }
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
