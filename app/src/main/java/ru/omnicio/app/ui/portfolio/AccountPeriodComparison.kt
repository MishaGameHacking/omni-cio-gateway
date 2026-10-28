package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.data.portfolio.PortfolioAccount
import ru.omnicio.app.data.portfolio.objects
import ru.omnicio.app.ui.spatial.SpatialBars
import ru.omnicio.app.ui.spectrum.SpectrumCard
import ru.omnicio.app.ui.workspace.*
import java.math.BigDecimal
import java.time.LocalDate

internal data class AccountPeriodObservation(val first: HistoryPoint, val last: HistoryPoint, val change: BigDecimal)

internal fun accountPeriodObservation(json: JSONObject): AccountPeriodObservation? {
    val points = json.objects("history").mapNotNull { row -> row.optString("value").toBigDecimalOrNull()?.let { HistoryPoint(row.optString("date"), it) } }
    val history = portfolioHistory(points)?.coordinates?.map { it.point } ?: return null
    if (history.size < 2) return null
    return AccountPeriodObservation(history.first(), history.last(), history.last().value.subtract(history.first().value))
}

@Composable
internal fun AccountPeriodComparison(token: String, account: PortfolioAccount) {
    val today = remember { LocalDate.now(Moscow) }
    var firstStart by rememberSaveable(account.id) { mutableStateOf<String?>(today.minusMonths(1).toString()) }
    var firstEnd by rememberSaveable(account.id) { mutableStateOf<String?>(today.toString()) }
    var secondStart by rememberSaveable(account.id) { mutableStateOf<String?>(today.minusMonths(2).toString()) }
    var secondEnd by rememberSaveable(account.id) { mutableStateOf<String?>(today.minusMonths(1).minusDays(1).toString()) }
    val firstPeriod = PortfolioPeriod(firstStart, firstEnd)
    val secondPeriod = PortfolioPeriod(secondStart, secondEnd)
    val first = rememberAccountData(token, account.id, "analytics", firstPeriod.parameters() + ("currency" to account.totalValue.currency), interval = 60_000)
    val second = rememberAccountData(token, account.id, "analytics", secondPeriod.parameters() + ("currency" to account.totalValue.currency), interval = 60_000)
    SpectrumCard {
        Text("Два фактических периода", style = MaterialTheme.typography.titleLarge)
        Text("Период А", style = MaterialTheme.typography.titleMedium)
        PeriodControls(firstPeriod) { firstStart = it.start; firstEnd = it.end }
        Text("Период Б", style = MaterialTheme.typography.titleMedium)
        PeriodControls(secondPeriod) { secondStart = it.start; secondEnd = it.end }
        AccountDataNotice(first); AccountDataNotice(second)
        val a = first.json?.takeIf { !first.showingPreviousQuery }
        val b = second.json?.takeIf { !second.showingPreviousQuery }
        if (a == null || b == null) { Text("Оба запроса должны завершиться с выбранными параметрами."); return@SpectrumCard }
        val ao = accountPeriodObservation(a); val bo = accountPeriodObservation(b)
        val currency = a.optString("currency")
        val comparable = currency.isNotBlank() && currency == b.optString("currency")
        if (comparable && !LocalWorkspacePreferences.current.value.hideHomeBalance) {
            val values = listOf(ao?.change?.toDouble(), bo?.change?.toDouble())
            if (values.any { it != null }) SpatialBars(values, minOf(0.0, values.filterNotNull().minOrNull() ?: 0.0),
                maxOf(0.0, values.filterNotNull().maxOrNull() ?: 0.0), modifier = Modifier.fillMaxWidth().height(120.dp))
            Text("Изменение оценки: А слева, Б справа · $currency", style = MaterialTheme.typography.bodySmall)
        } else if (!comparable) Text("Оценки в разных валютах; совместная шкала не применяется.")
        listOf(Triple("А", a, ao), Triple("Б", b, bo)).forEach { (label, data, result) ->
            Text("Период $label", style = MaterialTheme.typography.titleMedium)
            if (result == null) Text("Недостаточно сохранённых снимков для изменения стоимости.")
            else {
                DataRow("Первый фактический снимок · ${dateText(result.first.date)}", "${decimalText(result.first.value)} ${data.optString("currency")}")
                DataRow("Последний фактический снимок · ${dateText(result.last.date)}", "${decimalText(result.last.value)} ${data.optString("currency")}")
                DataRow("Изменение оценки", "${decimalText(result.change)} ${data.optString("currency")}")
            }
            if (data.optBoolean("historyTruncated")) Notice("История этого периода ограничена источником.")
            CashFlowSummary(data)
        }
        Text("Столбцы сравнивают наблюдаемое изменение баланса. Разная длина периодов, пополнения и выводы не превращаются в сравнение доходности.", style = MaterialTheme.typography.bodySmall)
        if (!LocalWorkspacePreferences.current.value.hideHomeBalance) {
            val archive = JSONObject().put("comparison", JSONArray(listOf(Triple("А", a, ao), Triple("Б", b, bo)).map { (label, data, result) ->
                JSONObject().put("title", "Период $label · ${account.name}").put("values", JSONArray(listOf(
                    "Первая дата наблюдения" to (result?.first?.date ?: "Нет"), "Последняя дата наблюдения" to (result?.last?.date ?: "Нет"),
                    "Изменение стоимости" to (result?.change?.toPlainString()?.plus(" ${data.optString("currency")}") ?: "Не определено"),
                    "Денежные потоки" to if (data.optBoolean("complete")) "Получены полностью" else "Неполные"
                ).map { (name, value) -> JSONObject().put("label", name).put("value", value) }))
            })).put("raw_periods", JSONArray(listOf(a, b)))
            SaveResearchButton(archive, "${account.name}: два периода", start = firstStart, end = firstEnd, source = "T‑Invest · операции и история снимков Analyst AI")
        }
    }
}
