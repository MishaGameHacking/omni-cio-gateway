package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import ru.omnicio.app.data.market.*
import ru.omnicio.app.data.market.records
import ru.omnicio.app.ui.portfolio.DataRow
import ru.omnicio.app.ui.portfolio.SourceProvenance
import ru.omnicio.app.ui.portfolio.WorkspaceSectionNotice
import ru.omnicio.app.ui.portfolio.workspaceMoney
import ru.omnicio.app.ui.spatial.SpatialGeoPoint
import ru.omnicio.app.ui.spatial.SpatialGeography
import ru.omnicio.app.ui.spectrum.*

/** The only financial geographic axis here is the broker's country of main risk. */
@Composable
internal fun GeographyWorkspacePanel(currency: String) {
    val request = rememberWorkspaceResource("/workspace?currency=$currency")
    val fallback = LocalWorkspaceSnapshot.current?.takeIf { it.optString("currency") == currency }
    val payload = request.data ?: fallback
    val exposure = payload?.section("exposures")
    val axis = payload?.sectionData("exposures")?.records("axes").orEmpty().singleOrNull { it.optString("id") == "country" }
    val countries = axis?.records("items").orEmpty().filter { it.optionalText("id") != null }.distinctBy { it.getString("id") }
    val sources = payload?.records("sources").orEmpty()
    var selectedId by rememberSaveable(currency) { mutableStateOf<String?>(null) }
    val points = countries.mapNotNull { row -> countryAnchor(row.getString("id"))?.let {
        SpatialGeoPoint(row.getString("id"), it.latitude, it.longitude)
    } }
    Column(verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
        WorkspaceRequestState(request)
        SpectrumCard(emphasized = true) {
            Text("География портфеля", style = MaterialTheme.typography.titleLarge)
            SpectrumBadge("Ось: страна основного риска")
            Text("Связь инструмента со страной передана справочником брокера. Она не обозначает биржу, гражданство владельца или место регистрации компании.")
            WorkspaceSectionNotice(exposure, "Географические связи пока не подтверждены.")
            if (axis?.has("unknown_count") == true) Text("Без подтверждённой страны: ${axis.optInt("unknown_count")}")
            if (axis != null && !axis.optBoolean("complete")) Text("Распределение неполное. Неизвестные связи не добавляются к какой-либо стране.")
            SpatialGeography(points, points.indexOfFirst { it.id == selectedId }.takeIf { it >= 0 },
                Modifier.fillMaxWidth().height(240.dp).semantics {
                    contentDescription = "Глобус стран основного риска. Выберите страну в доступном списке ниже. Подтверждённых географических меток: ${points.size}."
                })
            Text("Выбор страны в списке поворачивает глобус к её ориентиру. Метки одинакового размера: они не кодируют размер вложений.", style = MaterialTheme.typography.bodySmall)
            Text("Север остаётся сверху. Географический ориентир страны не является адресом эмитента.", style = MaterialTheme.typography.bodySmall)
        }
        if (countries.isEmpty()) WorkspaceEmpty("Страны пока не получены", "Когда брокер передаст страну риска инструмента, она появится здесь вместе с источником и составом позиций.")
        countries.forEach { country -> key(country.getString("id")) {
            val id = country.getString("id")
            GeographyCountryCard(country, sources, id == selectedId) { selectedId = if (id == selectedId) null else id }
        } }
        DetailFold("Справочник географических ориентиров") {
            Text("Координаты взяты из открытого справочника Google DSPL и встроены в приложение. Финансовые связи и названия стран поступают отдельно от брокера.")
            EvidenceLinks(listOf(JSONObject().put("id", COUNTRY_ANCHOR_SOURCE_ID).put("provider", "Google DSPL · географические ориентиры")
                .put("method", "countries.csv · Git blob 82486418c18a27f238ea09acf03f76fb5b235919")
                .put("unit", "географические градусы").put("url", COUNTRY_ANCHOR_SOURCE)))
        }
    }
}

@Composable
private fun GeographyCountryCard(country: JSONObject, sources: List<JSONObject>, selected: Boolean, onSelect: () -> Unit) {
    val id = country.getString("id")
    val destination = LocalPortfolioDestination.current
    val navigate = LocalEvidenceNavigator.current
    val accounts = LocalPortfolioSnapshot.current?.accounts.orEmpty()
    SpectrumCard(Modifier.fillMaxWidth().semantics { this.selected = selected }, emphasized = selected, onClick = onSelect) {
        Text("${country.optionalText("label") ?: id} · $id", style = MaterialTheme.typography.titleMedium)
        DataRow("Подтверждённая оценка", workspaceMoney(country.optJSONObject("value")))
        DataRow("Доля капитала", PrivateValue(country.optionalText("share_percent")?.let { "$it%" } ?: "Не получена"))
        if (countryAnchor(id) == null) Text("Для этого кода нет координат в справочнике. Строка сохраняется без выдуманной метки на глобусе.")
        Text(if (selected) "Выбрано · состав позиций" else "Выбрать и показать позиции", style = MaterialTheme.typography.bodySmall)
        if (selected) {
            val uids = country.stringList("instrument_uids")
            uids.forEach { uid ->
                val held = accounts.flatMap { account -> account.positions.filter { it.id == uid }.map { account to it } }
                if (held.isEmpty()) SpectrumSecondaryButton("Открыть сведения · ${uid.take(12)}", { navigate(EvidenceTarget("instrument", uid)) }, Modifier.fillMaxWidth())
                else held.forEach { (account, position) -> SpectrumSecondaryButton("${position.title} · ${account.name}", {
                    destination(PortfolioDestination(accountId = account.id, query = uid))
                }, Modifier.fillMaxWidth()) }
            }
            if (uids.isEmpty()) Text("Состав этой группы не передан источником.")
            SourceProvenance(sources, country.stringList("source_ids"), "Основания страны риска")
        }
    }
}
