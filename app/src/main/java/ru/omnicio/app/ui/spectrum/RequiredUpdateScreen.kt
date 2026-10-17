package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
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
fun RequiredUpdateScreen(
    state: UpdateGateUi,
    actions: UpdateGateActions,
    extraContent: @Composable () -> Unit = {},
) {
    var details by rememberSaveable { mutableStateOf(false) }
    val motion = LocalSpectrumMotionPreference.current
    val updateRequired = state.decision == ReleaseDecision.UPDATE_REQUIRED
    SpectrumUpdateBackdrop(
        motionAllowed = motion.enabled,
        modifier = Modifier.fillMaxSize(),
    ) {
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .safeDrawingPadding(),
            contentPadding = PaddingValues(horizontal = 20.dp, vertical = 28.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            item(key = "update-alert") {
                SpectrumUpdateAlert(
                    updateRequired = updateRequired,
                    motionAllowed = motion.enabled,
                    modifier = Modifier.size(148.dp),
                )
            }
            item(key = "update-title") {
                Text(
                    text = state.title,
                    style = MaterialTheme.typography.headlineLarge,
                    fontWeight = FontWeight.Bold,
                )
            }
            item(key = "update-details") {
                SpectrumCard(emphasized = true) {
                    Text(state.explanation, style = MaterialTheme.typography.bodyLarge)
                    Text(
                        "Установлено: ${state.installedVersion}",
                        style = MaterialTheme.typography.bodyLarge,
                    )
                    state.release?.let {
                        Text(
                            "Новая версия: ${it.versionName}",
                            style = MaterialTheme.typography.bodyLarge,
                        )
                    }
                    state.release?.notes
                        ?.takeIf(String::isNotBlank)
                        ?.let { Text(it, style = MaterialTheme.typography.bodyLarge) }

                    if (state.checking && !state.busy) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(12.dp),
                        ) {
                            SpectrumLoadingIndicator(Modifier.size(28.dp), "Проверка актуальной версии")
                            Text(
                                "Проверяем доступность актуальной версии.",
                                modifier = Modifier.weight(1f),
                            )
                        }
                    }
                    if (state.busy) {
                        Text("Скачивание и проверка: ${state.progressPercent}%")
                        SpectrumProgressBar(
                            fraction = state.progressPercent / 100f,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                    state.error?.let {
                        Text(
                            it,
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodyLarge,
                        )
                    }
                    state.installationStatus?.let {
                        Text(it, style = MaterialTheme.typography.bodyLarge)
                    }
                }
            }
            item(key = "update-read-only-access") { extraContent() }
            if (updateRequired) {
                item(key = "update-action") {
                    SpectrumPrimaryButton(
                        text = "Обновить приложение",
                        onClick = actions.update,
                        enabled = state.canUpdate,
                        symbol = SpectrumSymbol.Update,
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 54.dp),
                    )
                }
            }
            item(key = "update-process-toggle") {
                SpectrumSecondaryButton(if (details) "Скрыть подробности" else "Как проходит обновление",
                    onClick = { details = !details }, modifier = Modifier.heightIn(min = 48.dp))
            }
            if (details) item(key = "update-process") { UpdateProcessSummary() }
            if (details) item(key = "update-source") {
                Text(
                    "APK загружается с московского сервера Analyst AI. Перед установкой проверяются размер, контрольная сумма, приложение, версия и подпись.",
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            item(key = "update-android-confirmation") {
                Text(
                    "Подтвердите установку в окне Android. После обновления нажмите «Открыть».",
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            item(key = "update-retry") {
                SpectrumSecondaryButton(
                    text = "Повторить проверку",
                    onClick = actions.retry,
                    enabled = state.canRetry,
                    modifier = Modifier.heightIn(min = 48.dp),
                )
            }
            item(key = "update-close") {
                SpectrumSecondaryButton(
                    text = "Закрыть",
                    onClick = actions.close,
                    modifier = Modifier.heightIn(min = 48.dp),
                )
            }
        }
    }
}

@Composable
private fun UpdateProcessSummary() {
    SpectrumCard {
        Text(
            "Как проходит обновление",
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
        )
        UpdateProcessStep("1", "Скачивание", "Получаем APK только из канала Analyst AI.")
        UpdateProcessStep("2", "Проверка", "Сверяем размер, SHA-256, package, версию и подпись.")
        UpdateProcessStep("3", "Установка", "Передаём проверенный APK системному установщику Android.")
        UpdateProcessStep("4", "Запуск", "После установки открываем уже новую версию приложения.")
    }
}

@Composable
private fun UpdateProcessStep(number: String, title: String, explanation: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.Top,
    ) {
        SpectrumBadge(number, accent = LocalSpectrumPalette.current.cyan)
        Spacer(Modifier.width(12.dp))
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            Text(
                title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                explanation,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}


