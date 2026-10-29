package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import org.json.JSONObject
import java.time.Instant
import ru.omnicio.app.data.workspace.VolumeWorkspaceClient
import ru.omnicio.app.ui.spectrum.*

/** Reads the durable server corpus; navigating never starts a model or a crawl. */
@Composable
fun ServerResearchScreen(onBack: () -> Unit, onSaved: () -> Unit) {
    val user = LocalWorkspaceSession.current.userId
    var query by rememberSaveable(user) { mutableStateOf("") }
    var settledQuery by remember(user) { mutableStateOf("") }
    var kind by rememberSaveable(user) { mutableIntStateOf(0) }
    var selected by rememberSaveable(user) { mutableStateOf<String?>(null) }
    var cursors by rememberSaveable(user, kind, settledQuery) { mutableStateOf(listOf("")) }
    LaunchedEffect(query) { delay(350); settledQuery = query.trim() }
    val status = rememberWorkspaceResource("/workspace/osint/status")
    val suffix = listOf("limit=25", "q=" + VolumeWorkspaceClient.encode(settledQuery),
        when (kind) { 1 -> "kind=report"; 2 -> "kind=news"; else -> "" },
        cursors.last().takeIf { it.isNotBlank() }?.let { "before_id=$it" }.orEmpty())
        .filter { it.isNotBlank() }.joinToString("&")
    val documents = rememberWorkspaceResource("/workspace/osint/documents?$suffix")
    WorkspaceDetailPage("Источники и документы", "Собираются и сохраняются на сервере", onBack, SpectrumSymbol.Sources) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding).testTag("server-research"),
            contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            item {
                WorkspaceRequestState(status)
                status.data?.let { ServerCorpusStatus(it) }
            }
            item {
                SpectrumTextField(query, { query = it.take(160) }, label = { Text("Найти в сохранённых публикациях") }, modifier = Modifier.fillMaxWidth())
                WorkspaceChoices("Материалы", listOf("Все", "Отчёты", "Новости"), kind) { kind = it }
                SpectrumSecondaryButton("Мои сохранённые исследования", onSaved, Modifier.fillMaxWidth())
            }
            item { WorkspaceRequestState(documents) }
            val rows = documents.data?.records("items").orEmpty()
            if (documents.data != null && rows.isEmpty()) item { Text("По этому запросу пока нет сохранённых публикаций.") }
            if (documents.data?.optBoolean("search_limited") == true) item { Text("Поиск доступен только по названиям последних публикаций.") }
            items(rows, key = { it.text("id") }) { row ->
                SpectrumCard(onClick = { selected = row.text("id") }) {
                    SpectrumBadge(if (row.text("kind") == "report") "Отчёт компании" else "Публикация")
                    Text(row.text("title"), style = MaterialTheme.typography.titleMedium)
                    Text(row.text("publisher") + " · " + publicationTime(row, "published_at"),
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("Сохранено " + publicationTime(row, "last_seen"), style = MaterialTheme.typography.labelMedium)
                }
            }
            item {
                if (cursors.size > 1) SpectrumSecondaryButton("Более новые", { cursors = cursors.dropLast(1) }, Modifier.fillMaxWidth())
                documents.data?.text("next_before_id", "")?.takeIf { it.isNotBlank() }?.let { next ->
                    SpectrumSecondaryButton("Более ранние", { cursors = cursors + next }, Modifier.fillMaxWidth(), !documents.busy)
                }
            }
        }
    }
    selected?.let { id -> ServerDocument(id) { selected = null } }
}

@Composable
private fun ServerCorpusStatus(value: JSONObject) {
    SpectrumCard {
        Text("${value.optInt("documents")} материалов в базе", style = MaterialTheme.typography.titleLarge)
        Text("${value.optInt("in_progress")} загружается · ${value.optInt("due_targets")} ожидает обновления",
            style = MaterialTheme.typography.bodySmall)
        DetailFold("Состояние источников") {
            value.records("sources").forEach { row ->
                Text(row.text("title"), style = MaterialTheme.typography.titleSmall)
                val state = when {
                    row.text("state") == "pending" -> "Первое получение ещё не завершено"
                    row.text("state") == "unavailable" -> "Источник недоступен; сервер повторит попытку"
                    row.optBoolean("stale") -> "Сохранённые сведения требуют обновления"
                    row.text("state") == "partial" || row.optInt("target_failures") > 0 -> "Получена часть материалов"
                    else -> "Источник проверен"
                }
                Text(state + " · ${row.optInt("documents")} материалов", style = MaterialTheme.typography.bodySmall)
                Text("Успешная проверка: " + publicationTime(row, "last_success"), style = MaterialTheme.typography.bodySmall)
                HorizontalDivider()
            }
            Text("Это доступные системе источники. Список не означает полное покрытие всех компаний и новостей.", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun ServerDocument(id: String, close: () -> Unit) {
    val resource = rememberWorkspaceResource("/workspace/osint/documents/" + VolumeWorkspaceClient.encode(id))
    val uriHandler = LocalUriHandler.current
    WorkspaceDialog("Сохранённая публикация", close) {
        WorkspaceRequestState(resource)
        resource.data?.let { row ->
            Text(row.text("title"), style = MaterialTheme.typography.titleLarge)
            Text(row.text("publisher") + " · " + publicationTime(row, "published_at"))
            Text("Получено " + publicationTime(row, "last_seen"), style = MaterialTheme.typography.bodySmall)
            if (row.text("kind") == "report") Text(if (row.optJSONObject("original")?.optBoolean("available") == true)
                "Оригинальный PDF и извлечённый текст сохранены в базе" else "Сохранён извлечённый текст; оригинальный PDF ещё не получен",
                style = MaterialTheme.typography.bodySmall)
            val extraction = row.optJSONObject("analysis")?.optJSONObject("extraction")
            if (extraction?.optBoolean("needs_ocr") == true) Text("В отчёте есть страницы, требующие распознавания текста.")
            if (extraction?.optBoolean("truncated") == true) Text("Извлечён только доступный объём отчёта.")
            Text("Сообщение источника. Числа отчётности требуют проверки периода, единиц и соответствия эмитенту.", style = MaterialTheme.typography.bodySmall)
            ExplainWithAiButton("document", id, row.text("title"), beforeOpen = close)
            row.text("url", "").takeIf { it.startsWith("https://") }?.let { url ->
                SpectrumSecondaryButton("Открыть первоисточник", { uriHandler.openUri(url) }, Modifier.fillMaxWidth())
            }
            val body = row.text("text", "Текст публикации не получен")
            Text(body.take(24_000), style = MaterialTheme.typography.bodyMedium)
            if (body.length > 24_000) Text("Показаны первые 24 000 символов. Полный извлечённый текст сохранён на сервере.")
        }
    }
}

private fun publicationTime(value: JSONObject, field: String): String =
    if (value.isNull(field)) "дата не указана" else runCatching {
        localMoment(Instant.ofEpochSecond(value.getLong(field)).toString())
    }.getOrDefault("дата не указана")
