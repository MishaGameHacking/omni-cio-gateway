package ru.omnicio.app.ui

import java.io.IOException
import java.math.BigDecimal
import java.net.CookieManager
import java.net.CookiePolicy
import java.net.URI
import java.time.Instant
import javax.net.ssl.HttpsURLConnection
import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject

internal const val SERVER_ORIGIN = "https://omnicio.ru"
private const val MAX_RESPONSE_BYTES = 4 * 1024 * 1024

internal class ApiFailure(val status: Int, val code: String) : IOException()

/** One session, one memory-only cookie jar; never a global CookieHandler or disk cache. */
internal class ServerApi {
    private val cookies = CookieManager(null, CookiePolicy.ACCEPT_ORIGINAL_SERVER)
    var profile: String? = null
        private set
    private var build: String? = null

    fun request(path: String, method: String = "GET", body: JSONObject? = null): JSONObject {
        require(path.startsWith("/api/") && !path.contains("..") && !path.contains('#'))
        val uri = URI(SERVER_ORIGIN + path)
        val connection = uri.toURL().openConnection() as HttpsURLConnection
        try {
            connection.requestMethod = method
            connection.instanceFollowRedirects = false
            connection.useCaches = false
            connection.connectTimeout = 15_000
            connection.readTimeout = 30_000
            connection.setRequestProperty("Accept", "application/json")
            connection.setRequestProperty("Cache-Control", "no-store")
            connection.setRequestProperty("Origin", SERVER_ORIGIN)
            profile?.let { connection.setRequestProperty("X-Omnicio-Profile", it) }
            build?.let { connection.setRequestProperty("X-Omnicio-Client-Build", it) }
            cookies.get(uri, emptyMap()).forEach { (key, values) ->
                connection.setRequestProperty(key, values.joinToString("; "))
            }
            if (body != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
            val status = connection.responseCode
            val headers = connection.headerFields.filterKeys { it != null }
            cookies.put(uri, headers)
            connection.getHeaderField("X-Omnicio-Build")?.takeIf {
                it.matches(Regex("[0-9a-f]{12}"))
            }?.let { build = it }
            val stream = if (status in 200..299) connection.inputStream else connection.errorStream
            val bytes = stream?.use { input ->
                val output = java.io.ByteArrayOutputStream()
                val buffer = ByteArray(8192)
                while (output.size() <= MAX_RESPONSE_BYTES) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    output.write(buffer, 0, count)
                }
                output.toByteArray()
            } ?: byteArrayOf()
            if (bytes.size > MAX_RESPONSE_BYTES) throw ApiFailure(status, "response_too_large")
            val text = bytes.toString(Charsets.UTF_8)
            val json = if (text.isBlank()) JSONObject() else try {
                JSONObject(text)
            } catch (_: JSONException) {
                throw ApiFailure(status, "invalid_response")
            }
            if (status !in 200..299) {
                throw ApiFailure(status, json.opt("detail") as? String ?: "request_failed")
            }
            return json
        } finally {
            connection.disconnect()
        }
    }

    fun acceptLogin(result: JSONObject) {
        val id = result.getString("public_id")
        if (!id.matches(Regex("[0-9]{9}"))) throw ApiFailure(200, "invalid_response")
        profile = id
    }

    fun workspace(): ServerWorkspace {
        val root = request("/api/mobile/workspace")
        if (root.getInt("contract_version") != 1 || root.getString("public_id") != profile) {
            throw ApiFailure(409, "profile_context_changed")
        }
        val connection = root.getJSONObject("connection")
        val portfolio = root.getJSONObject("portfolio")
        val latest = portfolio.optJSONObject("latest")
        val events = root.getJSONObject("events")
        return ServerWorkspace(
            ServerConnection(connection.getBoolean("connected"), connection.text("account_name"),
                connection.text("verified_at")),
            latest?.let { parsePortfolio(it, portfolio.getJSONArray("history")) },
            parseEvents(events), events.text("next_cursor"),
            root.getJSONObject("goals").getJSONArray("items").objects().map {
                ServerGoal(it.getString("id"), it.getString("title"), it.decimal("target_amount_rub"),
                    it.text("target_date"), it.text("status"))
            },
        )
    }

    private fun parsePortfolio(latest: JSONObject, history: JSONArray): ServerPortfolio = ServerPortfolio(
        capturedAt = latest.text("captured_at"), freshness = latest.text("snapshot_freshness"),
        analysisStatus = latest.text("analysis_status"), total = latest.decimal("nav_rub"),
        cash = latest.decimal("rub_cash_total"),
        freeCash = if (latest.optBoolean("limits_loading_in_progress", true)) null
            else latest.decimal("rub_cash_unblocked"),
        blockedCash = latest.decimal("rub_cash_blocked"),
        positions = latest.getJSONArray("positions").objects().map {
            PortfolioPosition(it.getString("instrument_uid"), it.text("ticker").orEmpty(),
                it.text("name").orEmpty(), it.decimal("quantity"), it.decimal("value_rub"),
                it.decimal("current_price_value"), it.text("current_price_currency"),
                it.decimal("nav_percent"), it.optBoolean("blocked", false), it.text("risk_state"))
        },
        history = history.objects().map {
            HistoryPoint(Instant.parse(it.getString("captured_at")), it.decimal("nav_rub"),
                it.text("analysis_status") == "observed")
        }.sortedBy { it.at },
        sources = latest.optJSONArray("sources")?.objects()?.map {
            SourceInfo(it.getString("name"), it.text("url"), it.text("retrieved_at"), it.text("status"))
        }.orEmpty(),
    )
}

internal fun JSONObject.text(key: String): String? = if (isNull(key)) null else getString(key)
internal fun JSONObject.decimal(key: String): BigDecimal? {
    if (isNull(key)) return null
    return get(key).toString().takeIf { it.length <= 100 }?.toBigDecimalOrNull()
        ?.takeIf { it.precision() <= 40 && it.scale() in -18..18 }
        ?: throw ApiFailure(200, "invalid_number")
}
internal fun JSONArray.objects(): List<JSONObject> = (0 until length()).map { getJSONObject(it) }
internal fun parseEvents(root: JSONObject): List<ServerEvent> = root.getJSONArray("items").objects().map {
    val source = it.optJSONObject("source")
    ServerEvent(it.getString("id"), it.getString("title"), it.text("detail").orEmpty(),
        it.text("occurred_at"), it.text("severity"),
        source?.text("name"), !it.isNull("read_at"))
}

internal fun apiError(error: Exception): String = when {
    error is ApiFailure && error.code == "server_update_required" ->
        "Сервер ещё не поддерживает эту версию приложения. Требуется обновление OMNICIO на сервере."
    error is ApiFailure && error.code == "email_or_password_invalid" -> "Проверьте почту и пароль."
    error is ApiFailure && error.code == "email_code_invalid_or_expired" -> "Код неверный или истёк. Запросите новый."
    error is ApiFailure && error.code == "updated_legal_consent_required" ->
        "Требуется принять обновлённые условия в личном кабинете OMNICIO."
    error is ApiFailure && error.status == 401 -> "Сессия завершена. Войдите снова."
    error is ApiFailure && error.status == 409 -> "Данные или условия изменились. Обновите экран перед повтором."
    error is ApiFailure && error.status == 429 -> "Слишком много запросов. Повторите позже."
    error is ApiFailure && error.status in 400..499 -> "Запрос отклонён. Проверьте введённые данные и доступ к счёту."
    error is ApiFailure -> "Сервер не предоставил корректные данные. Попробуйте обновить экран."
    error is JSONException || error is java.time.DateTimeException -> "Формат ответа сервера не поддерживается."
    else -> "Не удалось связаться с сервером. Проверьте интернет и повторите запрос."
}
