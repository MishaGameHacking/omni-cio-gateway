package ru.omnicio.app.ui.portfolio

import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton

import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import org.json.JSONObject
import ru.omnicio.app.data.market.*
import ru.omnicio.app.data.market.records
import ru.omnicio.app.data.portfolio.PortfolioPosition
import ru.omnicio.app.ui.spectrum.SpectrumCard
import ru.omnicio.app.ui.workspace.*
import java.security.MessageDigest

internal const val DOSSIER_UNAVAILABLE = "Не получено"

@Composable
internal fun InstrumentDossierPanel(position: PortfolioPosition, onNavigate: () -> Unit = {}) {
    val request = rememberWorkspaceRequest("/workspace/instruments/${position.id}/dossier")
    WorkspaceRequestNotice(request)
    request.json?.let { payload ->
        if (payload.optString("instrument_uid") != position.id) {
            Text("Идентификатор ответа не совпал с выбранной бумагой. Сведения не показаны.")
        } else {
            SaveResearchButton(payload, "Досье ${position.ticker ?: position.title}", position.id,
                source = "T‑Invest и проверенные источники компании", observedAt = payload.optionalText("as_of"))
            InstrumentDossierContent(payload, onNavigate)
        }
    }
}

internal fun dossierSources(payload: JSONObject, section: String? = null): List<JSONObject> =
    (payload.records("sources") + section?.let { payload.section(it)?.records("sources") }.orEmpty())
        .distinctBy { it.optionalText("id") ?: it.toString() }

/** Only the identity is saved in UI state; refreshed facts are resolved from the current payload. */
internal fun dossierRecordKey(kind: String, row: JSONObject): String {
    val identity = row.optionalText("id") ?: MessageDigest.getInstance("SHA-256")
        .digest(row.toString().toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
    return "$kind:$identity"
}

internal enum class DossierFactKind { Metric, News }
internal data class DossierFact(val key: String, val kind: DossierFactKind, val row: JSONObject)

private fun dossierFacts(payload: JSONObject): List<DossierFact> =
    payload.sectionData("metrics")?.records("items").orEmpty().map { DossierFact(dossierRecordKey("metric", it), DossierFactKind.Metric, it) } +
        payload.sectionData("news")?.records("items").orEmpty().map { DossierFact(dossierRecordKey("news", it), DossierFactKind.News, it) }

@Composable
internal fun InstrumentDossierContent(payload: JSONObject, onNavigate: () -> Unit = {}) {
    var selectedFactKey by rememberSaveable(payload.optionalText("instrument_uid")) { mutableStateOf<String?>(null) }
    val selectedFact = dossierFacts(payload).firstOrNull { it.key == selectedFactKey }
    val select: (String) -> Unit = { selectedFactKey = it }
    Column(verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
        DossierHeader(payload)
        DossierHoldingsPanel(payload, onNavigate)
        DossierRatingsPanel(payload)
        DossierMetricsPanel(payload, select)
        DossierReportsPanel(payload)
        DossierNewsPanel(payload, select)
    }
    if (selectedFact != null) DossierFactSheet(payload, selectedFact, { selectedFactKey = null }, onNavigate)
    else if (selectedFactKey != null) WorkspaceDialog("Факт изменился", { selectedFactKey = null }) {
        Text("Выбранная запись отсутствует в текущем ответе источника. Другой факт не подставляется.")
        TextButton(onClick = { selectedFactKey = null }) { Text("Вернуться к досье") }
    }
}

@Composable
private fun DossierHeader(payload: JSONObject) {
    val instrument = payload.sectionData("instrument")
    SpectrumCard {
        Text(instrument?.optionalText("title") ?: "Досье инструмента", style = MaterialTheme.typography.titleLarge)
        Text(listOfNotNull(instrument?.optionalText("ticker"), instrument?.optionalText("isin")).joinToString(" · "))
        Text("Обновлено ${dateText(payload.optionalText("as_of"))}", style = MaterialTheme.typography.bodySmall)
        SourceProvenance(dossierSources(payload, "instrument"))
    }
}

@Composable
internal fun DossierHoldingsPanel(payload: JSONObject, onNavigate: () -> Unit, positionLinks: Boolean = false) {
    val destination = LocalPortfolioDestination.current
    val holdings = payload.sectionData("holdings")?.records("items").orEmpty()
    SpectrumCard {
        Text("Эта бумага на всех счетах", style = MaterialTheme.typography.titleLarge)
        WorkspaceSectionNotice(payload.section("holdings"))
        if (holdings.isEmpty()) Text("В полученном снимке этой бумаги на ваших счетах нет.")
        holdings.forEach { holding ->
            Text(holding.optionalText("account_name") ?: "Счёт", style = MaterialTheme.typography.titleMedium)
            DataRow("Количество", PrivateValue(holding.optionalText("quantity") ?: DOSSIER_UNAVAILABLE))
            DataRow("Стоимость", workspaceMoney(holding.optJSONObject("value")))
            if (holding.optBoolean("blocked")) Text("Есть ограничения")
            val accountId = holding.optionalText("account_id")
            TextButton(onClick = {
                onNavigate()
                destination(PortfolioDestination(accountId = accountId, section = if (positionLinks) 1 else 0,
                    query = if (positionLinks) payload.optString("instrument_uid") else ""))
            }, enabled = accountId != null) { Text(if (positionLinks) "Открыть текущую позицию" else "Открыть счёт") }
        }
    }
}

@Composable
private fun DossierRatingsPanel(payload: JSONObject) {
    val section = payload.section("ratings")
    val data = section?.optJSONObject("data")
    SpectrumCard {
        Text("Паспорт рейтинга", style = MaterialTheme.typography.titleLarge)
        WorkspaceSectionNotice(section, "Рейтинг для этой бумаги не подтверждён источником.")
        data?.records("items").orEmpty().forEach { rating -> DossierRatingRecord(rating) }
        data?.stringList("warnings").orEmpty().forEach { Text(it) }
        val history = data?.records("history").orEmpty()
        if (history.isNotEmpty()) DetailFold("Как менялся рейтинг") { history.forEach { row ->
            DataRow(dateText(row.optionalText("published_at") ?: row.optionalText("date")),
                "${row.optionalText("agency") ?: ""} · ${row.optionalText("grade") ?: DOSSIER_UNAVAILABLE}")
        } }
    }
}

@Composable
private fun DossierRatingRecord(rating: JSONObject) {
    Text("${rating.optionalText("agency") ?: "Агентство не указано"} · ${rating.optionalText("grade") ?: "Оценка не получена"}",
        style = MaterialTheme.typography.titleMedium)
    DataRow("Шкала", rating.optionalText("scale") ?: "Не указана")
    DataRow("Объект", when (rating.optionalText("subject_kind")) {
        "issue" -> "Выпуск"; "issuer", "company" -> "Компания"; else -> "Не подтверждён"
    })
    rating.optionalText("subject_id")?.let { DataRow("Идентификатор объекта", it) }
    DataRow("Статус", rating.optionalText("status") ?: "Не получен")
    DataRow("Прогноз", rating.optionalText("outlook") ?: "Не опубликован")
    rating.optJSONObject("source")?.let { SourceProvenance(listOf(it), title = "Публикация и актуальность рейтинга") }
}

@Composable
private fun DossierMetricsPanel(payload: JSONObject, select: (String) -> Unit) {
    val metrics = payload.sectionData("metrics")
    val sources = dossierSources(payload, "metrics")
    SpectrumCard {
        Text("Показатели компании", style = MaterialTheme.typography.titleLarge)
        WorkspaceSectionNotice(payload.section("metrics"))
        metrics?.records("items").orEmpty().forEach { metric ->
            val raw = metric.optionalText("value")
            val value = raw?.toBigDecimalOrNull()?.let { decimalText(it, 4) } ?: raw ?: DOSSIER_UNAVAILABLE
            DataRow(metric.optionalText("label") ?: "Показатель",
                PrivateValue(listOfNotNull(value, metric.optionalText("unit"), metric.optionalText("currency")).joinToString(" ")))
            metric.optionalText("period")?.let { Text("Период: $it", style = MaterialTheme.typography.bodySmall) }
            if (metric.optionalText("missing_reason") == "broker_zero_means_unavailable")
                Text("Источник обозначает нулём отсутствие данных. Числовая оценка не подставляется.", style = MaterialTheme.typography.bodySmall)
            SourceProvenance(sources, metric.stringList("source_ids"), "Откуда получено значение")
            TextButton(onClick = { select(dossierRecordKey("metric", metric)) }) { Text("Факт → компания → моя позиция") }
        }
        DossierMetricConflicts(metrics?.records("conflicts").orEmpty(), sources)
    }
}

@Composable
private fun DossierMetricConflicts(conflicts: List<JSONObject>, sources: List<JSONObject>) {
    if (conflicts.isEmpty()) return
    DetailFold("Расхождения источников (${conflicts.size})", initiallyOpen = true) {
        conflicts.forEach { conflict ->
            Text(conflict.optionalText("label") ?: conflict.optionalText("metric") ?: "Источники расходятся",
                style = MaterialTheme.typography.titleMedium)
            conflict.records("observations").forEach { observation ->
                DataRow(observation.optionalText("source_id") ?: "Источник", PrivateValue(observation.optionalText("value") ?: DOSSIER_UNAVAILABLE))
                observation.optionalText("period")?.let { Text(it) }
            }
            conflict.optionalText("reason")?.let { Text(it) }
            Text("Расхождение не разрешено автоматически. Сверьте период, единицы и публикации.", style = MaterialTheme.typography.bodySmall)
            SourceProvenance(sources, conflict.stringList("source_ids"))
        }
    }
}
