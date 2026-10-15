package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.updates.ReleaseDecision
import ru.omnicio.app.ui.theme.LocalSpectrumMotionPreference
import ru.omnicio.app.ui.updates.UpdateGateActions
import ru.omnicio.app.ui.updates.UpdateGateUi

/** A renderer of the existing verified gate, never a second installer or a bypass. */
@Composable
fun RequiredUpdateScreen(state: UpdateGateUi, actions: UpdateGateActions) {
    val motion = LocalSpectrumMotionPreference.current
    SpectrumBackground(Modifier.fillMaxSize()) {
        LazyColumn(Modifier.fillMaxSize().safeDrawingPadding(),
            contentPadding = PaddingValues(horizontal = 24.dp, vertical = 24.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            item { SpectrumBrand(compact = true) }
            item {
                SpectrumIcon(SpectrumSymbol.Update, Modifier.size(116.dp), selected = true, motionAllowed = motion.enabled)
            }
            item { Text(state.title, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center) }
            item { Text(state.explanation, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center) }
            item { UpdateVersionCard(state) }
            if (state.decision == ReleaseDecision.UPDATE_REQUIRED) item {
                SpectrumAction("Обновить приложение", actions.update, enabled = state.canUpdate)
            }
            item { UpdateProcessLegend() }
            item {
                Text("Файл проверяется перед установкой. Android может запросить разрешение и подтверждение обновления.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall, textAlign = TextAlign.Center)
            }
            item {
                TextButton(onClick = actions.retry, enabled = state.canRetry, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Повторить проверку") }
                TextButton(onClick = actions.close, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Закрыть") }
            }
        }
    }
}

@Composable
private fun UpdateVersionCard(state: UpdateGateUi) {
    var notesOpen by remember(state.release?.versionName) { mutableStateOf(false) }
    SpectrumCard(Modifier.fillMaxWidth(), emphasized = true) {
        Text("Установлена версия ${state.installedVersion}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        state.release?.let { Text("Новая версия ${it.versionName}", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold) }
        if (state.checking && !state.busy) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
                Text("Проверяем актуальность версии…", style = MaterialTheme.typography.bodySmall)
            }
        }
        if (state.busy) {
            Text("Загрузка и проверка · ${state.progressPercent}%")
            LinearProgressIndicator(progress = { state.progressPercent.coerceIn(0, 100) / 100f }, modifier = Modifier.fillMaxWidth())
        }
        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        state.installationStatus?.let { Text(it) }
        val notes = state.release?.notes?.takeIf(String::isNotBlank)
        if (notes != null) {
            TextButton(onClick = { notesOpen = !notesOpen }, modifier = Modifier.heightIn(min = 48.dp)) { Text(if (notesOpen) "Скрыть изменения" else "Что нового") }
            if (notesOpen) Text(notes, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
private fun UpdateProcessLegend() {
    val steps = listOf(SpectrumSymbol.Update to "Загрузка", SpectrumSymbol.Risk to "Проверка", SpectrumSymbol.Settings to "Установка", SpectrumSymbol.Analyst to "Запуск")
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Как проходит обновление", style = MaterialTheme.typography.titleMedium)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            steps.forEach { (symbol, title) ->
                Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    SpectrumIcon(symbol, Modifier.size(42.dp))
                    Text(title, style = MaterialTheme.typography.labelMedium, textAlign = TextAlign.Center,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}
