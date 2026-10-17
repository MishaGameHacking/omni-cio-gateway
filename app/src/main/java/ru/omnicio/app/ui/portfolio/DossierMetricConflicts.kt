package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import ru.omnicio.app.data.market.optionalText
import ru.omnicio.app.data.market.records
import ru.omnicio.app.data.market.stringList
import ru.omnicio.app.ui.workspace.DetailFold
import ru.omnicio.app.ui.workspace.PrivateValue

@Composable
internal fun DossierMetricConflicts(conflicts: List<JSONObject>, sources: List<JSONObject>) {
    if (conflicts.isEmpty()) return
    DetailFold("Расхождения источников (${conflicts.size})", initiallyOpen = true) {
        conflicts.forEach { conflict ->
            Text(conflict.optionalText("label") ?: conflict.optionalText("metric") ?: "Источники расходятся",
                style = MaterialTheme.typography.titleMedium)
            conflict.records("observations").forEachIndexed { index, observation ->
                ConflictObservation(observation, index)
            }
            conflict.optionalText("reason")?.let { reason -> Text(when (reason) {
                "same_basis_different_values" -> "За один период в одной валюте источник передал разные значения."
                "different_period_or_currency" -> "Наблюдения относятся к разным периодам или валютам."
                else -> reason
            }) }
            Text("Расхождение не разрешено автоматически. Сверьте период, единицы и публикации.", style = MaterialTheme.typography.bodySmall)
            SourceProvenance(sources, conflict.stringList("source_ids"))
        }
    }
}

@Composable
private fun ConflictObservation(observation: JSONObject, index: Int) {
    Column(Modifier.testTag("dossier-conflict-observation-$index"), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("Наблюдение ${index + 1}", style = MaterialTheme.typography.titleSmall)
        DataRow("Источник наблюдения", observation.optionalText("source_id") ?: "Не указан")
        DataRow("Период наблюдения", observation.optionalText("period") ?: "Не получен")
        DataRow("Валюта наблюдения", observation.optionalText("currency") ?: "Не указана")
        val metrics = observation.records("metrics")
        metrics.forEach { metric -> ConflictMetric(metric, observation) }
        val values = observation.optJSONObject("value")
        if (values != null) {
            val additional = additionalConflictFields(values.keys().asSequence().associateWith { values.opt(it) },
                metrics.mapNotNull { it.optionalText("id") }.toSet())
            if (additional.isNotEmpty()) {
                Text("Дополнительные поля источника", style = MaterialTheme.typography.titleSmall)
                Text("Единицы этих полей не подтверждены источником. Валюта наблюдения не применяется к ним автоматически.",
                    style = MaterialTheme.typography.bodySmall)
                additional.forEach { (name, value) -> DataRow(name, PrivateValue(value ?: DOSSIER_UNAVAILABLE)) }
            }
        } else if (metrics.isEmpty()) DataRow("Значение", PrivateValue(sourceScalar(observation.opt("value")) ?: DOSSIER_UNAVAILABLE))
    }
}

/** Preserve extra source values even when every named metric agrees between observations. */
internal fun additionalConflictFields(values: Map<String, Any?>, metricIds: Set<String>): Map<String, String?> =
    values.filterKeys { it !in metricIds && it !in setOf("currency", "fiscalPeriodEndDate", "period", "assetUid") }
        .toSortedMap().mapValues { sourceScalar(it.value) }

private fun sourceScalar(value: Any?): String? = when (value) {
    is String -> value.takeIf(String::isNotBlank)
    is Number, is Boolean -> value.toString()
    else -> null
}

@Composable
private fun ConflictMetric(metric: JSONObject, observation: JSONObject) {
    val value = sourceScalar(metric.opt("value")) ?: DOSSIER_UNAVAILABLE
    DataRow(metric.optionalText("label") ?: metric.optionalText("id") ?: "Показатель", PrivateValue(value))
    val unit = metric.optionalText("unit")
    DataRow("Единица показателя", when (unit) {
        "currency" -> "Денежная величина"; null -> "Не указана"; else -> unit
    })
    metric.optionalText("currency")?.let { DataRow("Валюта показателя", it) }
    metric.optionalText("period")?.takeIf { it != observation.optionalText("period") }?.let { DataRow("Период показателя", it) }
    if (metric.optionalText("missing_reason") == "broker_zero_means_unavailable")
        Text("Источник обозначает нулём отсутствие данных. Числовая оценка не подставляется.", style = MaterialTheme.typography.bodySmall)
}
