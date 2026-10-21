package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.workspace.*

internal data class PortfolioRow(val account: PortfolioAccount, val position: PortfolioPosition, val virtual: Boolean = false)

internal fun matchingPosition(position: PortfolioPosition, query: String): Boolean =
    query.isBlank() || listOfNotNull(position.title, position.ticker, position.isin, position.company)
        .any { it.contains(query.trim(), ignoreCase = true) }

/** No conversion, issuer identity inference or simulated risk ranking. */
internal fun sortedPortfolioRows(rows: List<PortfolioRow>, order: Int, currency: String): List<PortfolioRow> {
    val names = compareBy<PortfolioRow> { it.position.title.lowercase(java.util.Locale.ROOT) }
    return when (order) {
        0 -> rows.sortedWith(compareBy<PortfolioRow> { !it.position.blocked }.then(names))
        1, 2 -> rows.sortedWith(compareByDescending<PortfolioRow> {
            it.position.currentValue?.takeIf { amount -> amount.currency == currency }?.value?.toBigDecimal()
        }.then(names))
        else -> rows.sortedWith(names)
    }
}

@Composable
internal fun PortfolioAssetBrowser(snapshot: PortfolioSnapshot, onPosition: (String, PortfolioPosition) -> Unit,
    modifier: Modifier = Modifier, initialQuery: String = "", initialSector: String? = null,
    initialKind: String? = null, selectedAccount: String? = null) {
    var accountId by rememberSaveable(selectedAccount) { mutableStateOf(selectedAccount) }
    var query by rememberSaveable(initialQuery) { mutableStateOf(initialQuery) }
    var kind by rememberSaveable(initialKind) { mutableStateOf(initialKind ?: "all") }
    var sector by rememberSaveable(initialSector) { mutableStateOf(initialSector) }
    var group by rememberSaveable { mutableIntStateOf(0) }
    var order by rememberSaveable { mutableIntStateOf(0) }
    var filtersOpen by rememberSaveable { mutableStateOf(false) }
    var showRestricted by rememberSaveable { mutableStateOf(false) }
    var showCash by rememberSaveable { mutableStateOf(false) }
    val listState = rememberLazyListState()
    val kinds = listOf("all", "bond", "share", "etf", "cash", "other")
    val labels = listOf("Все", "Облигации", "Акции", "Фонды", "Деньги", "Прочие")
    val rows = remember(snapshot, query, kind, sector, order, accountId) {
        portfolioRows(snapshot, query, kind, sector, order, accountId)
    }
    val restricted = rows.filter { it.position.blocked }
    val cash = rows.filter { it.position.instrumentType in setOf("cash", "currency") && !it.position.blocked }
    val assets = rows.filter { !it.position.blocked && it.position.instrumentType !in setOf("cash", "currency") }
    val groups = assets.groupBy { row -> when (group) {
        1 -> row.position.company?.takeIf(String::isNotBlank) ?: "Компания не указана"
        2 -> row.position.sector?.takeIf(String::isNotBlank) ?: "Отрасль не указана"
        else -> row.account.name
    } }
    val changed = accountId != null || query.isNotBlank() || kind != "all" || sector != null || group != 0 || order != 0
    Column(modifier.fillMaxWidth()) {
        OutlinedTextField(query, { query = it }, label = { Text("Название, тикер или ISIN") }, singleLine = true,
            modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 8.dp).testTag("portfolio-search"))
        Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = { filtersOpen = true }) { Text("Фильтры и порядок") }
            Text("${rows.size}", Modifier.weight(1f), style = MaterialTheme.typography.bodySmall)
            if (changed) TextButton(onClick = { query = ""; kind = "all"; sector = null; group = 0; order = 0; accountId = null }) { Text("Сбросить") }
        }
        if (accountId != null || kind != "all" || sector != null || group != 0 || order != 0) Text(
            listOfNotNull(snapshot.accounts.firstOrNull { it.id == accountId }?.name, labels[kinds.indexOf(kind).coerceAtLeast(0)], sector?.let { if (it == "__unknown__") "Отрасль не указана" else it },
                listOf("По счетам", "По названиям компаний", "По отраслям")[group],
                listOf("Сначала ограничения", "По стоимости", "По доле", "По названию")[order]).joinToString(" · "),
            Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.bodySmall)
        LazyColumn(Modifier.weight(1f).fillMaxWidth().testTag("portfolio-content"), state = listState,
            contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
            if (rows.isEmpty()) item { WorkspaceEmpty(if (changed) "Ничего не найдено" else "Активов пока нет",
                if (changed) "Измените запрос или условия поиска." else "Счёт подключён. Полученные позиции появятся здесь.") }
            restrictedRows(restricted, snapshot, showRestricted, { showRestricted = !showRestricted }, onPosition)
            cashRows(cash, snapshot, showCash, { showCash = !showCash }, onPosition)
            if (group == 1) item { Notice("Названия получены от брокера. Проверенные группы связанных эмитентов ещё не подключены.") }
            if (order in 1..2 && rows.any { it.position.currentValue?.currency != snapshot.totalValue.currency }) item {
                Notice("Сначала — оценки в ${snapshot.totalValue.currency}. Несопоставимые валюты и неизвестные значения расположены ниже.")
            }
            assetGroups(groups, group, snapshot, onPosition)
            if (snapshot.accounts.any { it.virtualPositions.isNotEmpty() }) item { DetailFold("Виртуальные позиции") {
                val destination = LocalPortfolioDestination.current
                snapshot.accounts.filter { it.virtualPositions.isNotEmpty() }.forEach { account ->
                    TextButton(onClick = { destination(PortfolioDestination(accountId = account.id, section = 0)) }) { Text("${account.name} · ${account.virtualPositions.size}") }
                }
            } }
        }
    }
    if (filtersOpen) AlertDialog(onDismissRequest = { filtersOpen = false }, title = { Text("Состав портфеля") }, text = {
        LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item { WorkspaceChoices("Счёт", listOf("Все счета") + snapshot.accounts.map { it.name }, snapshot.accounts.indexOfFirst { it.id == accountId } + 1) {
                accountId = snapshot.accounts.getOrNull(it - 1)?.id
            } }
            item { WorkspaceChoices("Класс", labels, kinds.indexOf(kind).coerceAtLeast(0)) { kind = kinds[it] } }
            item { WorkspaceChoices("Группировать", listOf("По счетам", "По компаниям", "По отраслям"), group) { group = it } }
            item { WorkspaceChoices("Порядок", listOf("Сначала ограничения", "По стоимости", "По доле", "По названию"), order) { order = it } }
        }
    }, confirmButton = { TextButton(onClick = { filtersOpen = false }) { Text("Показать") } })
}

internal fun portfolioRows(snapshot: PortfolioSnapshot, query: String, kind: String, sector: String?, order: Int, selectedAccount: String?): List<PortfolioRow> {
    val all = snapshot.accounts.filter { selectedAccount == null || it.id == selectedAccount }.flatMap { account ->
        account.positions.map { PortfolioRow(account, it) }
    }.filter { matchingPosition(it.position, query) && matchingSector(it.position.sector, sector) &&
        matchingKind(it.position.instrumentType, kind) }
    return sortedPortfolioRows(all, order, snapshot.totalValue.currency)
}

private fun LazyListScope.assetGroups(groups: Map<String, List<PortfolioRow>>, group: Int,
    snapshot: PortfolioSnapshot, onPosition: (String, PortfolioPosition) -> Unit) {
            groups.forEach { (label, entries) ->
                item(key = "heading:$label") {
                    SectionHeading(label)
                    if (group == 1) {
                        val values = entries.mapNotNull { it.position.currentValue }
                        values.groupBy { it.currency }.forEach { (currency, amounts) ->
                            DataRow("Стоимость выпусков · $currency", decimalText(amounts.sumOf { it.value.toBigDecimal() }) + " " + currencySymbol(currency))
                        }
                        if (values.size != entries.size) Notice("Часть выпусков без оценки; сумма неполная.")
                    }
                }
                items(entries, key = { "${it.account.id}:${it.position.id}" }) { row ->
                    PositionLine(row.position, total = snapshot.totalValue,
                        accountName = if (group == 0) null else row.account.name) { onPosition(row.account.id, row.position) }
                    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = .3f))
                }
            }
}

private fun LazyListScope.cashRows(cash: List<PortfolioRow>, snapshot: PortfolioSnapshot,
    showCash: Boolean, onToggle: () -> Unit, onPosition: (String, PortfolioPosition) -> Unit) {
            if (cash.isNotEmpty()) {
                item { SpectrumCard {
                    Text("Денежные средства", style = MaterialTheme.typography.titleMedium)
                    cash.mapNotNull { it.position.currentValue }.groupBy { it.currency }.forEach { (currency, values) ->
                        DataRow(currency, decimalText(values.sumOf { it.value.toBigDecimal() }) + " " + currencySymbol(currency))
                    }
                    Text("Это остатки; доступность для покупки и вывода проверяется отдельно.", style = MaterialTheme.typography.bodySmall)
                    TextButton(onClick = onToggle) { Text(if (showCash) "Скрыть остатки по счетам" else "Остатки по счетам") }
                } }
                if (showCash) items(cash, key = { "cash:${it.account.id}:${it.position.id}" }) { row ->
                    PositionLine(row.position, total = snapshot.totalValue, accountName = row.account.name) { onPosition(row.account.id, row.position) }
                }
            }
}

internal fun matchingSector(value: String?, filter: String?): Boolean = when (filter) {
    null -> true
    "__unknown__" -> value.isNullOrBlank()
    else -> value == filter
}
internal fun matchingKind(value: String, filter: String): Boolean = when (filter) {
    "all" -> true
    "cash" -> value in setOf("cash", "currency")
    "other" -> value !in setOf("bond", "share", "etf", "cash", "currency")
    else -> value == filter
}


private fun LazyListScope.restrictedRows(
    restricted: List<PortfolioRow>, snapshot: PortfolioSnapshot, showRestricted: Boolean,
    onToggle: () -> Unit, onPosition: (String, PortfolioPosition) -> Unit,
) {
    if (restricted.isNotEmpty()) {
        item { SpectrumCard {
            Text("Ограниченные активы · ${restricted.size}", style = MaterialTheme.typography.titleMedium)
            Text("Условия сделки уточняются у брокера.", style = MaterialTheme.typography.bodySmall)
            TextButton(onClick = onToggle) { Text(if (showRestricted) "Свернуть" else "Посмотреть ограничения") }
        } }
        if (showRestricted) items(restricted, key = { "restricted:${it.account.id}:${it.position.id}" }) { row ->
            PositionLine(row.position, total = snapshot.totalValue, accountName = row.account.name) { onPosition(row.account.id, row.position) }
        }
    }
}
