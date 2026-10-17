package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.data.market.*
import ru.omnicio.app.ui.spatial.SpatialBars
import ru.omnicio.app.ui.spectrum.SpectrumCard
import ru.omnicio.app.ui.workspace.*
import java.math.BigDecimal
import java.math.RoundingMode
import java.time.LocalDate

internal data class ComparableQuotePeriod(val start: String, val end: String, val openings: List<BigDecimal>, val closings: List<BigDecimal>)

/** All instruments must have complete observations at exactly the same timestamps. */
internal fun comparableQuotePeriod(series: List<CandleSnapshot>): ComparableQuotePeriod? {
    if (series.size !in 2..3 || series.any { it.state !in setOf("available", "partial") }) return null
    if (series.any { it.unit !in setOf("quote_currency", "percent_of_nominal", "points") }) return null
    if (series.map { it.unit to it.currency }.distinct().size != 1 || series.map { it.interval }.distinct().size != 1) return null
    if (series.any { it.unit == "quote_currency" && (it.currency == null || !it.currency.matches(Regex("[A-Z]{3}"))) }) return null
    val byTime = series.map { snapshot -> snapshot.candles.filter { it.isComplete }.associateBy { it.time } }
    val common = byTime.map { it.keys }.reduce { a, b -> a.intersect(b) }.sorted()
    if (common.size < 2) return null
    val first = common.first(); val last = common.last()
    return ComparableQuotePeriod(first, last, byTime.map { it.getValue(first).close }, byTime.map { it.getValue(last).close })
}

@Composable
internal fun CommonPeriodComparison(rows: List<PortfolioRow>) {
    val instruments = rows.distinctBy { it.position.id }
    var start by rememberSaveable { mutableStateOf<String?>(LocalDate.now().minusMonths(1).toString()) }
    var end by rememberSaveable { mutableStateOf<String?>(LocalDate.now().toString()) }
    val period = PortfolioPeriod(start, end)
    SpectrumCard {
        Text("Сравнить один рыночный период", style = MaterialTheme.typography.titleLarge)
        PeriodControls(period) { selected ->
            val today = LocalDate.now(Moscow)
            start = selected.start ?: today.minusYears(5).toString()
            end = selected.end ?: today.toString()
        }
        if (instruments.size < 2) { Text("Для рыночного сравнения нужны разные инструменты. Позиции одной бумаги на разных счетах имеют одну котировку."); return@SpectrumCard }
        if (start == null || end == null) { Text("Выберите точные границы периода. Котировки за неизвестный интервал не сравниваются."); return@SpectrumCard }
        val requests = instruments.map { row -> key(row.position.id) {
            rememberWorkspaceRequest("/workspace/instruments/${row.position.id}/candles", mapOf("start" to start!!, "end" to end!!, "interval" to "day"))
        } }
        requests.forEachIndexed { index, request ->
            Text(instruments[index].position.ticker ?: instruments[index].position.title, style = MaterialTheme.typography.titleMedium)
            WorkspaceRequestNotice(request)
        }
        val series = requests.mapIndexed { index, request ->
            request.json?.takeIf { !request.showingPreviousQuery }?.let { runCatching { parseCandles(it, instruments[index].position.id) }.getOrNull() }
        }
        if (series.any { it == null }) { Text("Ждём проверенные котировки всех выбранных бумаг."); return@SpectrumCard }
        val actual = series.filterNotNull()
        actual.forEachIndexed { index, sample ->
            Text("${instruments[index].position.ticker ?: instruments[index].position.title}: ${sample.unitLabel}${sample.currency?.let { " · $it" }.orEmpty()}")
            if (sample.state != "available") Text(sample.reason ?: "Выборка котировок неполная.")
        }
        val result = comparableQuotePeriod(actual)
        if (result == null) {
            Text("Совместимая шкала не получена: нужны одинаковые единицы и как минимум две общие завершённые свечи. Валюты не пересчитываются, отсутствующие дни не интерполируются.")
            return@SpectrumCard
        }
        Text("Общие закрытия: ${dateText(result.start, "dd.MM.yyyy")} — ${dateText(result.end, "dd.MM.yyyy")}")
        val differences = result.openings.zip(result.closings).map { (before, after) ->
            if (before.signum() > 0) after.subtract(before).multiply(BigDecimal(100)).divide(before, 10, RoundingMode.HALF_UP) else null
        }
        if (!LocalWorkspacePreferences.current.value.hideHomeBalance) {
            val values = differences.map { it?.toDouble() }
            if (values.any { it != null }) SpatialBars(values, minOf(0.0, values.filterNotNull().minOrNull() ?: 0.0),
                maxOf(0.0, values.filterNotNull().maxOrNull() ?: 0.0), modifier = Modifier.fillMaxWidth().height(130.dp))
            differences.forEachIndexed { index, change ->
                DataRow(instruments[index].position.ticker ?: instruments[index].position.title, change?.let { "${decimalText(it)}%" } ?: "Изменение не определено")
                DataRow("Цена закрытия начала / конца", "${result.openings[index].toPlainString()} / ${result.closings[index].toPlainString()} ${actual[index].unitLabel}")
            }
            val archive = JSONObject().put("comparison", JSONArray(instruments.mapIndexed { index, row ->
                JSONObject().put("title", row.position.title).put("instrument_uid", row.position.id).put("values", JSONArray(listOf(
                    "Начало" to result.start, "Конец" to result.end, "Единица" to actual[index].unitLabel,
                    "Первая цена закрытия" to result.openings[index].toPlainString(), "Последняя цена закрытия" to result.closings[index].toPlainString(),
                    "Изменение цены, %" to (differences[index]?.toPlainString() ?: "Не определено")
                ).map { (label, value) -> JSONObject().put("label", label).put("value", value) }))
            })).put("raw_candles", JSONArray(requests.map { it.json }))
            SaveResearchButton(archive, "Период ${instruments.joinToString(" / ") { it.position.ticker ?: it.position.title }}", start = result.start, end = result.end,
                source = "T‑Invest · GetCandles · общие завершённые свечи", observedAt = actual.mapNotNull { it.asOf }.minOrNull())
        } else Text("Цены и изменения скрыты режимом приватности.")
        Text("Это изменение цены закрытия. Выплаты, комиссии, налоги и индивидуальные сделки не включены.", style = MaterialTheme.typography.bodySmall)
        actual.forEach { SourceProvenance(it.sources) }
    }
}
