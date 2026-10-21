package ru.omnicio.app.data.research

import java.net.URI
import javax.net.ssl.HttpsURLConnection
import org.json.JSONObject
import ru.omnicio.app.data.backend.BackendConfig
import ru.omnicio.app.data.backend.BackendResult
import ru.omnicio.app.data.updates.ClientVersion

class ResearchClient {
    /** Authenticated broker-derived data; no free prompt and no order endpoint. */
    fun read(token: String): BackendResult<JSONObject> {
        var connection: HttpsURLConnection? = null
        return try {
            connection = BackendConfig.openConnection(URI(BackendConfig.BASE_URL + "/analysis/research"))
            connection.apply {
                requestMethod = "GET"
                instanceFollowRedirects = false
                connectTimeout = 10_000
                readTimeout = 60_000
                setRequestProperty("Accept", "application/json")
                setRequestProperty("Authorization", "Bearer $token")
                // The research screen participates in the same compatibility gate.
                ClientVersion.attach(this)
            }
            val status = connection.responseCode
            ClientVersion.observeStatus(status)
            when (status) {
                200 -> {
                    val text = connection.inputStream.bufferedReader(Charsets.UTF_8).use { reader ->
                        val buffer = CharArray(4096)
                        val result = StringBuilder()
                        while (true) {
                            val count = reader.read(buffer)
                            if (count < 0) break
                            require(result.length + count <= 1_000_000) { "Research response too large" }
                            result.append(buffer, 0, count)
                        }
                        result.toString()
                    }
                    BackendResult.Success(JSONObject(text))
                }
                401, 403 -> BackendResult.Failure("Войдите в Analyst AI заново.", retryable = false)
                404 -> BackendResult.Failure("Этот раздел ещё не установлен на сервер. Остальные функции приложения доступны.", retryable = false)
                409 -> BackendResult.Failure("Сначала подключите read-only T‑API в профиле.", retryable = false)
                426 -> BackendResult.Failure("Нужно обновить Analyst AI. Проверка портфеля приостановлена до установки поддерживаемой версии.", retryable = false)
                else -> BackendResult.Failure("Источник данных временно недоступен. Последний результат не является новой проверкой.", retryable = status >= 500 || status == 429)
            }
        } catch (_: Exception) {
            BackendResult.Failure("Не удалось получить проверку портфеля. Данные не подменены примером.", retryable = true)
        } finally {
            connection?.disconnect()
        }
    }
}
