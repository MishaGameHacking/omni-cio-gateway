package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import ru.omnicio.app.data.market.optionalText
import ru.omnicio.app.data.market.records
import ru.omnicio.app.data.market.stringList
import ru.omnicio.app.data.portfolio.PortfolioPosition
import ru.omnicio.app.ui.instruments.BrokerInstrumentActions
import ru.omnicio.app.ui.spatial.SpatialWindow
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.workspace.*

/** One reachable control keeps the selected account/UID through every contextual action. */
@Composable
internal fun InstrumentContextActions(position: PortfolioPosition, accountId: String?, onEvents: () -> Unit) {
    val user = LocalWorkspaceSession.current.userId
    val snapshot = LocalPortfolioSnapshot.current
    val rows = snapshot?.accounts.orEmpty().flatMap { account -> account.positions.map { PortfolioRow(account, it) } }
    val origin = rows.singleOrNull { it.account.id == accountId && it.position.id == position.id }
    var panel by rememberSaveable(user, accountId, position.id) { mutableStateOf<String?>(null) }
    var selectedKeys by rememberSaveable(user, accountId, position.id) { mutableStateOf(emptyList<String>()) }
    val selectedRows = selectedKeys.mapNotNull { key -> rows.singleOrNull { portfolioRowKey(it) == key } }
    SpectrumTextButton("Действия с бумагой", { panel = "menu" }, Modifier.fillMaxWidth().testTag("instrument-context-actions"),
        symbol = SpectrumSymbol.Expand)
    when (panel) {
        "menu" -> InstrumentActionSheet(position, { panel = null }) {
            SpectrumTextButton("Сравнить с другими бумагами", {
                selectedKeys = origin?.let { listOf(portfolioRowKey(it)) }.orEmpty(); panel = "choose"
            }, Modifier.fillMaxWidth().testTag("instrument-context-compare"), enabled = origin != null, symbol = SpectrumSymbol.Allocation)
            if (origin == null) Text("Для сравнения откройте актуальную позицию на конкретном счёте.")
            SpectrumTextButton("События и отчётность", { panel = null; onEvents() },
                Modifier.fillMaxWidth().testTag("instrument-context-events"), symbol = SpectrumSymbol.Calendar)
            SpectrumTextButton("Риски этой бумаги", { panel = "risks" },
                Modifier.fillMaxWidth().testTag("instrument-context-risks"), symbol = SpectrumSymbol.Risk)
            BrokerInstrumentActions(position.instrumentType, position.ticker, position.isin, compact = true)
        }
        "choose" -> InstrumentComparisonPicker(position, rows, origin, selectedRows, { row ->
            val id = portfolioRowKey(row)
            selectedKeys = if (id in selectedKeys) selectedKeys - id else selectedKeys + id
        }, { panel = "comparison" }, { panel = "menu" })
        "comparison" -> AssetComparisonDialog(selectedRows, snapshot?.asOf) { panel = "choose" }
        "risks" -> InstrumentActionSheet(position, { panel = "menu" }, back = true) {
            InstrumentRiskContext(position.id, snapshot?.totalValue?.currency ?: "RUB")
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun InstrumentActionSheet(position: PortfolioPosition, close: () -> Unit, back: Boolean = false, content: @Composable ColumnScope.() -> Unit) {
    ModalBottomSheet(onDismissRequest = close, dragHandle = null, containerColor = Color.Transparent, tonalElevation = 0.dp) {
        SpatialWindow(Modifier.fillMaxWidth().heightIn(max = 680.dp)) {
            SpectrumCard(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).semantics { testTagsAsResourceId = true }
                .testTag("workspace-content"), emphasized = true) {
                Text(position.ticker ?: position.title, style = MaterialTheme.typography.titleLarge)
                Text(position.title, style = MaterialTheme.typography.bodyMedium)
                content()
                SpectrumTextButton(if (back) "Назад к действиям" else "Закрыть действия", close, Modifier.fillMaxWidth(),
                    symbol = if (back) SpectrumSymbol.Back else SpectrumSymbol.Close)
            }
        }
    }
}

@Composable
private fun InstrumentComparisonPicker(position: PortfolioPosition, rows: List<PortfolioRow>, origin: PortfolioRow?,
    selected: List<PortfolioRow>, toggle: (PortfolioRow) -> Unit, compare: () -> Unit, close: () -> Unit) {
    val user = LocalWorkspaceSession.current.userId
    var query by rememberSaveable(user, origin?.account?.id, position.id) { mutableStateOf("") }
    val candidates = rows.filter { it.position.id != position.id }.sortedBy(::portfolioRowKey).filter { row ->
        query.isBlank() || listOfNotNull(row.position.title, row.position.ticker, row.account.name, row.position.id)
            .any { it.contains(query.trim(), ignoreCase = true) }
    }
    InstrumentActionSheet(position, close, back = true) {
        Text("Выберите ещё одну или две бумаги", style = MaterialTheme.typography.titleMedium)
        origin?.let { Text("Исходная позиция: ${it.position.ticker ?: it.position.title} · ${it.account.name}") }
        SpectrumTextField(query, { query = it.take(160) }, Modifier.fillMaxWidth(), label = { Text("Название, тикер или счёт") })
        SpectrumPrimaryButton("Сравнить выбранные (${selected.size}/3)", compare, Modifier.fillMaxWidth().testTag("instrument-context-open-comparison"),
            enabled = origin != null && selected.any { portfolioRowKey(it) == portfolioRowKey(origin) } && selected.size in 2..3)
        if (candidates.isEmpty()) Text("Других текущих позиций по этому запросу нет.")
        candidates.forEach { row -> key(portfolioRowKey(row)) {
            val chosen = selected.any { portfolioRowKey(it) == portfolioRowKey(row) }
            val sameInstrumentChosen = selected.any { it.position.id == row.position.id }
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(row.position.ticker ?: row.position.title, style = MaterialTheme.typography.titleMedium)
                Text(row.position.title)
                Text(row.account.name, style = MaterialTheme.typography.bodySmall)
                SpectrumTextButton(if (chosen) "Убрать из сравнения" else "Добавить к сравнению", { toggle(row) },
                    Modifier.fillMaxWidth().testTag("instrument-context-pick-${portfolioRowKey(row)}"),
                    enabled = chosen || (selected.size < 3 && !sameInstrumentChosen), symbol = if (chosen) SpectrumSymbol.Check else SpectrumSymbol.Expand)
            }
        } }
    }
}

@Composable
private fun InstrumentRiskContext(uid: String, currency: String) {
    val resource = rememberWorkspaceResource("/workspace/risks?currency=$currency")
    Text("Риски этой бумаги", style = MaterialTheme.typography.titleLarge)
    Text("Связанные концентрации и события по всем вашим счетам. Доля группы относится ко всей группе, содержащей эту бумагу.")
    WorkspaceRequestState(resource)
    resource.data?.let { payload ->
        DataRow("Снимок для расчёта", dateText(payload.optionalText("as_of")))
        DataRow("Версия правил", payload.opt("strategy_version")?.takeIf { it is Number || it is String }?.toString() ?: "Не получена")
        val concentrations = payload.records("concentrations").filter { uid in it.stringList("instrument_uids") }
        if (concentrations.isEmpty()) Text("В полученном снимке нет рассчитанных концентраций, связанных с этой бумагой. Это не подтверждение отсутствия риска.")
        val sources = LocalWorkspaceSnapshot.current?.records("sources").orEmpty()
        concentrations.forEach { concentration -> InstrumentConcentration(concentration, sources) }
        val missing = payload.records("coverage").filter { uid in it.stringList("missing_instrument_uids") }
        if (missing.isNotEmpty()) DetailFold("Каких сведений об этой бумаге не хватает", initiallyOpen = true) {
            missing.forEach { axis -> Text(riskDirection(axis.optString("direction"))) }
            Text("Неизвестные сведения не считаются безопасными; полнота источников не является вероятностью потери.")
        }
        val events = payload.records("events").filter { uid in it.stringList("instrument_uids") }
        DetailFold("Изменения риска этой бумаги") {
            if (events.isEmpty()) Text("В последних 100 полученных событиях риска нет записей с этим UID.")
            events.forEach { event ->
                Text(event.optionalText("title") ?: "Изменение риска", style = MaterialTheme.typography.titleMedium)
                Text(dateText(event.optionalText("occurred_at") ?: event.optionalText("created_at")))
                if (event.optString("kind").endsWith("data_stale")) Text("Недостаточно свежих подтверждённых сведений. Риск не считается устранённым.")
                SourceProvenance((event.records("sources") + sources).distinctBy { it.optionalText("id") ?: it.toString() }, event.stringList("source_ids"))
            }
        }
    }
}

@Composable
private fun InstrumentConcentration(row: JSONObject, sources: List<JSONObject>) {
    Column(Modifier.testTag("instrument-risk-${row.optString("direction")}-${row.optString("id")}"),
        verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(row.optionalText("label") ?: "Концентрация", style = MaterialTheme.typography.titleMedium)
        Text(riskDirection(row.optString("direction")), style = MaterialTheme.typography.bodySmall)
        DataRow("Оценка", workspaceMoney(row.optJSONObject("value")))
        DataRow("Доля", PrivateValue(row.optionalText("share_percent")?.let { "$it%" } ?: "Не получена"))
        DataRow("Лимит", row.optionalText("limit_percent")?.let { "$it%" } ?: "Не задан")
        Text(when {
            row.isNull("breached") || !row.has("breached") -> "Сопоставление с лимитом не подтверждено"
            row.optBoolean("breached") -> "Лимит превышен"
            else -> "В пределах заданного лимита"
        })
        SourceProvenance(sources, row.stringList("source_ids"))
    }
}
