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
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.updates.UpdateFlow
import ru.omnicio.app.data.updates.UpdateStage

@Composable
fun RequiredUpdateScreen(
    state: UpdateFlow,
    versionLabel: String,
    onUpdate: () -> Unit,
    onHelp: () -> Unit,
    onSignOut: () -> Unit,
) {
    val stage = state.stage
    SpectrumBackground(Modifier.fillMaxSize()) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(horizontal = 24.dp, vertical = 36.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            item {
                SpectrumIcon(
                    symbol = SpectrumSymbol.Update,
                    modifier = Modifier.size(112.dp),
                    selected = true,
                    tile = true,
                    motionAllowed = true,
                )
            }
            item {
                Text(
                    text = "Требуется обновление",
                    style = MaterialTheme.typography.headlineLarge,
                    fontWeight = FontWeight.Bold,
                )
            }
            item {
                SpectrumCard(emphasized = true) {
                    Text(
                        text = "Для продолжения нужна версия $versionLabel. Портфель, вход и настройки сохранятся.",
                        style = MaterialTheme.typography.bodyLarge,
                    )
                    Column(
                        modifier = Modifier.padding(top = 14.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Text(stageMessage(stage))
                        if (stage is UpdateStage.Downloading && stage.total > 0L) {
                            LinearProgressIndicator(
                                progress = { stage.received.toFloat() / stage.total.toFloat() },
                                modifier = Modifier.fillMaxWidth(),
                            )
                            Text(
                                text = "${stage.received / 1_048_576} из ${stage.total / 1_048_576} МБ",
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                }
            }
            item {
                Button(
                    onClick = onUpdate,
                    modifier = Modifier.fillMaxWidth(),
                    enabled = stage == UpdateStage.Required || stage is UpdateStage.Failed,
                ) {
                    Text(if (stage is UpdateStage.Failed) "Повторить обновление" else "Обновить приложение")
                }
            }
            item {
                Text(
                    text = "APK загружается только с московского сервера Analyst AI. Перед установкой проверяются размер, SHA‑256, package, versionCode и сертификат подписи.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            item {
                Text(
                    text = "Android может открыть системное окно подтверждения. Это штатная защита устройства — приложение не пытается её обходить.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            item { TextButton(onClick = onHelp) { Text("Помощь с обновлением") } }
            item { TextButton(onClick = onSignOut) { Text("Выйти из аккаунта") } }
        }
    }
}

private fun stageMessage(stage: UpdateStage): String = when (stage) {
    UpdateStage.Checking -> "Проверяем версию приложения."
    UpdateStage.Required -> "Новая версия готова к безопасной загрузке."
    is UpdateStage.UnsupportedVersion ->
        "На устройстве установлена более новая неизвестная версия (${stage.installedCode}). Понижение версии запрещено."
    is UpdateStage.Downloading -> "Скачиваем APK с сервера Analyst AI."
    UpdateStage.Verifying -> "Проверяем подпись и целостность APK."
    UpdateStage.AwaitingInstaller -> "Передаём проверенный APK системному установщику Android."
    UpdateStage.AwaitingUser -> "Подтвердите установку в системном окне Android."
    UpdateStage.VerifyInstalledVersion -> "Проверяем установленную версию."
    UpdateStage.Current -> "Приложение обновлено."
    is UpdateStage.Failed -> stage.message
}
