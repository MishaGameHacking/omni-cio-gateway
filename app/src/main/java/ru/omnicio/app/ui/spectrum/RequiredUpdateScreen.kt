package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.updates.ReleaseDecision
import ru.omnicio.app.ui.theme.LocalSpectrumMotionPreference
import ru.omnicio.app.ui.updates.UpdateGateActions
import ru.omnicio.app.ui.updates.UpdateGateUi

/** Spectrum renders the shared gate; it cannot download, install, or unblock content. */
@Composable
fun RequiredUpdateScreen(state: UpdateGateUi, actions: UpdateGateActions) {
    val motion = LocalSpectrumMotionPreference.current
    SpectrumBackground(Modifier.fillMaxSize()) {
        LazyColumn(
            modifier = Modifier.fillMaxSize().safeDrawingPadding(),
            contentPadding = PaddingValues(horizontal = 20.dp, vertical = 28.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            item {
                SpectrumIcon(SpectrumSymbol.Update, Modifier.size(112.dp), selected = true,
                    tile = true, motionAllowed = motion.enabled)
            }
            item { Text(state.title, style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold) }
            item {
                SpectrumCard(emphasized = true) {
                    Text(state.explanation, style = MaterialTheme.typography.bodyLarge)
                    Text("Установлено: ${state.installedVersion}", style = MaterialTheme.typography.bodyLarge)
                    state.release?.let { Text("Новая версия: ${it.versionName}", style = MaterialTheme.typography.bodyLarge) }
                    state.release?.notes?.takeIf(String::isNotBlank)?.let { Text(it, style = MaterialTheme.typography.bodyLarge) }
                    if (state.checking && !state.busy) {
                        CircularProgressIndicator(Modifier.size(24.dp), strokeWidth = 2.dp)
                        Text("Проверяем доступность актуальной версии.")
                    }
                    if (state.busy) {
                        Text("Скачивание и проверка: ${state.progressPercent}%")
                        LinearProgressIndicator(progress = { state.progressPercent / 100f }, modifier = Modifier.fillMaxWidth())
                    }
                    state.error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyLarge) }
                    state.installationStatus?.let { Text(it, style = MaterialTheme.typography.bodyLarge) }
                }
            }
            if (state.decision == ReleaseDecision.UPDATE_REQUIRED) {
                item {
                    Button(onClick = actions.update, enabled = state.canUpdate,
                        modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Обновить приложение") }
                }
            }
            item {
                Text("APK загружается с московского сервера Analyst AI. Перед установкой проверяются размер, контрольная сумма, приложение, версия и подпись.",
                    style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            item {
                Text("Android может попросить разрешение на установку и открыть системное подтверждение. После установки при необходимости нажмите «Открыть».",
                    style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            item { TextButton(onClick = actions.retry, enabled = state.canRetry, modifier = Modifier.heightIn(min = 48.dp)) { Text("Повторить проверку") } }
            item { TextButton(onClick = actions.close, modifier = Modifier.heightIn(min = 48.dp)) { Text("Закрыть") } }
        }
    }
}
