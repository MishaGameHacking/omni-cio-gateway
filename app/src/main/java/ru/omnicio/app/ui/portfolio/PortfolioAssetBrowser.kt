package ru.omnicio.app.ui.portfolio

import ru.omnicio.app.ui.spectrum.SpectrumAlertDialog as AlertDialog
import ru.omnicio.app.ui.spectrum.SpectrumChoiceChip as FilterChip

import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton

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
import ru.omnicio.app.data.market.*
import ru.omnicio.app.data.market.records
import ru.omnicio.app.data.workspace.*
import java.util.UUID
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.workspace.*

internal data class PortfolioRow(val account: PortfolioAccount, val position: PortfolioPosition, val virtual: Boolean = false)

internal fun matchingPosition(position: PortfolioPosition, query: String): Boolean =
    query.isBlank() || listOfNotNull(position.id, position.title, position.ticker, position.isin, position.company)
        .any { it.contains(query.trim(), ignoreCase = true) }

/** No conversion, issuer identity inference or simulated risk ranking. */
internal fun sortedPortfolioRows(rows: List<PortfolioRow>, order: Int, currency: String): List<PortfolioRow> {
    val names = compareBy<PortfolioRow> { it.position.title.lowercase(java.util.Locale.ROOT) }
        .thenBy { it.account.id }.thenBy { it.position.id }
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
    val personal = rememberPersonalWorkspace()
    var onlyWatched by rememberSaveable { mutableStateOf(false) }
    var exposureId by rememberSaveable { mutableStateOf<String?>(null) }
    val exposureRequest = rememberWorkspaceRequest(parameters = mapOf("currency" to snapshot.totalValue.currency), refreshKey = LocalWorkspaceRefreshKey.current)
    val exposureAxis = exposureRequest.json?.sectionData("exposures")?.records("axes")?.firstOrNull {
        it.optString("id") == if (group == 3) "issuer" else if (group == 4) "group" else ""
    }
    var selecting by rememberSaveable { mutableStateOf(false) }
    var selectedKeys by rememberSaveable { mutableStateOf(arrayListOf<String>()) }
    var comparing by rememberSaveable { mutableStateOf(false) }
    var saveFilter by rememberSaveable { mutableStateOf(false) }
    var filterTitle by rememberSaveable { mutableStateOf("") }
    var batchReason by rememberSaveable { mutableStateOf<String?>(null) }
    val allCurrent = snapshot.accounts.flatMap { account -> account.positions.map { PortfolioRow(account, it) } }
    val chosen = allCurrent.filter { portfolioRowKey(it) in selectedKeys }
    val open: (String, PortfolioPosition) -> Unit = { id, position ->
        if (!selecting) onPosition(id, position)
        else {
            val key = "$id:${position.id}"
            selectedKeys = ArrayList(if (key in selectedKeys) selectedKeys.filter { it != key }
                else (selectedKeys + key).take(20))
        }
    }
    val listState = rememberLazyListState()
    val kinds = listOf("all", "bond", "share", "etf", "cash", "futures", "option", "other")
    val labels = listOf("Все", "Облигации", "Акции", "Фонды", "Деньги", "Фьючерсы", "Опционы", "Прочие")
    val candidates = remember(snapshot, query, kind, sector, order, accountId, onlyWatched, personal.data, exposureId, exposureAxis) {
        portfolioRows(snapshot, query, kind, sector, order, accountId)
            .filter { !onlyWatched || it.position.id in personal.watches.map { watch -> watch.uid } }
            .filter { exposureId == null || exposureMembership(exposureAxis, it.position.id).any { entry -> entry.optString("id") == exposureId } }
    }
    var frozenOrder by rememberSaveable(query, kind, sector, order, accountId, onlyWatched, exposureId) { mutableStateOf<List<String>?>(null) }
    val lookup = candidates.associateBy(::portfolioRowKey)
    val candidateKeys = candidates.map(::portfolioRowKey)
    val stableKeys = frozenOrder?.filter { it in lookup }?.let { it + candidateKeys.filterNot(it::contains) } ?: candidateKeys
    val rows = stableKeys.mapNotNull(lookup::get)
    LaunchedEffect(candidateKeys) { if (frozenOrder == null) frozenOrder = candidateKeys }
    val restricted = rows.filter { it.position.blocked }
    val cash = rows.filter { it.position.instrumentType in setOf("cash", "currency") && !it.position.blocked }
    val assets = rows.filter { !it.position.blocked && it.position.instrumentType !in setOf("cash", "currency") }
    val groups = assets.groupBy { row -> when (group) {
        1 -> row.position.company?.takeIf(String::isNotBlank) ?: "Компания не указана"
        2 -> row.position.sector?.takeIf(String::isNotBlank) ?: "Отрасль не указана"
        3, 4 -> exposureMembership(exposureAxis, row.position.id).let { memberships -> when {
            memberships.isEmpty() -> "Связь не подтверждена"
            memberships.size == 1 -> memberships.first().optionalText("label") ?: "Имя не получено"
            else -> "Несколько подтверждённых связей"
        } }
        else -> row.account.name
    } }
    val changed = accountId != null || query.isNotBlank() || kind != "all" || sector != null || group != 0 || order != 0 || onlyWatched || exposureId != null
    Column(modifier.fillMaxWidth()) {
        SpectrumTextField(query, { query = it }, label = { Text("Название, тикер или ISIN") }, singleLine = true,
            modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 8.dp).testTag("portfolio-search"))
        Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = { filtersOpen = true }) { Text("Фильтры и порядок") }
            Text("${rows.size}", Modifier.weight(1f), style = MaterialTheme.typography.bodySmall)
            if (changed) TextButton(onClick = { query = ""; kind = "all"; sector = null; group = 0; order = 0; accountId = null; onlyWatched = false; exposureId = null }) { Text("Сбросить") }
        }
        Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            FilterChip(selected = onlyWatched, onClick = { onlyWatched = !onlyWatched }, label = { Text("Наблюдение") })
            TextButton(onClick = { saveFilter = true }, enabled = personal.loaded && !personal.busy) { Text("Сохранить фильтр") }
            TextButton(onClick = { selecting = !selecting; if (!selecting) selectedKeys = arrayListOf() }) { Text(if (selecting) "Готово" else "Выбрать") }
        }
        if (stableKeys != candidateKeys) TextButton(onClick = { frozenOrder = candidateKeys }, modifier = Modifier.fillMaxWidth()) {
            Text("Оценки обновлены · применить новый порядок")
        }
        if (personal.filters.isNotEmpty()) DetailFold("Мои фильтры (${personal.filters.size})", Modifier.padding(horizontal = 20.dp)) {
            personal.filters.forEach { saved -> Row(Modifier.fillMaxWidth()) {
                TextButton(onClick = { accountId = saved.accountId; query = saved.query; kind = saved.kind; sector = saved.sector; group = saved.group; order = saved.order; onlyWatched = saved.watchedOnly; exposureId = saved.exposureId }, modifier = Modifier.weight(1f)) { Text(saved.title) }
                TextButton(onClick = { personal.deleteFilter(saved.id) }, enabled = !personal.busy) { Text("Удалить") }
            } }
        }
        if (accountId != null && snapshot.accounts.none { it.id == accountId }) Notice("Счёт сохранённого фильтра сейчас недоступен. Выберите другой счёт или сбросьте фильтр.")
        if (selecting) SpectrumCard(Modifier.padding(horizontal = 20.dp)) {
            Text("Выбрано ${chosen.size} из 20", style = MaterialTheme.typography.titleMedium)
            if (chosen.size != selectedKeys.size) Text("Часть выбранных позиций исчезла из текущих данных и не включена в итог.")
            chosen.mapNotNull { it.position.currentValue }.groupBy { it.currency }.forEach { (currency, amounts) ->
                DataRow("Стоимость выбранного", PrivateValue("${decimalText(amounts.sumOf { it.value.toBigDecimal() })} ${currencySymbol(currency)}"))
                val total = snapshot.totalValue.takeIf { it.currency == currency }?.value?.toBigDecimal()
                if (total != null && total.signum() > 0) DataRow("Доля текущего капитала", PrivateValue("${decimalText(amounts.sumOf { it.value.toBigDecimal() }.multiply(java.math.BigDecimal(100)).divide(total, 4, java.math.RoundingMode.HALF_UP))}%"))
            }
            if (chosen.any { it.position.currentValue == null }) Text("Итог неполный: есть позиции без оценки.")
            Row {
                TextButton(onClick = { comparing = true }, enabled = chosen.size in 2..3) { Text("Сравнить 2–3") }
                TextButton(onClick = { batchReason = "" }, enabled = chosen.isNotEmpty()) { Text("Наблюдать") }
                TextButton(onClick = { selectedKeys = arrayListOf() }) { Text("Сбросить") }
            }
            if (chosen.isNotEmpty()) {
                SaveResearchButton(comparisonArchive(chosen), "Выбранные позиции (${chosen.size})",
                    source = "T‑Invest · выбранные позиции по счетам", observedAt = snapshot.asOf)
                DetailFold("Выбранные позиции") { chosen.forEach { Text("${it.position.title} · ${it.account.name}") } }
            }
        }
        personal.error?.let { Text(it, Modifier.padding(horizontal = 20.dp), color = MaterialTheme.colorScheme.error) }
        if (accountId != null || kind != "all" || sector != null || group != 0 || order != 0) Text(
            listOfNotNull(snapshot.accounts.firstOrNull { it.id == accountId }?.name, labels[kinds.indexOf(kind).coerceAtLeast(0)], sector?.let { if (it == "__unknown__") "Отрасль не указана" else it },
                listOf("По счетам", "По названиям компаний", "По отраслям", "По подтверждённым эмитентам", "По подтверждённым группам")[group],
                listOf("Сначала ограничения", "По стоимости", "По доле", "По названию")[order]).joinToString(" · "),
            Modifier.padding(horizontal = 20.dp), style = MaterialTheme.typography.bodySmall)
        LazyColumn(Modifier.weight(1f).fillMaxWidth().testTag("portfolio-content"), state = listState,
            contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
            if (group in 3..4) item(key = "verified-exposures") { VerifiedExposurePanel(exposureRequest, exposureAxis, exposureId) { exposureId = it } }
            if (rows.isEmpty()) item { WorkspaceEmpty(if (changed) "Ничего не найдено" else "Активов пока нет",
                if (changed) "Измените запрос или условия поиска." else "Счёт подключён. Полученные позиции появятся здесь.") }
            if (restricted.isNotEmpty()) {
                item { SpectrumCard {
                    Text("Ограниченные активы · ${restricted.size}", style = MaterialTheme.typography.titleMedium)
                    Text("Условия сделки уточняются у брокера.", style = MaterialTheme.typography.bodySmall)
                    TextButton(onClick = { showRestricted = !showRestricted }) { Text(if (showRestricted) "Свернуть" else "Посмотреть ограничения") }
                } }
                if (showRestricted) items(restricted, key = { "restricted:${it.account.id}:${it.position.id}" }) { row ->
                    PositionLine(row.position, total = snapshot.totalValue, accountName = row.account.name,
                        selected = portfolioRowKey(row) in selectedKeys, sharedKey = portfolioRowKey(row)) { open(row.account.id, row.position) }
                }
            }
            cashRows(cash, snapshot, showCash, { showCash = !showCash }, open, selectedKeys.toSet())
            if (group == 1) item { Notice("Здесь объединены одинаковые названия из данных брокера. Для проверенных отношений выберите «Проверенные эмитенты» или «Проверенные группы».") }
            if (order in 1..2 && rows.any { it.position.currentValue?.currency != snapshot.totalValue.currency }) item {
                Notice("Сначала — оценки в ${snapshot.totalValue.currency}. Несопоставимые валюты и неизвестные значения расположены ниже.")
            }
            assetGroups(groups, group, snapshot, open, selectedKeys.toSet())
            if (snapshot.accounts.any { it.virtualPositions.isNotEmpty() }) item { DetailFold("Виртуальные позиции") {
                val destination = LocalPortfolioDestination.current
                snapshot.accounts.filter { it.virtualPositions.isNotEmpty() }.forEach { account ->
                    TextButton(onClick = { destination(PortfolioDestination(accountId = account.id, section = 0)) }) { Text("${account.name} · ${account.virtualPositions.size}") }
                }
            } }
        }
    }
    if (filtersOpen) AlertDialog(onDismissRequest = { filtersOpen = false }, title = { Text("Состав портфеля") }, text = {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            WorkspaceChoices("Счёт", listOf("Все счета") + snapshot.accounts.map { it.name }, snapshot.accounts.indexOfFirst { it.id == accountId } + 1) {
                accountId = snapshot.accounts.getOrNull(it - 1)?.id
            }
            WorkspaceChoices("Класс", labels, kinds.indexOf(kind).coerceAtLeast(0)) { kind = kinds[it] }
            WorkspaceChoices("Группировать", listOf("По счетам", "По названиям компаний", "По отраслям", "Проверенные эмитенты", "Проверенные группы"), group) { group = it; exposureId = null }
            WorkspaceChoices("Порядок", listOf("Сначала ограничения", "По стоимости", "По доле", "По названию"), order) { order = it }
        }
    }, confirmButton = { TextButton(onClick = { filtersOpen = false }) { Text("Показать") } })
    if (saveFilter) AlertDialog(onDismissRequest = { saveFilter = false }, title = { Text("Сохранить условия") },
        text = { SpectrumTextField(filterTitle, { filterTitle = it.take(100) }, label = { Text("Название фильтра") }) },
        confirmButton = { TextButton(onClick = {
            personal.saveFilter(SavedPortfolioFilter(UUID.randomUUID().toString(), filterTitle, query, accountId, kind, sector, group, order, onlyWatched, exposureId))
            saveFilter = false; filterTitle = ""
        }, enabled = filterTitle.isNotBlank() && !personal.busy && personal.filters.size < 30) { Text("Сохранить") } },
        dismissButton = { TextButton(onClick = { saveFilter = false }) { Text("Отмена") } })
    if (comparing) AssetComparisonDialog(chosen.take(3), snapshot.asOf, { comparing = false })
    if (batchReason != null) AlertDialog(onDismissRequest = { batchReason = null }, title = { Text("Причина наблюдения") },
        text = { SpectrumTextField(batchReason ?: "", { batchReason = it.take(800) }, label = { Text("Общая заметка для выбранных бумаг") }) },
        confirmButton = { TextButton(onClick = {
            personal.watchMany(chosen.map { it.position.id to it.position.title }, batchReason ?: ""); batchReason = null
        }, enabled = !batchReason.isNullOrBlank()) { Text("Добавить") } }, dismissButton = { TextButton(onClick = { batchReason = null }) { Text("Отмена") } })
}

internal fun portfolioRowKey(row: PortfolioRow): String = "${row.account.id}:${row.position.id}"

internal fun portfolioRows(snapshot: PortfolioSnapshot, query: String, kind: String, sector: String?, order: Int, selectedAccount: String?): List<PortfolioRow> {
    val all = snapshot.accounts.filter { selectedAccount == null || it.id == selectedAccount }.flatMap { account ->
        account.positions.map { PortfolioRow(account, it) }
    }.filter { matchingPosition(it.position, query) && matchingSector(it.position.sector, sector) &&
        matchingKind(it.position.instrumentType, kind) }
    return sortedPortfolioRows(all, order, snapshot.totalValue.currency)
}

private fun LazyListScope.assetGroups(groups: Map<String, List<PortfolioRow>>, group: Int,
    snapshot: PortfolioSnapshot, onPosition: (String, PortfolioPosition) -> Unit, selected: Set<String> = emptySet()) {
            groups.forEach { (label, entries) ->
                item(key = "heading:$label") {
                    SectionHeading(label)
                    AssetGroupValues(entries, group)
                }
                items(entries, key = { "${it.account.id}:${it.position.id}" }) { row ->
                    val duration = portfolioMotionDuration(220, 100)
                    Box(Modifier.animateItem(
                        fadeInSpec = if (duration > 0) androidx.compose.animation.core.tween(duration) else null,
                        placementSpec = if (duration > 0) androidx.compose.animation.core.tween(duration) else null,
                        fadeOutSpec = if (duration > 0) androidx.compose.animation.core.tween(duration) else null)) {
                        PositionLine(row.position, total = snapshot.totalValue,
                            accountName = if (group == 0) null else row.account.name, selected = portfolioRowKey(row) in selected,
                            sharedKey = portfolioRowKey(row)) { onPosition(row.account.id, row.position) }
                    }
                    Spacer(Modifier.height(4.dp))
                }
            }
}

private fun LazyListScope.cashRows(cash: List<PortfolioRow>, snapshot: PortfolioSnapshot,
    showCash: Boolean, onToggle: () -> Unit, onPosition: (String, PortfolioPosition) -> Unit, selected: Set<String> = emptySet()) {
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
                    PositionLine(row.position, total = snapshot.totalValue, accountName = row.account.name, sharedKey = portfolioRowKey(row), selected = portfolioRowKey(row) in selected) { onPosition(row.account.id, row.position) }
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

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 @Composable
private fun AssetGroupValues(entries: List<PortfolioRow>, group: Int) {
    if (group == 1) {
        val values = entries.mapNotNull { it.position.currentValue }
        values
            .groupBy { it.currency }
            .forEach { (currency, amounts) ->
                DataRow(
                    "Стоимость выпусков · $currency",
                    decimalText(amounts.sumOf { it.value.toBigDecimal() }) +
                        " " +
                        currencySymbol(currency),
                )
            }
        if (values.size != entries.size) Notice("Часть выпусков без оценки; сумма неполная.")
    }
}
