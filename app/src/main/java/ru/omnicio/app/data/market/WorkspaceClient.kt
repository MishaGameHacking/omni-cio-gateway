package ru.omnicio.app.data.market

import androidx.activity.ComponentActivity
import androidx.activity.compose.LocalActivity
import androidx.compose.runtime.*
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import ru.omnicio.app.data.backend.BackendConfig
import ru.omnicio.app.data.backend.BackendResult
import ru.omnicio.app.data.updates.ClientVersion
import ru.omnicio.app.data.workspace.LocalPortfolioReadSource
import ru.omnicio.app.ui.workspace.LocalWorkspaceSession
import java.net.URI
import java.net.URLEncoder
import javax.net.ssl.HttpsURLConnection

/** Only the application's authenticated read-only workspace endpoints. */
class WorkspaceClient {
    fun read(token: String, path: String = "/workspace", parameters: Map<String, String> = emptyMap()): BackendResult<JSONObject> {
        if (token.isBlank()) return BackendResult.Failure("Нужен действующий сеанс Analyst AI.", false)
        if (!path.matches(Regex("/workspace(?:/instruments/[A-Za-z0-9:_-]{1,128}/(?:candles|dossier))?")))
            return BackendResult.Failure("Неизвестный раздел данных.", false)
        val query = parameters.entries.sortedBy { it.key }.joinToString("&") {
            URLEncoder.encode(it.key, "UTF-8") + "=" + URLEncoder.encode(it.value, "UTF-8")
        }
        var connection: HttpsURLConnection? = null
        return try {
            connection = URI(BackendConfig.BASE_URL + path + if (query.isEmpty()) "" else "?$query").toURL()
                .openConnection() as HttpsURLConnection
            connection.apply {
                requestMethod = "GET"; instanceFollowRedirects = false
                connectTimeout = 10_000; readTimeout = 45_000
                setRequestProperty("Accept", "application/json")
                setRequestProperty("Authorization", "Bearer $token")
                ClientVersion.attach(this)
            }
            val status = connection.responseCode
            ClientVersion.observeStatus(status)
            ru.omnicio.app.data.backend.SessionExpiry.observe(status, token)
            when (status) {
                200 -> {
                    val body = connection.inputStream.bufferedReader(Charsets.UTF_8).use { reader ->
                        val output = StringBuilder(); val buffer = CharArray(4096)
                        while (true) {
                            val n = reader.read(buffer); if (n < 0) break
                            require(output.length + n <= 2_000_000)
                            output.append(buffer, 0, n)
                        }
                        output.toString()
                    }
                    val json = JSONObject(body)
                    require(json.optInt("schema_version") == 1)
                    BackendResult.Success(json)
                }
                401, 403 -> BackendResult.Failure("Сеанс больше не подтверждён. Войдите заново.", false)
                404 -> BackendResult.Failure("Сведения для этого инструмента не найдены.", false)
                409 -> BackendResult.Failure("Проверьте подключение счёта в профиле.", false)
                422 -> BackendResult.Failure("Источник не поддерживает выбранный инструмент или период. Измените запрос.", false)
                426 -> BackendResult.Failure("Для доступа к данным требуется обновление приложения.", false)
                429 -> BackendResult.Failure("Источник ограничил частоту запросов. Повторите немного позже.", true)
                else -> BackendResult.Failure("Не удалось обновить сведения из источника.", status >= 500)
            }
        } catch (_: Exception) { BackendResult.Failure("Не удалось получить сведения. Проверьте соединение и повторите запрос.", true) }
        finally { connection?.disconnect() }
    }
}

data class WorkspaceRequest(val json: JSONObject?, val loading: Boolean, val error: String?,
    val showingPreviousQuery: Boolean, val displayedParameters: Map<String, String>, val refresh: () -> Unit)

@Composable
fun rememberWorkspaceRequest(path: String = "/workspace", parameters: Map<String, String> = emptyMap(),
    refreshKey: Int = 0): WorkspaceRequest {
    val token = LocalWorkspaceSession.current.token
    val lifecycle = (LocalActivity.current as? ComponentActivity)?.lifecycle
    var active by remember(lifecycle) { mutableStateOf(lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) == true) }
    var json by remember(token, path) { mutableStateOf<JSONObject?>(null) }
    var displayed by remember(token, path) { mutableStateOf<Map<String, String>>(emptyMap()) }
    var loading by remember(token, path) { mutableStateOf(false) }
    var error by remember(token, path) { mutableStateOf<String?>(null) }
    var attempt by remember(token, path) { mutableIntStateOf(0) }
    var generation by remember(token, path) { mutableIntStateOf(0) }
    val client = LocalPortfolioReadSource.current
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, _ -> active = lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) == true }
        lifecycle?.addObserver(observer)
        onDispose { lifecycle?.removeObserver(observer) }
    }
    LaunchedEffect(client, token, path, parameters, attempt, active, refreshKey) {
        val requestId = ++generation
        if (!active || token.isBlank()) { loading = false; return@LaunchedEffect }
        loading = true; error = null
        try {
            val result = withContext(Dispatchers.IO) { client.workspace(token, path, parameters) }
            if (requestId == generation) when (result) {
                is BackendResult.Success -> { json = result.value; displayed = parameters.toMap() }
                is BackendResult.Failure -> error = result.message
            }
        } finally { if (requestId == generation) loading = false }
    }
    return WorkspaceRequest(json, loading, error, json != null && displayed != parameters, displayed) { attempt++ }
}

fun JSONObject.section(name: String): JSONObject? = optJSONObject("sections")?.optJSONObject(name)
fun JSONObject.sectionData(name: String): JSONObject? = section(name)?.optJSONObject("data")
fun JSONObject.records(key: String): List<JSONObject> = optJSONArray(key)?.let { values ->
    (0 until values.length()).mapNotNull(values::optJSONObject)
} ?: emptyList()
fun JSONObject.optionalText(key: String): String? = (opt(key) as? String)?.takeIf(String::isNotBlank)
fun JSONObject.stringList(key: String): List<String> = optJSONArray(key)?.let { values ->
    (0 until values.length()).mapNotNull { values.opt(it) as? String }
} ?: emptyList()
