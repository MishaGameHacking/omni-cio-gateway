package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import org.json.JSONObject
import ru.omnicio.app.data.market.optionalText
import ru.omnicio.app.data.market.records
import ru.omnicio.app.ui.portfolio.DataRow
import ru.omnicio.app.ui.portfolio.SourceProvenance
import ru.omnicio.app.ui.portfolio.dateText
import ru.omnicio.app.ui.spectrum.*
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Calendar times are actual broker instants; device/Moscow zones only format them. */
@Composable
internal fun TradingCalendarPanel() {
    val request = rememberWorkspaceResource("/workspace/markets/calendar")
    val exchanges = request.data?.records("exchanges").orEmpty().filter { it.optionalText("exchange") != null }
    var exchangeId by rememberSaveable { mutableStateOf<String?>(null) }
    var selectedDate by rememberSaveable { mutableStateOf<String?>(null) }
    val exchange = exchanges.firstOrNull { it.optString("exchange") == exchangeId } ?: exchanges.firstOrNull()
    val days = exchange?.records("days").orEmpty().sortedBy { it.optString("date") }
    val day = days.firstOrNull { it.optString("date") == selectedDate } ?: days.firstOrNull()
    Column(verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
        WorkspaceRequestState(request)
        SpectrumCard(emphasized = true) {
            Text("Торговые сессии", style = MaterialTheme.typography.titleLarge)
            Text("Подтверждённое расписание площадок на период, который вернул брокер. Расписание не подтверждает доступность покупки конкретной бумаги.")
            request.data?.optionalText("as_of")?.let { Text("Получено ${dateText(it)}", style = MaterialTheme.typography.bodySmall) }
            if (exchanges.isNotEmpty()) WorkspaceChoices("Площадка", exchanges.map { it.getString("exchange") }, exchanges.indexOf(exchange)) {
                exchangeId = exchanges[it].getString("exchange"); selectedDate = null
            }
            if (days.isNotEmpty()) WorkspaceChoices("Дата расписания", days.map { dateText(it.optString("date"), "dd.MM") }, days.indexOf(day)) {
                selectedDate = days[it].optString("date")
            }
            if (days.isEmpty() && !request.busy) Text("Расписание дней не получено. Отсутствие ответа не означает выходной день.")
        }
        day?.let { TradingDayDetails(it) }
        request.data?.optJSONObject("source")?.let { source -> SourceProvenance(listOf(source), title = "Источник расписания") }
        SpectrumSecondaryButton("Обновить расписание", request.refresh, Modifier.fillMaxWidth(), !request.busy)
    }
}

@Composable
private fun TradingDayDetails(day: JSONObject) {
    val localZone = ZoneId.systemDefault()
    val moscow = ZoneId.of("Europe/Moscow")
    val times = listOf("startTime" to "Начало основной сессии", "endTime" to "Конец основной сессии",
        "openingAuctionStartTime" to "Начало аукциона открытия", "closingAuctionEndTime" to "Конец аукциона закрытия")
    SpectrumCard {
        Text(dateText(day.optString("date"), "dd MMMM yyyy"), style = MaterialTheme.typography.titleLarge)
        Text(when (day.opt("isTradingDay") as? Boolean) {
            true -> "Торговый день по расписанию"; false -> "Торговый день не запланирован"; null -> "Статус торгового дня не получен"
        })
        times.forEach { (field, title) ->
            val raw = day.optionalText(field)
            Text(title, style = MaterialTheme.typography.titleMedium)
            DataRow("Ваше время · ${localZone.id}", tradingLocalTime(raw, localZone))
            DataRow("Москва · Europe/Moscow", tradingLocalTime(raw, moscow))
        }
        DetailFold("Времена, переданные брокером") {
            times.forEach { (field, title) -> DataRow(title, day.optionalText(field) ?: "Не передано") }
            Text("Временные зоны пересчитаны из конкретного момента с учётом календарных правил. Неизвестное время не заменяется обычными часами торгов.", style = MaterialTheme.typography.bodySmall)
        }
    }
}

internal fun tradingLocalTime(raw: String?, zone: ZoneId): String = raw?.let {
    runCatching { DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm z", Locale.forLanguageTag("ru"))
        .format(Instant.parse(it).atZone(zone)) }.getOrNull()
} ?: "Время не получено"
