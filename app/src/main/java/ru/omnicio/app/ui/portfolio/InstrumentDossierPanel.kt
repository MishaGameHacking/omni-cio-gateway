package ru.omnicio.app.ui.portfolio

import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import ru.omnicio.app.data.market.*
import ru.omnicio.app.data.market.records
import ru.omnicio.app.data.portfolio.PortfolioPosition
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.workspace.*

@Composable
internal fun InstrumentDossierPanel(position: PortfolioPosition, onNavigate: () -> Unit = {}) {
    val request = rememberWorkspaceRequest("/workspace/instruments/${position.id}/dossier")
    WorkspaceRequestNotice(request)
    request.json?.let { payload ->
        if (payload.optString("instrument_uid") != position.id) {
            Text("Идентификатор ответа не совпал с выбранной бумагой. Сведения не показаны.")
        } else {
            SaveResearchButton(payload, "Досье ${position.ticker ?: position.title}", position.id,
                source = "T‑Invest и проверенные источники компании", observedAt = payload.optionalText("as_of"))
            InstrumentDossierContent(payload, onNavigate)
        }
    }
}

@Composable
@OptIn(ExperimentalMaterial3Api::class)
internal fun InstrumentDossierContent(payload: JSONObject, onNavigate: () -> Unit = {}) {
    val sources = payload.records("sources")
    val instrument = payload.sectionData("instrument")
    val destination = LocalPortfolioDestination.current
    var selectedFact by remember(payload.optionalText("instrument_uid")) { mutableStateOf<JSONObject?>(null) }
    Column(verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
        SpectrumCard {
            Text(instrument?.optionalText("title") ?: "Досье инструмента", style = MaterialTheme.typography.titleLarge)
            Text(listOfNotNull(instrument?.optionalText("ticker"), instrument?.optionalText("isin")).joinToString(" · "))
            Text("Обновлено ${dateText(payload.optionalText("as_of"))}", style = MaterialTheme.typography.bodySmall)
            SourceProvenance(sources)
        }
        SpectrumCard {
            Text("Эта бумага на всех счетах", style = MaterialTheme.typography.titleLarge)
            WorkspaceSectionNotice(payload.section("holdings"))
            val holdings = payload.sectionData("holdings")?.records("items").orEmpty()
            holdings.forEach { holding ->
                Text(holding.optionalText("account_name") ?: "Счёт", style = MaterialTheme.typography.titleMedium)
                DataRow("Количество", PrivateValue(holding.optionalText("quantity") ?: "Не получено"))
                DataRow("Стоимость", workspaceMoney(holding.optJSONObject("value")))
                if (holding.optBoolean("blocked")) Text("Есть ограничения")
                TextButton(onClick = { onNavigate(); destination(PortfolioDestination(accountId = holding.optionalText("account_id"), section = 0)) }) { Text("Открыть счёт") }
            }
        }
        SpectrumCard {
            Text("Паспорт рейтинга", style = MaterialTheme.typography.titleLarge)
            val section = payload.section("ratings")
            WorkspaceSectionNotice(section, "Рейтинг для этой бумаги не подтверждён источником.")
            val data = section?.optJSONObject("data")
            data?.records("items").orEmpty().forEach { rating ->
                Text("${rating.optionalText("agency") ?: "Агентство не указано"} · ${rating.optionalText("grade") ?: "Оценка не получена"}", style = MaterialTheme.typography.titleMedium)
                DataRow("Шкала", rating.optionalText("scale") ?: "Не указана")
                DataRow("Объект", when (rating.optionalText("subject_kind")) { "issue" -> "Выпуск"; "issuer", "company" -> "Компания"; else -> "Не подтверждён" })
                rating.optionalText("subject_id")?.let { DataRow("Идентификатор объекта", it) }
                DataRow("Статус", rating.optionalText("status") ?: "Не получен")
                DataRow("Прогноз", rating.optionalText("outlook") ?: "Не опубликован")
                rating.optJSONObject("source")?.let { SourceProvenance(listOf(it), title = "Публикация и актуальность рейтинга") }
            }
            data?.stringList("warnings").orEmpty().forEach { Text(it) }
            val history = data?.records("history").orEmpty()
            if (history.isNotEmpty()) DetailFold("Как менялся рейтинг") { history.forEach { row ->
                DataRow(dateText(row.optionalText("published_at") ?: row.optionalText("date")), "${row.optionalText("agency") ?: ""} · ${row.optionalText("grade") ?: "Не получено"}")
            } }
        }
        SpectrumCard {
            Text("Показатели компании", style = MaterialTheme.typography.titleLarge)
            WorkspaceSectionNotice(payload.section("metrics"))
            val metrics = payload.sectionData("metrics")
            metrics?.records("items").orEmpty().forEach { metric ->
                val raw = metric.optionalText("value")
                val value = raw?.toBigDecimalOrNull()?.let { decimalText(it, 4) } ?: raw ?: "Не получено"
                DataRow(metric.optionalText("label") ?: "Показатель", PrivateValue(listOfNotNull(value,
                    metric.optionalText("unit"), metric.optionalText("currency")).joinToString(" ")))
                metric.optionalText("period")?.let { Text("Период: $it", style = MaterialTheme.typography.bodySmall) }
                SourceProvenance(sources, metric.stringList("source_ids"), "Откуда получено значение")
                TextButton(onClick = { selectedFact = JSONObject(metric.toString()).put("title", metric.optionalText("label")).put("summary", listOfNotNull(raw, metric.optionalText("unit"), metric.optionalText("currency")).joinToString(" ")) }) {
                    Text("Факт → компания → моя позиция")
                }
            }
            val conflicts = metrics?.records("conflicts").orEmpty()
            if (conflicts.isNotEmpty()) DetailFold("Расхождения источников (${conflicts.size})", initiallyOpen = true) {
                conflicts.forEach { conflict ->
                    Text(conflict.optionalText("label") ?: conflict.optionalText("metric") ?: "Источники расходятся", style = MaterialTheme.typography.titleMedium)
                    conflict.records("observations").forEach { observation ->
                        DataRow(observation.optionalText("source_id") ?: "Источник", PrivateValue(observation.optionalText("value") ?: "Не получено"))
                        observation.optionalText("period")?.let { Text(it) }
                    }
                    conflict.optionalText("reason")?.let { Text(it) }
                    Text("Расхождение не разрешено автоматически. Сверьте период, единицы и публикации.", style = MaterialTheme.typography.bodySmall)
                    SourceProvenance(sources, conflict.stringList("source_ids"))
                }
            }
        }
        SpectrumCard {
            Text("Календарь отчётности", style = MaterialTheme.typography.titleLarge)
            WorkspaceSectionNotice(payload.section("reports"), "Проверенные даты отчётов не получены.")
            payload.sectionData("reports")?.records("items").orEmpty().sortedBy { it.optString("date") }.forEach { report ->
                Text("${report.optionalText("title") ?: "Отчёт"} · ${dateText(report.optionalText("date"), "dd.MM.yyyy")}", style = MaterialTheme.typography.titleMedium)
                Text(if (report.optString("status") == "published") "Опубликован" else "Дата объявлена источником")
                SourceProvenance(sources, report.stringList("source_ids"))
            }
        }
        SpectrumCard {
            Text("События и новости", style = MaterialTheme.typography.titleLarge)
            WorkspaceSectionNotice(payload.section("news"))
            val items = payload.sectionData("news")?.records("items").orEmpty()
            val unique = deduplicateSourceEvents(items)
            unique.forEach { event ->
                Text(event.optionalText("title") ?: "Событие", style = MaterialTheme.typography.titleMedium)
                Text(dateText(event.optionalText("published_at")), style = MaterialTheme.typography.bodySmall)
                Text(when (event.optString("relationship")) { "verified" -> "Факт связан с компанией источником"; "broker_link" -> "Источник отнёс событие к инструменту"; else -> "Связь требует проверки" }, style = MaterialTheme.typography.bodySmall)
                val publications = event.records("sources")
                if (publications.isNotEmpty()) SourceProvenance(publications)
                else SourceProvenance(sources, event.stringList("source_ids"))
                TextButton(onClick = { selectedFact = event }) { Text("Факт → компания → моя позиция") }
            }
            if (items.size != unique.size) Text("Публикации одного события объединены по идентификатору источника; все переданные источники сохранены.")
            if (items.any { it.optionalText("id") == null }) Text("Записи без идентификатора показаны отдельно: одинакового заголовка недостаточно для объединения.")
            val events = payload.sectionData("events")?.records("items").orEmpty()
            if (events.isNotEmpty()) WorkspaceEvents(events, sources)
        }
    }
    selectedFact?.let { fact ->
        var step by remember(fact) { mutableIntStateOf(0) }
        ModalBottomSheet(onDismissRequest = { selectedFact = null }) {
            Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
                Text("Контекст факта", style = MaterialTheme.typography.headlineSmall)
                SpectrumTabs(listOf("Факт", "Компания", "Мои позиции"), step, { step = it })
                when (step) {
                    0 -> {
                        Text(fact.optionalText("title") ?: "Полученный факт", style = MaterialTheme.typography.titleLarge)
                        fact.optionalText("summary")?.let { Text(PrivateValue(it)) }
                        fact.optionalText("period")?.let { DataRow("Период", it) }
                        val publications = fact.records("sources")
                        if (publications.isNotEmpty()) SourceProvenance(publications)
                        else SourceProvenance(sources, fact.stringList("source_ids"))
                        TextButton(onClick = { step = 1 }) { Text("Перейти к компании") }
                    }
                    1 -> {
                        Text(instrument?.optionalText("issuer_name") ?: "Эмитент не подтверждён источником", style = MaterialTheme.typography.titleLarge)
                        instrument?.optionalText("issuer_id")?.let { DataRow("Идентификатор эмитента", it) }
                        Text("Инструмент: ${instrument?.optionalText("title") ?: payload.optString("instrument_uid")}")
                        instrument?.optJSONObject("issuer_source")?.let { SourceProvenance(listOf(it)) }
                        Text("Связь с бумагой и связь с компанией проверяются отдельно. Заголовок не доказывает влияние на цену.")
                        TextButton(onClick = { step = 2 }) { Text("Мои позиции в этой бумаге") }
                    }
                    else -> {
                        val holdings = payload.sectionData("holdings")?.records("items").orEmpty()
                        WorkspaceSectionNotice(payload.section("holdings"))
                        holdings.forEach { holding ->
                            SpectrumCard {
                                Text(holding.optionalText("account_name") ?: "Счёт", style = MaterialTheme.typography.titleMedium)
                                DataRow("Количество", PrivateValue(holding.optionalText("quantity") ?: "Не получено"))
                                DataRow("Стоимость", workspaceMoney(holding.optJSONObject("value")))
                                TextButton(onClick = {
                                    selectedFact = null; onNavigate()
                                    destination(PortfolioDestination(section = 1, accountId = holding.optionalText("account_id"), query = payload.optString("instrument_uid")))
                                }) { Text("Открыть текущую позицию") }
                            }
                        }
                        if (holdings.isEmpty()) Text("В полученном снимке этой бумаги на ваших счетах нет.")
                    }
                }
                TextButton(onClick = { selectedFact = null }, modifier = Modifier.fillMaxWidth()) { Text("Закрыть контекст") }
                Spacer(Modifier.windowInsetsBottomHeight(WindowInsets.safeDrawing))
            }
        }
    }
}
