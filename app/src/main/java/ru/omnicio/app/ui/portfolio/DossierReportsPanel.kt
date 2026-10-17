package ru.omnicio.app.ui.portfolio

import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton

import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import ru.omnicio.app.data.market.*
import ru.omnicio.app.ui.spectrum.SpectrumCard
import ru.omnicio.app.ui.spectrum.SpectrumTabs
import ru.omnicio.app.ui.workspace.DetailFold
import java.time.Instant
import java.time.LocalDate
import java.time.YearMonth
import java.time.format.DateTimeFormatter

internal enum class ReportPublicationState { Scheduled, Published, Unconfirmed }

/** A calendar date, including a past date, cannot prove publication. */
internal fun reportPublicationState(status: String?, confirmed: Boolean?, hasPublicationSource: Boolean): ReportPublicationState = when {
    status == "scheduled" -> ReportPublicationState.Scheduled
    status == "published" && confirmed != false && hasPublicationSource -> ReportPublicationState.Published
    else -> ReportPublicationState.Unconfirmed
}

internal fun reportCalendarDate(raw: String?): LocalDate? = raw?.let { value ->
    runCatching { Instant.parse(value).atZone(Moscow).toLocalDate() }.getOrNull()
        ?: runCatching { LocalDate.parse(value) }.getOrNull()
}

private fun publicationState(report: JSONObject, sources: List<JSONObject>): ReportPublicationState {
    val relevant = report.stringList("source_ids").toSet()
    val source = report.optJSONObject("source")
    val publishedSource = source?.optionalText("published_at") != null ||
        sources.any { it.optString("id") in relevant && it.optionalText("published_at") != null }
    return reportPublicationState(report.optionalText("status"), report.opt("publication_confirmed") as? Boolean, publishedSource)
}

@Composable
internal fun DossierReportsPanel(payload: JSONObject) {
    val section = payload.section("reports")
    val reports = payload.sectionData("reports")?.records("items").orEmpty()
    val sources = dossierSources(payload, "reports")
    var monthText by rememberSaveable(payload.optionalText("instrument_uid")) { mutableStateOf<String?>(null) }
    var filter by rememberSaveable(payload.optionalText("instrument_uid")) { mutableIntStateOf(0) }
    val month = monthText?.let { runCatching { YearMonth.parse(it) }.getOrNull() }
    val visible = reports.filter { report ->
        val date = reportCalendarDate(report.optionalText("date"))
        val inMonth = month == null || date?.let { YearMonth.from(it) == month } == true
        val state = publicationState(report, sources)
        inMonth && when (filter) {
            1 -> state == ReportPublicationState.Scheduled
            2 -> state == ReportPublicationState.Published
            else -> true
        }
    }.sortedBy { reportCalendarDate(it.optionalText("date")) ?: LocalDate.MAX }
    SpectrumCard {
        Text("Календарь отчётности", style = MaterialTheme.typography.titleLarge)
        WorkspaceSectionNotice(section, "Проверенные даты отчётов не получены.")
        Text("Объявленные даты и опубликованные документы показаны раздельно. Наступление даты не подтверждает выход отчёта.",
            style = MaterialTheme.typography.bodySmall)
        SpectrumTabs(listOf("Все", "Объявлены", "Опубликованы"), filter, { filter = it })
        ReportMonthControls(month) { monthText = it?.toString() }
        if (visible.isEmpty()) Text("Для выбранного месяца и статуса подтверждённых записей не получено.")
        visible.forEach { report -> key(dossierRecordKey("report", report)) {
            ReportCalendarEntry(report, publicationState(report, sources), sources)
        } }
        val undated = reports.count { reportCalendarDate(it.optionalText("date")) == null }
        if (undated > 0) Text("Без подтверждённой даты: $undated. Эти записи доступны в режиме «Все даты».", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun ReportMonthControls(month: YearMonth?, select: (YearMonth?) -> Unit) {
    val current = month ?: YearMonth.now(Moscow)
    Text(month?.format(DateTimeFormatter.ofPattern("LLLL yyyy", Russian)) ?: "Все даты", style = MaterialTheme.typography.titleMedium)
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        TextButton(onClick = { select(current.minusMonths(1)) }) { Text("Предыдущий месяц") }
        TextButton(onClick = { select(YearMonth.now(Moscow)) }) { Text("Текущий месяц") }
        TextButton(onClick = { select(current.plusMonths(1)) }) { Text("Следующий месяц") }
        if (month != null) TextButton(onClick = { select(null) }) { Text("Все даты") }
    }
}

@Composable
private fun ReportCalendarEntry(report: JSONObject, state: ReportPublicationState, sources: List<JSONObject>) {
    val date = reportCalendarDate(report.optionalText("date"))
    Column(Modifier.fillMaxWidth().testTag("dossier-report-${report.optString("id")}"),
        verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(report.optionalText("title") ?: "Отчёт", style = MaterialTheme.typography.titleMedium)
        Text(date?.format(DateTimeFormatter.ofPattern("dd.MM.yyyy")) ?: "Дата не подтверждена")
        Text(when (state) {
            ReportPublicationState.Published -> "Опубликован: есть проверенный источник документа"
            ReportPublicationState.Scheduled -> "Дата объявлена источником"
            ReportPublicationState.Unconfirmed -> "Публикация не подтверждена"
        })
        if (state == ReportPublicationState.Scheduled && date?.isBefore(LocalDate.now(Moscow)) == true)
            Text("Объявленная дата прошла; подтверждение публикации ещё не получено.", style = MaterialTheme.typography.bodySmall)
        ReportPeriod(report)
        report.optionalText("record_created_at")?.let { Text("Запись календаря создана: ${dateText(it)}", style = MaterialTheme.typography.bodySmall) }
        val ownSource = report.optJSONObject("source")
        if (ownSource != null) SourceProvenance(listOf(ownSource), title = "Проверенная публикация документа")
        else SourceProvenance(sources, report.stringList("source_ids"), "Источник объявленной даты")
    }
}

@Composable
private fun ReportPeriod(report: JSONObject) {
    val begin = report.optionalText("period_start")
    val end = report.optionalText("period_end")
    if (begin != null || end != null) DataRow("Период отчёта", "${begin ?: "Начало не указано"} — ${end ?: "Конец не указан"}")
    val year = report.opt("period_year")?.takeUnless { it == JSONObject.NULL }?.toString()
    val number = report.opt("period_num")?.takeUnless { it == JSONObject.NULL }?.toString()
    val type = report.optionalText("period_type")
    if (year != null) DataRow("Год отчётности", year)
    if (number != null) DataRow("Период по календарю источника", number)
    if (type != null) DetailFold("Тип периода у источника") { Text(type) }
}
