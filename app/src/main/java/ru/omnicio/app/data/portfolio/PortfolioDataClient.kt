package ru.omnicio.app.data.portfolio

import java.net.URI
import java.net.URLEncoder
import javax.net.ssl.HttpsURLConnection
import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.data.backend.BackendConfig
import ru.omnicio.app.data.backend.BackendResult

class PortfolioDataClient {
    fun portfolio(token: String, currency: PortfolioCurrency): BackendResult<PortfolioSnapshot> =
        when (val response = get(token, "/tinvest/dashboard?currency=${currency.name}")) {
            is BackendResult.Failure -> response
            is BackendResult.Success -> try {
                BackendResult.Success(parsePortfolio(response.value))
            } catch (_: Exception) {
                BackendResult.Failure("Не удалось прочитать портфель. Последние данные сохранены на экране.", true)
            }
        }

    fun details(token: String, accountId: String, section: String, parameters: Map<String, String> = emptyMap()): BackendResult<JSONObject> {
        require(section in setOf("operations", "orders", "analytics", "payments"))
        val query = parameters.entries.joinToString("&") { "${encode(it.key)}=${encode(it.value)}" }
        return get(token, "/tinvest/accounts/${encode(accountId)}/$section?$query")
    }

    private fun encode(text: String): String = URLEncoder.encode(text, "UTF-8")

    private fun get(token: String, path: String): BackendResult<JSONObject> {
        var connection: HttpsURLConnection? = null
        return try {
            connection = BackendConfig.openConnection(URI(BackendConfig.BASE_URL + path))
            ru.omnicio.app.data.updates.ClientVersion.attach(connection)
            connection.requestMethod = "GET"
            connection.instanceFollowRedirects = false
            connection.connectTimeout = 10_000
            connection.readTimeout = 45_000
            connection.setRequestProperty("Authorization", "Bearer $token")
            connection.setRequestProperty("Accept", "application/json")
            val status = connection.responseCode
            ru.omnicio.app.data.updates.ClientVersion.observeStatus(status)
            if (status in 200..299) {
                val bytes = connection.inputStream.use { it.readNBytes(2_000_001) }
                require(bytes.size <= 2_000_000)
                BackendResult.Success(JSONObject(String(bytes, Charsets.UTF_8)))
            } else {
                val message = when (status) {
                    426 -> "Обновите Analyst AI, чтобы продолжить."
                    401, 403 -> "Сеанс истёк. Войдите через Telegram заново."
                    409 -> "Подключите T‑API в профиле."
                    422 -> "Проверьте токен T‑Invest и его права в профиле."
                    404 -> "Данные счёта недоступны. Возможно, сервер ещё обновляется."
                    400 -> "Проверьте выбранный период. Даты в будущем недоступны."
                    else -> "Не удалось обновить данные. Повторная проверка будет выполнена автоматически."
                }
                BackendResult.Failure(message, status == 429 || status >= 500 || status == 404 || status == 426)
            }
        } catch (_: Exception) {
            BackendResult.Failure("Нет связи с сервером. Показаны последние успешно полученные данные.", true)
        } finally {
            connection?.disconnect()
        }
    }

    private fun parsePortfolio(json: JSONObject): PortfolioSnapshot = PortfolioSnapshot(
        totalValue = parseMoney(json.getJSONObject("totalValue")),
        expectedYieldAmount = json.money("expectedYieldAmount"),
        expectedYieldPercent = json.decimal("expectedYieldPercent"),
        accounts = json.objects("accounts").map { account ->
            PortfolioAccount(
                id = account.getString("id"), name = account.getString("name"),
                totalValue = parseMoney(account.getJSONObject("totalValue")),
                expectedYieldPercent = account.decimal("expectedYieldPercent"),
                positions = account.objects("positions").map(::parsePosition),
                dailyYieldAmount = account.money("dailyYieldAmount"),
                dailyYieldPercent = account.decimal("dailyYieldPercent"),
                allocations = parseAllocations(account), openedAt = account.nullableText("openedAt"),
                accountType = account.nullableText("accountType"),
                limitsLoading = account.optBoolean("limitsLoading"),
                virtualPositions = account.objects("virtualPositions").map(::parsePosition),
            )
        },
        allocations = parseAllocations(json), asOf = json.nullableText("asOf"),
        warnings = (json.optJSONArray("warnings") ?: JSONArray()).let { values ->
            (0 until values.length()).map { values.getString(it) }
        },
    )

    private fun parsePosition(json: JSONObject) = PortfolioPosition(
        id = json.getString("id"), title = json.getString("title"), ticker = json.nullableText("ticker"),
        quantity = json.decimal("quantity"), currentValue = json.money("currentValue"),
        expectedYieldPercent = json.decimal("expectedYieldPercent"),
        currentPrice = json.money("currentPrice"), averagePrice = json.money("averagePrice"),
        expectedYieldAmount = json.money("expectedYieldAmount"), dailyYieldAmount = json.money("dailyYieldAmount"),
        currentNkd = json.money("currentNkd"), blocked = json.optBoolean("blocked"),
        blockedQuantity = json.decimal("blockedQuantity"), instrumentType = json.optString("instrumentType"),
        sector = json.nullableText("sector"), company = json.nullableText("company"),
        isin = json.nullableText("isin"), exchange = json.nullableText("exchange"),
    )

    private fun parseAllocations(json: JSONObject) = json.objects("allocations").map {
        PortfolioAllocation(it.getString("title"), parseDecimal(it.getJSONObject("sharePercent")))
    }
}

internal fun JSONObject.objects(key: String): List<JSONObject> =
    (optJSONArray(key) ?: JSONArray()).let { array -> (0 until array.length()).mapNotNull(array::optJSONObject) }
internal fun JSONObject.nullableText(key: String): String? =
    if (isNull(key)) null else optString(key).takeIf { it.isNotBlank() }
internal fun parseDecimal(json: JSONObject) = ApiDecimal(json.optString("units", "0").toLong(), json.optInt("nano"))
internal fun parseMoney(json: JSONObject) = MoneyAmount(parseDecimal(json.getJSONObject("value")), json.getString("currency"))
internal fun JSONObject.money(key: String): MoneyAmount? = optJSONObject(key)?.let(::parseMoney)
internal fun JSONObject.decimal(key: String): ApiDecimal? = optJSONObject(key)?.let(::parseDecimal)
