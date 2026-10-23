package ru.omnicio.app.ui.workspace

import ru.omnicio.app.ui.spectrum.SpectrumAlertDialog as AlertDialog

import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton

import ru.omnicio.app.ui.spatial.SpatialBackHandler as BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import ru.omnicio.app.data.market.records
import ru.omnicio.app.data.portfolio.PortfolioUiState
import ru.omnicio.app.data.workspace.*
import ru.omnicio.app.ui.portfolio.*
import ru.omnicio.app.ui.research.ResearchSnapshot
import ru.omnicio.app.ui.spectrum.*

@Composable
fun SaveResearchButton(payload: JSONObject, defaultTitle: String, instrumentId: String? = null,
    start: String? = null, end: String? = null, source: String = "T‑Invest / Analyst AI", observedAt: String? = null) {
    val personal = rememberPersonalWorkspace()
    var open by rememberSaveable { mutableStateOf(false) }
    var title by rememberSaveable(defaultTitle) { mutableStateOf(defaultTitle) }
    var note by rememberSaveable { mutableStateOf("") }
    TextButton(onClick = { open = true }, enabled = personal.loaded && !personal.busy) { Text("Сохранить исследование") }
    personal.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
    if (open) AlertDialog(onDismissRequest = { open = false }, title = { Text("Сохранить с контекстом") }, text = {
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            SpectrumTextField(title, { title = it.take(140) }, label = { Text("Название исследования") }, modifier = Modifier.fillMaxWidth())
            SpectrumTextField(note, { note = it.take(2000) }, label = { Text("Что проверяем / ваша заметка") }, modifier = Modifier.fillMaxWidth())
            Text("Источник: $source", style = MaterialTheme.typography.bodySmall)
            Text("Наблюдение: ${dateText(observedAt)}", style = MaterialTheme.typography.bodySmall)
            if (start != null || end != null) Text("Период: ${start ?: "не указан"} — ${end ?: "не указан"}")
            Text("Сохранённый снимок можно открыть без сети. Новые сведения не меняют его содержание.", style = MaterialTheme.typography.bodySmall)
            if (personal.research.size >= 40) Text("Уже сохранено 40 исследований. Удалите ненужное в разделе «Сохранённое».", color = MaterialTheme.colorScheme.error)
        }
    }, confirmButton = { TextButton(onClick = {
        personal.saveResearch(ResearchDraft(title, instrumentId, start, end, source, observedAt, note), JSONObject(payload.toString())); open = false
    }, enabled = title.isNotBlank() && personal.research.size < 40 && !personal.busy) { Text("Сохранить") } },
        dismissButton = { TextButton(onClick = { open = false }) { Text("Отмена") } })
}

@Composable
fun ResearchLibraryScreen(state: PortfolioUiState, onBack: () -> Unit, initialId: String? = null) {
    val personal = rememberPersonalWorkspace()
    val user = LocalWorkspaceSession.current.userId
    var query by rememberSaveable(user) { mutableStateOf("") }
    var selectedId by rememberSaveable(user, initialId) { mutableStateOf(initialId) }
    var archive by remember(user, selectedId) { mutableStateOf<JSONObject?>(null) }
    var archiveLoaded by remember(user, selectedId) { mutableStateOf(false) }
    var deleteId by rememberSaveable(user) { mutableStateOf<String?>(null) }
    val delete = personal.research.firstOrNull { it.id == deleteId }
    var currentKey by rememberSaveable(user) { mutableStateOf<String?>(null) }
    val selected = personal.research.firstOrNull { it.id == selectedId }
    val snapshot = (state as? PortfolioUiState.Ready)?.snapshot
    BackHandler(selectedId != null) { selectedId = null }
    LaunchedEffect(user, selectedId) {
        selectedId?.let { archive = personal.store.archive(it); archiveLoaded = true }
    }
    WorkspaceDetailPage("Сохранённое", "Исследования с датой и источниками", { if (selectedId != null) selectedId = null else onBack() }, SpectrumSymbol.Sources) { padding ->
        LazyColumn(Modifier.fillMaxSize().semantics { testTagsAsResourceId = true }.testTag("workspace-content")
            .padding(padding).consumeWindowInsets(padding), contentPadding = PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
            if (!personal.loaded) item { SpectrumLoadingIndicator(description = "Читаем сохранённые исследования") }
            personal.error?.let { item { Text(it, color = MaterialTheme.colorScheme.error); TextButton(onClick = personal.retry) { Text("Повторить чтение") } } }
            if (selected == null) {
                item { SpectrumTextField(query, { query = it }, label = { Text("Название, заметка или источник") }, modifier = Modifier.fillMaxWidth()) }
                val entries = personal.research.filter { listOf(it.title, it.note, it.source).any { text -> text.contains(query, true) } }
                if (personal.loaded && entries.isEmpty()) item { WorkspaceEmpty("Пока нет сохранённых исследований", "Откройте исследование бумаги или котировки и нажмите «Сохранить исследование».") }
                items(entries, key = { it.id }) { entry -> SpectrumCard(onClick = { selectedId = entry.id }) {
                    Text(entry.title, style = MaterialTheme.typography.titleLarge)
                    Text("Сохранено ${dateText(entry.capturedAt)}", style = MaterialTheme.typography.bodySmall)
                    Text("Наблюдение ${dateText(entry.observedAt)} · ${entry.source}", style = MaterialTheme.typography.bodySmall)
                    if (entry.note.isNotBlank()) Text(PrivateValue(entry.note))
                    TextButton(onClick = { deleteId = entry.id }) { Text("Удалить") }
                } }
            } else {
                item { SpectrumCard(emphasized = true) {
                    Text(selected.title, style = MaterialTheme.typography.headlineSmall)
                    SpectrumBadge("Сохранённый снимок")
                    Text("Данные на ${dateText(selected.observedAt)}. Текущие сведения могли измениться.")
                    Text("${selected.source} · сохранено ${dateText(selected.capturedAt)}", style = MaterialTheme.typography.bodySmall)
                    if (selected.start != null || selected.end != null) Text("${selected.start ?: "начало не указано"} — ${selected.end ?: "конец не указан"}")
                    if (selected.note.isNotBlank()) Text(PrivateValue(selected.note))
                    val positions = snapshot?.accounts?.flatMap { account -> account.positions.filter { it.id == selected.instrumentId }.map { account to it } }.orEmpty()
                    positions.forEach { (account, position) ->
                        TextButton(onClick = { currentKey = "${account.id}:${position.id}" }) { Text(if (positions.size == 1) "Открыть текущую позицию" else "Текущая позиция · ${account.name}") }
                    }
                } }
                item {
                    SavedArchiveContent(archive, archiveLoaded)
                }
            }
        }
    }
    val current = snapshot?.accounts?.flatMap { account -> account.positions.map { account to it } }?.singleOrNull {
        "${it.first.id}:${it.second.id}" == currentKey
    }
    current?.let { (account, position) -> InstrumentDetailsScreen(position, { currentKey = null }, account.name, sharedKey = currentKey ?: position.id, accountId = account.id) }
    if (currentKey != null && current == null) AlertDialog(onDismissRequest = { currentKey = null }, title = { Text("Текущая позиция не получена") },
        text = { Text("Сохранённое исследование остаётся доступным. Прежняя цена не подставляется вместо текущей позиции.") },
        confirmButton = { TextButton(onClick = { currentKey = null }) { Text("Закрыть") } })
    delete?.let { entry -> AlertDialog(onDismissRequest = { deleteId = null }, title = { Text("Удалить исследование?") },
        text = { Text(entry.title) }, confirmButton = { TextButton(onClick = { personal.deleteResearch(entry.id); deleteId = null }) { Text("Удалить") } },
        dismissButton = { TextButton(onClick = { deleteId = null }) { Text("Оставить") } }) }
}

@Composable
private fun ArchiveContent(payload: JSONObject) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        when {
            payload.has("cards") -> ResearchSnapshot(payload, "archive")
            payload.has("candles") -> {
                val candles = payload.records("candles")
                Text("Котировки · ${payload.optionalText("unit_label") ?: "единица не указана"}")
                Text("Период ${payload.optionalText("start")} — ${payload.optionalText("end")}")
                candles.takeLast(100).forEach { candle ->
                    DataRow(dateText(candle.optionalText("time")), "О ${candle.optionalText("open")} · В ${candle.optionalText("high")} · Н ${candle.optionalText("low")} · З ${candle.optionalText("close")}")
                }
                if (candles.size > 100) Text("В просмотре последние 100 свечей из ${candles.size}. Полный снимок сохранён.")
                SourceProvenance(payload.records("sources"))
            }
            payload.has("comparison") -> payload.records("comparison").forEach { row -> SpectrumCard {
                Text(row.optString("title"), style = MaterialTheme.typography.titleMedium)
                row.records("values").forEach { DataRow(it.optString("label"), it.optString("value")) }
            } }
            payload.has("sections") -> InstrumentDossierContent(payload)
            else -> Text(payload.optionalText("summary") ?: payload.optionalText("explanation") ?: "Подробности доступны в исходном сохранённом исследовании.")
        }
    }
}


@Composable
private fun SavedArchiveContent(archive: JSONObject?, loaded: Boolean) {
    when {
        LocalWorkspacePreferences.current.value.hideHomeBalance -> Text("Исследование скрыто режимом приватности.")
        !loaded -> SpectrumLoadingIndicator(description = "Расшифровываем сохранённый снимок")
        archive == null -> Text("Сохранённый файл недоступен. Исследование не заменено текущими данными.")
        else -> ArchiveContent(archive)
    }
}
