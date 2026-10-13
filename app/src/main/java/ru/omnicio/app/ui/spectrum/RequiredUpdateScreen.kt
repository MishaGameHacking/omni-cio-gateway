package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Button
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.updates.UpdateFlow
import ru.omnicio.app.data.updates.UpdateStage

/** UI component only. Root routing and the authenticated server must enforce policy.
 * This cannot turn a legacy APK into an updater, download or silently install a file.
 */
@Composable
fun RequiredUpdateScreen(
    state: UpdateFlow,
    versionLabel: String,
    onUpdate: () -> Unit,
    onHelp: () -> Unit,
    onSignOut: () -> Unit,
) {
    val stage = state.stage
    Scaffold { insets ->
        LazyColumn(modifier = Modifier.fillMaxSize().padding(insets),
            contentPadding = PaddingValues(24.dp), verticalArrangement = Arrangement.spacedBy(22.dp),
            horizontalAlignment = Alignment.CenterHorizontally) {
            item { SpectrumIcon(SpectrumSymbol.Update, Modifier.size(112.dp), selected = true) }
            item { Text("Обновите Analyst AI", style = MaterialTheme.typography.headlineLarge) }
            item { Text("Для продолжения нужна версия $versionLabel. Ваши счета и настройки сохранятся.",
                style = MaterialTheme.typography.bodyLarge) }
            item {
                val message = when (stage) {
                    UpdateStage.Checking -> "Проверяем версию приложения."
                    UpdateStage.Required -> "Файл будет получен с нашего российского сервера."
                    is UpdateStage.Downloading -> "Скачиваем обновление."
                    UpdateStage.Verifying -> "Проверяем подпись и целостность APK."
                    UpdateStage.AwaitingInstaller, UpdateStage.AwaitingUser -> "Продолжите в системном установщике Android."
                    UpdateStage.VerifyInstalledVersion -> "Проверяем установленную версию."
                    UpdateStage.Current -> "Приложение обновлено."
                    is UpdateStage.Failed -> stage.message
                }
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(message)
                    if (stage is UpdateStage.Downloading && stage.total > 0) {
                        LinearProgressIndicator(progress = { stage.received.toFloat() / stage.total.toFloat() },
                            modifier = Modifier.fillMaxWidth())
                    }
                }
            }
            item {
                Button(onClick = onUpdate, modifier = Modifier.fillMaxWidth(),
                    enabled = stage == UpdateStage.Required || stage is UpdateStage.Failed) {
                    Text(if (stage is UpdateStage.Failed) "Повторить" else "Обновить приложение")
                }
            }
            item { Text("Android может запросить разрешение на установку. Отмена не удаляет ваши данные.",
                color = MaterialTheme.colorScheme.onSurfaceVariant) }
            item { TextButton(onClick = onHelp) { Text("Помощь с обновлением") } }
            item { TextButton(onClick = onSignOut) { Text("Выйти из аккаунта") } }
        }
    }
}
