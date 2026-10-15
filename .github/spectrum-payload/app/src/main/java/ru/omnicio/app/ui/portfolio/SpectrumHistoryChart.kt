package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import ru.omnicio.app.data.portfolio.PortfolioSnapshot
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette
import java.time.LocalDate

/** Reads saved observations only. No synthetic price line is ever generated in production. */
@Composable
internal fun DashboardHistory(token: String, snapshot: PortfolioSnapshot) {
    val account = snapshot.accounts.singleOrNull()
    if (account == null) {
        Notice("История доступна отдельно по каждому счёту в разделе «Портфель».")
        return
    }
    if (token.isBlank()) {
        Notice("Исторические значения появятся после получения данных счёта.")
        return
    }
    var period by rememberSaveable(account.id) { mutableIntStateOf(2) }
    ChoiceRow(listOf("1Д", "1Н", "1М", "6М", "1Г", "Всё"), period) { period = it }
    val today = LocalDate.now(Moscow)
    val start = when (period) { 0 -> today; 1 -> today.minusWeeks(1); 2 -> today.minusMonths(1); 3 -> today.minusMonths(6); 4 -> today.minusYears(1); else -> null }
    val query = buildMap { put("currency", snapshot.totalValue.currency); start?.let { put("start", it.toString()) } }
    val request = rememberAccountData(token, account.id, "analytics", query, interval = 60_000)
    if (request.showingPreviousQuery || request.error != null) AccountDataNotice(request)
    val json = request.json
    if (json == null) {
        Notice(if (request.loading) "Получаем историю стоимости…" else "История пока не получена.")
        return
    }
    val points = remember(json) { validatedHistoryPoints(json) }
    if (points == null) {
        Notice("Историю нельзя отобразить: часть наблюдений имеет неверный формат.")
        return
    }
    HistoryChart(points, json.optString("currency"), compact = true)
    if (json.optBoolean("historyTruncated")) Notice("История ограничена сервером. Выберите более короткий период.")
}

internal fun validatedHistoryPoints(json: JSONObject): List<HistoryPoint>? {
    val rows = json.optJSONArray("history") ?: return null
    if (rows.length() > 10000) return null
    val points = ArrayList<HistoryPoint>(rows.length())
    for (i in 0 until rows.length()) {
        val row = rows.optJSONObject(i) ?: return null
        val value = row.optString("value").toBigDecimalOrNull() ?: return null
        val date = row.optString("date").takeIf { it.isNotBlank() } ?: return null
        points.add(HistoryPoint(date, value))
    }
    return points
}

@Composable
internal fun HistoryChart(points: List<HistoryPoint>, currency: String, compact: Boolean = false) {
    if (points.size < 2) {
        Notice(if (points.isEmpty()) "В этом периоде ещё нет сохранённых снимков стоимости." else "Первый снимок получен. Линия появится после следующего измерения.")
        return
    }
    val geometry = remember(points) { portfolioHistory(points) }
    if (geometry == null) {
        Notice("Историю нельзя корректно отобразить: проверьте даты и значения. Пропуски не заменяются нулями.")
        return
    }
    val data = geometry.coordinates
    if (!compact) Text(decimalText(data.last().point.value) + " " + currencySymbol(currency), fontWeight = FontWeight.Bold)
    HistoryLine(data, currency, compact)
    DataRow(dateText(data.first().point.date, "dd.MM.yy"), dateText(data.last().point.date, "dd.MM.yy"))
    Notice(if (compact) "Стоимость счёта, не график доходности." else "Сохранённые снимки стоимости. Пополнения и выводы также меняют баланс; история до подключения не восстанавливается.")
    HistoryValues(data, currency)
}

@Composable
private fun HistoryLine(data: List<HistoryCoordinate>, currency: String, compact: Boolean) {
    val accent = LocalSpectrumPalette.current.emerald
    val grid = MaterialTheme.colorScheme.outlineVariant.copy(alpha = .55f)
    Canvas(Modifier.fillMaxWidth().height(if (compact) 116.dp else 180.dp).semantics {
        contentDescription = "Стоимость счёта: ${data.size} снимков, от ${decimalText(data.first().point.value)} до ${decimalText(data.last().point.value)} $currency. Таблица доступна кнопкой «Значения графика»."
    }) {
        if (size.width <= 0f || size.height <= 0f) return@Canvas
        val inset = 5.dp.toPx()
        val height = (size.height - inset * 2f).coerceAtLeast(1f)
        val width = (size.width - inset * 2f).coerceAtLeast(1f)
        repeat(3) { i ->
            val y = inset + i * height / 2f
            drawLine(grid, Offset(inset, y), Offset(size.width - inset, y), .6.dp.toPx())
        }
        val line = Path()
        data.forEachIndexed { index, point ->
            val x = inset + point.x * width
            val y = inset + point.y * height
            if (index == 0) line.moveTo(x, y) else line.lineTo(x, y)
        }
        val fill = Path().apply {
            addPath(line)
            lineTo(inset + data.last().x * width, size.height - inset)
            lineTo(inset + data.first().x * width, size.height - inset)
            close()
        }
        drawPath(fill, Brush.verticalGradient(listOf(accent.copy(alpha = .18f), Color.Transparent)))
        drawPath(line, accent.copy(alpha = .12f), style = Stroke(7.dp.toPx(), cap = StrokeCap.Round))
        drawPath(line, accent, style = Stroke(2.dp.toPx(), cap = StrokeCap.Round))
        val end = Offset(inset + data.last().x * width, inset + data.last().y * height)
        drawCircle(accent.copy(alpha = .16f), 7.dp.toPx(), end)
        drawCircle(accent, 3.dp.toPx(), end)
    }
}

@Composable
private fun HistoryValues(data: List<HistoryCoordinate>, currency: String) {
    var expanded by remember(currency) { mutableStateOf(false) }
    var page by remember(currency) { mutableIntStateOf(0) }
    TextButton(onClick = { expanded = !expanded }, modifier = Modifier.heightIn(min = 48.dp)) {
        Text(if (expanded) "Скрыть значения графика" else "Значения графика")
    }
    if (!expanded) return
    val window = historyWindow(data.size, page)
    for (index in window.first until window.end) {
        val point = data[index].point
        DataRow(dateText(point.date), decimalText(point.value) + " " + currencySymbol(currency))
    }
    Notice("Показаны ${window.first + 1}–${window.end} из ${data.size} снимков.")
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        TextButton(onClick = { page = window.page - 1 }, enabled = window.page > 0, modifier = Modifier.weight(1f)) { Text("Предыдущие") }
        TextButton(onClick = { page = window.page + 1 }, enabled = window.page + 1 < window.pages, modifier = Modifier.weight(1f)) { Text("Следующие") }
    }
}
