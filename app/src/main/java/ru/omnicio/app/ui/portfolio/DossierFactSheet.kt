package ru.omnicio.app.ui.portfolio

import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import ru.omnicio.app.data.market.*
import ru.omnicio.app.ui.spatial.SpatialWindow
import ru.omnicio.app.ui.spectrum.SpectrumTabs
import ru.omnicio.app.ui.workspace.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun DossierFactSheet(payload: JSONObject, fact: DossierFact, close: () -> Unit, onNavigate: () -> Unit) {
    var step by rememberSaveable(fact.key) { mutableIntStateOf(0) }
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ModalBottomSheet(onDismissRequest = close, sheetState = sheetState, dragHandle = null) {
        SpatialWindow(Modifier.fillMaxWidth()) {
            Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).semantics { testTagsAsResourceId = true }
                .testTag("workspace-content").navigationBarsPadding().padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
                Text("Контекст факта", style = MaterialTheme.typography.headlineSmall)
                SpectrumTabs(listOf("Факт", "Компания", "Мои позиции"), step, { step = it })
                when (step) {
                    0 -> {
                        DossierFactRecord(payload, fact)
                        if (fact.kind == DossierFactKind.News) DossierEventImpactAction(payload.optionalText("instrument_uid"), fact.row) {
                            close(); onNavigate()
                        }
                        TextButton(onClick = { step = 1 }) { Text("Перейти к компании") }
                    }
                    1 -> {
                        DossierCompanyRecord(payload)
                        TextButton(onClick = { step = 2 }) { Text("Мои позиции в этой бумаге") }
                    }
                    else -> DossierHoldingsPanel(payload, { close(); onNavigate() }, positionLinks = true)
                }
                TextButton(onClick = close, modifier = Modifier.fillMaxWidth()) { Text("Закрыть контекст") }
            }
        }
    }
}

@Composable
private fun DossierFactRecord(payload: JSONObject, fact: DossierFact) {
    val row = fact.row
    Text(row.optionalText("title") ?: row.optionalText("label") ?: "Полученный факт", style = MaterialTheme.typography.titleLarge)
    if (fact.kind == DossierFactKind.News) {
        row.optionalText("summary")?.let { Text(PrivateValue(it)) }
        DossierNewsIdentity(row)
        DossierNewsEvidence(row, dossierSources(payload, "news"))
    } else {
        val value = row.optionalText("value") ?: DOSSIER_UNAVAILABLE
        DataRow("Значение источника", PrivateValue(listOfNotNull(value, row.optionalText("unit"), row.optionalText("currency")).joinToString(" ")))
        row.optionalText("period")?.let { DataRow("Период", it) }
        SourceProvenance(dossierSources(payload, "metrics"), row.stringList("source_ids"))
    }
}

@Composable
private fun DossierCompanyRecord(payload: JSONObject) {
    val instrument = payload.sectionData("instrument")
    Text(instrument?.optionalText("issuer_name") ?: "Эмитент не подтверждён источником", style = MaterialTheme.typography.titleLarge)
    instrument?.optionalText("issuer_id")?.let { DataRow("Идентификатор эмитента", it) }
    Text("Инструмент: ${instrument?.optionalText("title") ?: payload.optString("instrument_uid")}")
    instrument?.optJSONObject("issuer_source")?.let { SourceProvenance(listOf(it)) }
    Text("Связь с бумагой и связь с компанией проверяются отдельно. Заголовок не доказывает влияние на цену.")
}
