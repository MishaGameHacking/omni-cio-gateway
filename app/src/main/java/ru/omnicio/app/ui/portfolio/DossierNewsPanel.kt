package ru.omnicio.app.ui.portfolio

import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton

import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.key
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp
import java.net.URI
import org.json.JSONObject
import ru.omnicio.app.data.market.*
import ru.omnicio.app.ui.spectrum.SpectrumCard
import ru.omnicio.app.ui.workspace.DetailFold
import ru.omnicio.app.ui.workspace.PrivateValue

@Composable
internal fun DossierNewsPanel(payload: JSONObject, select: (String) -> Unit) {
    val items = payload.sectionData("news")?.records("items").orEmpty()
    val sources = dossierSources(payload, "news")
    SpectrumCard {
        Text("События и новости", style = MaterialTheme.typography.titleLarge)
        WorkspaceSectionNotice(payload.section("news"))
        if (items.isEmpty()) Text("В полученных данных связанных публикаций нет.")
        // Grouping and publication roles are validated by the server against exact
        // publication identities/content. Headlines are never merged on the device.
        items.forEach { event -> key(dossierRecordKey("news", event)) {
            Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(event.optionalText("title") ?: "Публикация", style = MaterialTheme.typography.titleMedium)
                Text(dateText(event.optionalText("published_at")), style = MaterialTheme.typography.bodySmall)
                event.optionalText("summary")?.let { Text(PrivateValue(it)) }
                DossierNewsIdentity(event)
                DossierNewsEvidence(event, sources)
                TextButton(onClick = { select(dossierRecordKey("news", event)) }) { Text("Факт → компания → моя позиция") }
            }
        } }
        val events = payload.sectionData("events")?.records("items").orEmpty()
        if (events.isNotEmpty()) WorkspaceEvents(events, dossierSources(payload, "events"))
    }
}

@Composable
internal fun DossierNewsIdentity(event: JSONObject) {
    Text(when (event.optionalText("relationship")) {
        "verified" -> "Связь с компанией подтверждена источником"
        "broker_link" -> "Брокер отнёс публикацию к инструменту"
        else -> "Связь с компанией требует проверки"
    }, style = MaterialTheme.typography.bodySmall)
    Text(when {
        event.optBoolean("event_identity_verified") && event.optString("deduplication") == "reviewed_event_identity" ->
            "Принадлежность публикаций одному событию проверена по источникам."
        event.optString("deduplication") == "identical_publication_content" ->
            "Совпадающие тексты собраны вместе. Это само по себе не подтверждает, что разные сообщения описывают одно событие."
        else -> "Отдельная публикация. Одинаковые заголовки не объединяют события."
    }, style = MaterialTheme.typography.bodySmall)
    Text("Связь с инструментом не доказывает влияние новости на цену.", style = MaterialTheme.typography.bodySmall)
}

@Composable
internal fun DossierNewsEvidence(event: JSONObject, sources: List<JSONObject>) {
    val publications = event.records("sources")
    val primarySources = event.records("primary_sources")
    val proofs = (event.records("evidence_sources") + sources).mapNotNull { it.optionalText("id") }.toSet()
    if (publications.isNotEmpty()) DetailFold("Публикации и их роли (${publications.size})") {
        publications.forEach { publication -> PublicationRecord(publication, primarySources.isNotEmpty(),
            publication.optionalText("review_source_id") in proofs) }
    }
    if (primarySources.isNotEmpty()) {
        SourceProvenance(primarySources, title = "Проверенный первичный источник")
        primarySources.forEach { SourcePublicationLink(it, "Открыть проверенный первичный источник") }
    } else Text("Первичный источник не подтверждён. Ссылка брокера и ранняя дата публикации его не заменяют.", style = MaterialTheme.typography.bodySmall)
    val identifiers = event.stringList("source_ids") + publications.flatMap {
        listOfNotNull(it.optionalText("source_id"), it.optionalText("review_source_id"))
    }
    val evidence = (event.records("evidence_sources") + sources.filter { it.optString("id") in identifiers })
        .distinctBy { it.optionalText("id") ?: it.toString() }
    SourceProvenance(evidence, title = "Основания связи и происхождение публикаций")
}

@Composable
private fun PublicationRecord(publication: JSONObject, hasVerifiedPrimary: Boolean, hasProof: Boolean) {
    Text(publication.optionalText("provider") ?: "Поставщик публикации не указан", style = MaterialTheme.typography.titleMedium)
    val role = publication.optionalText("publication_role")
    Text(when {
        role == "primary" && hasVerifiedPrimary && hasProof -> "Первичный источник: проверенная связь"
        role == "repost" && hasProof -> "Републикация: роль проверена"
        role == "independent_report" && hasProof -> "Самостоятельное сообщение: роль проверена"
        else -> "Роль публикации не подтверждена"
    })
    publication.optionalText("published_at")?.let { Text("Опубликовано: ${dateText(it)}", style = MaterialTheme.typography.bodySmall) }
    SourcePublicationLink(publication, "Открыть эту публикацию")
    DetailFold("Идентификатор и основание роли") {
        publication.optionalText("broker_news_id")?.let { DataRow("Запись у брокера", it) }
        publication.optionalText("source_id")?.let { DataRow("Источник", it) }
        publication.optionalText("review_source_id")?.let { DataRow("Подтверждающий документ", it) }
        publication.optionalText("publication_role_basis")?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
    }
}

@Composable
private fun SourcePublicationLink(source: JSONObject, title: String) {
    val url = source.optionalText("url") ?: return
    val valid = runCatching { URI(url).let { it.scheme == "https" && it.host != null && it.userInfo == null } }.getOrDefault(false)
    if (!valid) return
    val handler = LocalUriHandler.current
    TextButton(onClick = { runCatching { handler.openUri(url) } }) { Text(title) }
}
