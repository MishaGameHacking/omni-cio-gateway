package ru.omnicio.app.ui

import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import java.time.Instant
import java.time.temporal.ChronoUnit
import ru.omnicio.app.R

@Composable
internal fun OverviewScreen(state: AppUiState, model: OmnicioViewModel, onConnect: () -> Unit) {
    val workspace = state.workspace
    val portfolio = workspace?.portfolio
    LazyColumn(contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item {
            Text("Обзор", style = MaterialTheme.typography.headlineLarge)
            Text(workspace?.connection?.name ?: "Ваш инвестиционный счёт",
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if (workspace == null) {
            item { EmptyState(if (state.busy) "Загружаем данные" else "Данные не получены",
                "Суммы и история появятся после ответа сервера. Отсутствующие значения не заменяются нулями.") }
        } else if (!workspace.connection.connected) {
            item { EmptyState("Подключите свой счёт", "Разрешите чтение данных выбранного счёта Т-Инвестиций. Торговые операции недоступны.", R.drawable.ic_bank) }
            item { Button(onClick = onConnect, modifier = Modifier.fillMaxWidth()) { Text("Подключить счёт") } }
        } else {
            item {
                OmniCard {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text("Стоимость портфеля", Modifier.weight(1f), color = MaterialTheme.colorScheme.onSurfaceVariant)
                        IconButton(onClick = model::toggleAmountsHidden) {
                            OmniIcon(R.drawable.ic_eye, if (state.amountsHidden) "Показать суммы" else "Скрыть суммы")
                        }
                    }
                    Text(money(portfolio?.total, state.amountsHidden), style = MaterialTheme.typography.displaySmall)
                    Text(statusLabel(if (portfolio?.freshness == "fresh") portfolio.analysisStatus else portfolio?.freshness),
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(timestampLabel(portfolio?.capturedAt), style = MaterialTheme.typography.bodySmall)
                }
            }
            item {
                OmniCard {
                    SectionTitle("Деньги на счёте")
                    MetricRow("Всего", money(portfolio?.cash, state.amountsHidden))
                    MetricRow("Не заблокировано", money(portfolio?.freeCash, state.amountsHidden))
                    MetricRow("Заблокировано", money(portfolio?.blockedCash, state.amountsHidden))
                    Text("Незаблокированный остаток по ответу брокера. Это не обещание доступности любой покупки.",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            item { PortfolioHistory(portfolio?.history.orEmpty(), state.amountsHidden) }
            item {
                Button(onClick = model::syncPortfolio, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) {
                    OmniIcon(R.drawable.ic_refresh)
                    Spacer(Modifier.width(8.dp))
                    Text("Обновить у брокера")
                }
            }
            item { SourcesCard(portfolio?.sources.orEmpty()) }
        }
    }
}

@Composable
internal fun MetricRow(label: String, value: String) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.titleMedium)
    }
}

@Composable
internal fun SourcesCard(sources: List<SourceInfo>) {
    val uri = androidx.compose.ui.platform.LocalUriHandler.current
    OmniCard {
        SectionTitle("Источники и актуальность")
        if (sources.isEmpty()) Text("Сервер не передал сведения об источнике. Данные не считаются подтверждёнными.")
        sources.forEach { source ->
            Text(source.name, style = MaterialTheme.typography.titleMedium)
            Text(statusLabel(source.status), style = MaterialTheme.typography.bodySmall)
            Text(timestampLabel(source.at), style = MaterialTheme.typography.bodySmall)
            val url = source.url?.takeIf {
                val parsed = runCatching { java.net.URI(it) }.getOrNull()
                parsed?.scheme == "https" && parsed.host != null && parsed.userInfo == null
            }
            if (url != null) TextButton(onClick = { uri.openUri(url) }) {
                OmniIcon(R.drawable.ic_link)
                Spacer(Modifier.width(8.dp))
                Text("Открыть источник")
            }
        }
    }
}

@Composable
private fun PortfolioHistory(history: List<HistoryPoint>, hidden: Boolean) {
    var days by remember { mutableStateOf<Int?>(null) }
    var index by remember(history, days) { mutableIntStateOf(0) }
    var table by remember { mutableStateOf(false) }
    val periods = listOf("Неделя" to 7, "Месяц" to 30, "Год" to 365, "Всё" to null)
    val cutoff = days?.let { Instant.now().minus(it.toLong(), ChronoUnit.DAYS) }
    val points = history.filter { cutoff == null || !it.at.isBefore(cutoff) }
    val valid = points.filter { it.complete && it.value != null }
    val selected = points.getOrNull(index.coerceIn(0, (points.size - 1).coerceAtLeast(0)))
    OmniCard {
        SectionTitle("История стоимости")
        Text("До 365 последних наблюдений сервера. Изменение стоимости включает пополнения и выводы и не является доходностью.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            periods.forEach { (label, value) -> FilterChip(days == value, { days = value }, label = { Text(label) }) }
        }
        when {
            hidden -> Text("История скрыта вместе с суммами.")
            valid.isEmpty() -> Text("Нет подтверждённой истории за выбранный период.")
            else -> {
                if (selected != null) {
                    Text(if (selected.complete) money(selected.value) else "Неполное наблюдение — значение не показано",
                        style = MaterialTheme.typography.headlineSmall)
                    Text(timestampLabel(selected.at.toString()), style = MaterialTheme.typography.bodySmall)
                }
                HistoryPlot(points, index)
                if (points.size > 1) Slider(value = index.toFloat(), onValueChange = { index = it.toInt() },
                    valueRange = 0f..(points.size - 1).toFloat(), steps = (points.size - 2).coerceAtLeast(0),
                    modifier = Modifier.semantics { contentDescription = "Выбрать наблюдение на графике" })
                Text("Период: ${timestampLabel(points.first().at.toString())} — ${timestampLabel(points.last().at.toString())}",
                    style = MaterialTheme.typography.bodySmall)
                TextButton(onClick = { table = !table }) { Text(if (table) "Скрыть значения" else "Показать значения") }
                if (table) Column(Modifier.heightIn(max = 240.dp).verticalScrollForHistory()) {
                    points.forEach {
                        ListItem(headlineContent = { Text(if (it.complete) money(it.value) else "Нет полного значения") },
                            supportingContent = { Text(timestampLabel(it.at.toString())) })
                    }
                }
            }
        }
    }
}

@Composable
private fun Modifier.verticalScrollForHistory(): Modifier =
    this.then(Modifier.verticalScroll(androidx.compose.foundation.rememberScrollState()))

@Composable
private fun HistoryPlot(points: List<HistoryPoint>, selected: Int) {
    val values = points.filter { it.complete }.mapNotNull { it.value }
    val min = values.minOrNull() ?: return
    val max = values.maxOrNull() ?: return
    val color = MaterialTheme.colorScheme.onSurface
    val grid = MaterialTheme.colorScheme.outlineVariant
    val accent = MaterialTheme.colorScheme.primary
    Column {
        Text(money(max), style = MaterialTheme.typography.labelMedium)
        Canvas(Modifier.fillMaxWidth().height(160.dp).semantics {
            contentDescription = "График стоимости в рублях. Точные значения доступны ползунком и в списке."
        }) {
            val pad = 8.dp.toPx()
            val start = points.first().at.toEpochMilli()
            val span = (points.last().at.toEpochMilli() - start).coerceAtLeast(1)
            fun position(point: HistoryPoint): Offset = Offset(
                pad + (size.width - 2 * pad) * (point.at.toEpochMilli() - start).toDouble().div(span).toFloat(),
                pad + (size.height - 2 * pad) * (1 - chartFraction(requireNotNull(point.value), min, max)),
            )
            for (level in 0..2) {
                val y = pad + (size.height - 2 * pad) * level / 2
                drawLine(grid, Offset(pad, y), Offset(size.width - pad, y), 1.dp.toPx())
            }
            var previous: HistoryPoint? = null
            points.forEachIndexed { index, point ->
                if (!point.complete || point.value == null) { previous = null } else {
                    val offset = position(point)
                    previous?.let { drawLine(color, position(it), offset, 2.dp.toPx(), StrokeCap.Round) }
                    drawCircle(if (index == selected) accent else color, if (index == selected) 6.dp.toPx() else 2.dp.toPx(), offset)
                    previous = point
                }
            }
        }
        Text(money(min), style = MaterialTheme.typography.labelMedium)
    }
}
