package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.key
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import ru.omnicio.app.data.market.optionalText
import ru.omnicio.app.data.market.records
import ru.omnicio.app.data.market.section
import ru.omnicio.app.data.market.stringList
import ru.omnicio.app.ui.spectrum.SpectrumCard
import ru.omnicio.app.ui.workspace.DetailFold
import java.time.Instant

/** Reviewed rating history keeps its own publication, agency, scale and subject. */
@Composable
internal fun DossierRatingsPanel(payload: JSONObject) {
    val section = payload.section("ratings")
    val data = section?.optJSONObject("data")
    SpectrumCard {
        Text("Паспорт рейтинга", style = MaterialTheme.typography.titleLarge)
        WorkspaceSectionNotice(section, "Рейтинг для этой бумаги не подтверждён источником.")
        data?.records("items").orEmpty().forEach { rating -> DossierRatingRecord(rating) }
        data?.stringList("warnings").orEmpty().forEach { Text(it) }
        val history = data?.records("history").orEmpty().sortedBy { rating ->
            rating.optJSONObject("source")?.optionalText("published_at")?.let { runCatching { Instant.parse(it) }.getOrNull() }
                ?: Instant.MAX
        }
        if (history.isNotEmpty()) DetailFold("Как менялся рейтинг") {
            Text("Каждая публикация относится к своему объекту и шкале. Рейтинги выпуска и эмитента не образуют одну общую оценку.",
                style = MaterialTheme.typography.bodySmall)
            history.forEach { row -> key(dossierRecordKey("rating", row)) {
                Column(Modifier.testTag("dossier-rating-history-${row.optJSONObject("source")?.optString("id")}"),
                    verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    DataRow("Дата публикации рейтинга", dateText(row.optJSONObject("source")?.optionalText("published_at")))
                    DossierRatingRecord(row)
                }
            } }
        }
    }
}

private fun ratingSource(rating: JSONObject): JSONObject? = rating.optJSONObject("source")?.let { raw ->
    JSONObject(raw.toString()).apply {
        if (optionalText("provider") == null) put("provider", rating.optionalText("agency"))
        if (optionalText("subject_id") == null) put("subject_id", rating.optionalText("subject_id"))
        if (optionalText("observed_at") == null) put("observed_at", raw.optionalText("checked_at"))
    }
}

@Composable
private fun DossierRatingRecord(rating: JSONObject) {
    Text("${rating.optionalText("agency") ?: "Агентство не указано"} · ${rating.optionalText("grade") ?: "Оценка не получена"}",
        style = MaterialTheme.typography.titleMedium)
    DataRow("Шкала", rating.optionalText("scale") ?: "Не указана")
    DataRow("Объект", when (rating.optionalText("subject_kind")) {
        "issue" -> "Выпуск"; "issuer" -> "Эмитент"; "company" -> "Компания"; else -> "Не подтверждён"
    })
    rating.optionalText("subject_id")?.let { DataRow("Идентификатор объекта", it) }
    DataRow("Статус", rating.optionalText("status") ?: "Не получен")
    DataRow("Прогноз", rating.optionalText("outlook") ?: "Не опубликован")
    ratingSource(rating)?.let { SourceProvenance(listOf(it), title = "Публикация и актуальность рейтинга") }
}
