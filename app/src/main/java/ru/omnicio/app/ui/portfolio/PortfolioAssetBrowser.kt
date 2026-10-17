package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.ui.spectrum.*

private data class PortfolioRow(val account: PortfolioAccount, val position: PortfolioPosition)

/** Grouping is a presentation of broker labels, not an invented issuer risk model. */
@Composable
internal fun PortfolioAssetBrowser(snapshot: PortfolioSnapshot, onPosition: (String, PortfolioPosition) -> Unit,
    modifier: Modifier = Modifier) {
    var kind by rememberSaveable { mutableIntStateOf(0) }
    var group by rememberSaveable { mutableIntStateOf(0) }
    var restrictedFirst by rememberSaveable { mutableStateOf(false) }
    var filtersOpen by rememberSaveable { mutableStateOf(false) }
    val types = listOf(null, "bond", "share", "etf", "cash")
    val rows = remember(snapshot, kind, group, restrictedFirst) {
        snapshot.accounts.flatMap { account -> account.positions.map { PortfolioRow(account, it) } }
            .filter { kind == 0 || it.position.instrumentType == types[kind] ||
                (kind == 4 && it.position.instrumentType == "currency") }
            .sortedWith(compareBy<PortfolioRow> { if (restrictedFirst && it.position.blocked) 0 else 1 }
                .thenBy(String.CASE_INSENSITIVE_ORDER) { it.position.title })
            .groupBy { row -> when (group) {
                1 -> row.position.company?.takeIf(String::isNotBlank) ?: "Компания не указана"
                2 -> row.position.sector?.takeIf(String::isNotBlank) ?: "Отрасль не указана"
                else -> row.account.name
            } }
    }
    Column(modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp), horizontalArrangement = Arrangement.SpaceBetween) {
            TextButton(onClick = { filtersOpen = true }) { Text("Фильтры и порядок") }
            TextButton(onClick = { kind = 0; group = 0; restrictedFirst = false }) { Text("Сбросить") }
        }
        LazyColumn(Modifier.weight(1f).fillMaxWidth(), contentPadding = PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (group == 1) item { Notice("Группировка по названиям компаний из данных брокера; группы связанных эмитентов ещё не определены.") }
            if (rows.isEmpty()) item { SpectrumCard { Text("По этим условиям позиций нет.") } }
            rows.forEach { (label, entries) ->
                item(key = "heading:$label") { SectionHeading(label) }
                items(entries, key = { "${it.account.id}:${it.position.id}" }) { row ->
                    SpectrumCard { PositionLine(row.position) { onPosition(row.account.id, row.position) } }
                }
            }
            if (snapshot.accounts.any { it.virtualPositions.isNotEmpty() }) item { Notice("Виртуальные позиции доступны в подробностях счёта.") }
        }
    }
    if (filtersOpen) AlertDialog(onDismissRequest = { filtersOpen = false },
        title = { Text("Состав портфеля") }, text = {
            androidx.compose.foundation.lazy.LazyColumn(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                item { SpectrumTabs(listOf("Все", "Облигации", "Акции", "Фонды", "Деньги"), kind, { kind = it }) }
                item { ru.omnicio.app.ui.workspace.WorkspaceChoices("Группировать", listOf("По счетам", "По компаниям", "По отраслям"), group) { group = it } }
                item { ru.omnicio.app.ui.workspace.WorkspaceToggle("Сначала ограничения", "Далее — по названию", restrictedFirst) { restrictedFirst = it } }
            }
        }, confirmButton = { TextButton(onClick = { filtersOpen = false }) { Text("Показать") } })
}
