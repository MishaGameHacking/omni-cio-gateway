package ru.omnicio.app.ui.portfolio

import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import ru.omnicio.app.data.market.*
import ru.omnicio.app.data.market.records
import ru.omnicio.app.ui.spectrum.SpectrumCard
import ru.omnicio.app.ui.workspace.*

internal fun exposureMembership(axis: JSONObject?, uid: String): List<JSONObject> = axis?.records("items").orEmpty()
    .filter { uid in it.stringList("instrument_uids") }

@Composable
internal fun VerifiedExposurePanel(request: WorkspaceRequest, axis: JSONObject?, selectedId: String?, onSelect: (String?) -> Unit) {
    SpectrumCard(Modifier.padding(horizontal = 20.dp)) {
        Text(axis?.optionalText("label") ?: "Проверенные связи эмитентов", style = MaterialTheme.typography.titleMedium)
        WorkspaceRequestNotice(request)
        WorkspaceSectionNotice(request.json?.section("exposures"))
        if (axis == null) Text("Подтверждённые связи для этого разреза не получены. Название компании не используется как идентификатор группы.")
        else {
            val entries = axis.records("items")
            if (!axis.optBoolean("complete")) Text("Разрез неполный. Инструментов без подтверждённой связи: ${axis.optInt("unknown_count") }.")
            val positive = entries.all { it.optionalText("share_percent")?.toBigDecimalOrNull()?.signum()?.let { sign -> sign >= 0 } == true }
            val sum = entries.sumOf { it.optionalText("share_percent")?.toDoubleOrNull() ?: 0.0 }
            if (positive && sum > 0.0 && sum <= 100.1 && !request.showingPreviousQuery) {
                val slices = entries.map { ChartSlice(it.optionalText("label") ?: "Название не получено", it.optString("share_percent").toFloatOrNull() ?: 0f, it.optString("id")) } +
                    if (sum < 99.9) listOf(ChartSlice("Не распределено источником", (100.0 - sum).toFloat(), "__unmapped__")) else emptyList()
                StructureChart(slices, PrivateValue("${entries.size} групп"), "Подтверждённые группы") {
                    if (it != "__unmapped__") onSelect(if (selectedId == it) null else it)
                }
            }
            entries.forEach { entry ->
                TextButton(onClick = { onSelect(if (selectedId == entry.optString("id")) null else entry.optString("id")) }, modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.fillMaxWidth()) {
                        Text((if (selectedId == entry.optString("id")) "Выбрано · " else "") + (entry.optionalText("label") ?: "Название не получено"))
                        Text("${PrivateValue(entry.optionalText("share_percent")?.let { "$it%" } ?: "Доля не получена")} · ${workspaceMoney(entry.optJSONObject("value"))}", style = MaterialTheme.typography.bodySmall)
                    }
                }
                if (selectedId == entry.optString("id")) SourceProvenance(request.json?.records("sources").orEmpty(), entry.stringList("source_ids"))
            }
            if (selectedId != null) TextButton(onClick = { onSelect(null) }) { Text("Показать все группы") }
        }
    }
}
