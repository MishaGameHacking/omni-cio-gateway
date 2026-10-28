package ru.omnicio.app.ui.home

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.*
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import ru.omnicio.app.BuildConfig
import ru.omnicio.app.data.portfolio.PortfolioCurrency
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.workspace.*

/** Reads saved server evidence only while this partial-screen panel is open. */
@Composable
internal fun HomeSystemReadiness(currency: PortfolioCurrency) {
    val session = LocalWorkspaceSession.current
    var open by rememberSaveable(session.userId, currency.name) { mutableStateOf(false) }
    val resource = rememberWorkspaceResource("/workspace/system-readiness?currency=${currency.name}", enabled = open)
    val foreground = workspaceForeground()
    val refresh by rememberUpdatedState(resource.refresh)
    LaunchedEffect(open, foreground) {
        if (open && foreground) while (isActive) { delay(60_000); refresh() }
    }
    SpectrumCard(Modifier.testTag("system-readiness-entry"), onClick = { open = true }) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            SpectrumIcon(SpectrumSymbol.Sources, Modifier.size(36.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("Данные для анализа", style = MaterialTheme.typography.titleMedium)
                Text("Свежесть, источники и ограничения", style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        Text("Версия ${BuildConfig.VERSION_NAME} · ${BuildConfig.VERSION_CODE}",
            style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.testTag("installed-app-version"))
    }
    if (open) WorkspaceDialog("Данные для анализа", onDismiss = { open = false }) {
        val model = remember(resource.data?.toString()) { systemReadinessModel(resource.data) }
        if (resource.busy) SpectrumLoadingIndicator(description = "Проверяем состояние данных")
        if (resource.error != null) {
            Text(resource.error, color = MaterialTheme.colorScheme.error,
                modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
            if (model != null) Text("Ниже последние полученные сведения. Текущая свежесть не подтверждена.",
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if (model == null && !resource.busy && resource.error == null) {
            Text("Сервер пока не передал подтверждённое состояние данных.",
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if (model != null) ReadinessDetails(model, currentResponse = resource.error == null && !resource.busy)
        SpectrumSecondaryButton("Обновить сведения", resource.refresh, Modifier.fillMaxWidth(), enabled = !resource.busy)
        SpectrumSecondaryButton("Закрыть", { open = false }, Modifier.fillMaxWidth())
    }
}

@Composable
private fun ReadinessDetails(model: SystemReadinessModel, currentResponse: Boolean) {
    SpectrumBadge(if (model.readOnlyConfirmed) "Режим наблюдения" else "Режим не подтверждён")
    Text("Проверено · ${localMoment(model.evaluatedAt)}", style = MaterialTheme.typography.bodySmall)
    Text(model.valuationAt?.let { "Оценка портфеля · ${localMoment(it)}" } ?: "Время оценки портфеля не получено",
        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    Text(if (currentResponse) "Актуальных разделов: ${model.currentCount} из ${model.lanes.size}"
        else "Последняя проверка: ${model.currentCount} из ${model.lanes.size} разделов были актуальны",
        style = MaterialTheme.typography.titleMedium)
    model.freshnessFraction?.let { fraction ->
        LinearProgressIndicator(progress = { fraction }, modifier = Modifier.fillMaxWidth()
            .semantics { contentDescription = "Доля актуальных разделов данных на момент проверки" },
            color = if (currentResponse) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
    }
    if (model.lanes.isEmpty()) Text("Разделы ещё не получены.")
    model.lanes.forEach { lane ->
        Column(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(lane.title, style = MaterialTheme.typography.titleSmall)
            Text(readinessStateTitle(lane.state), style = MaterialTheme.typography.bodyMedium,
                color = if (currentResponse && lane.current) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
            lane.observedAt?.let { Text(localMoment(it), style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
    }
    if (model.notices.isNotEmpty()) DetailFold("Что требует внимания") {
        model.notices.forEach { Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    }
    DetailFold("Источники и сверка") {
        Text("Записей источников: ${model.sourceCount?.toString() ?: "нет сведений"}")
        Text("Неподтверждённых ссылок: ${model.unresolvedSources?.toString() ?: "нет сведений"}")
        Text(if (model.liveCashReconciled) "Независимая сверка денег подтверждена сервером."
            else "Независимая сверка денежных остатков пока не подтверждена.")
        Text("Свежесть публикации и проверка её содержания — разные условия. Новая проверка статуса не обновляет оценку портфеля.",
            color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
