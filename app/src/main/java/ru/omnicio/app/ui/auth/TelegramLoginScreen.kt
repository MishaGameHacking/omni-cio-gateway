package ru.omnicio.app.ui.auth

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.spatial.SpatialIcon
import ru.omnicio.app.ui.spatial.SpatialState
import ru.omnicio.app.ui.theme.LocalSpectrumMotionPreference

@Composable
fun TelegramLoginScreen(loading: Boolean, errorMessage: String?, onLoginClick: () -> Unit,
    modifier: Modifier = Modifier, loadingLabel: String = "Проверяем сохранённый сеанс…") {
    SpectrumBackground(modifier.fillMaxSize()) {
        Scaffold(containerColor = Color.Transparent, contentWindowInsets = WindowInsets.safeDrawing) { padding ->
            Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)
                .verticalScroll(rememberScrollState()).padding(horizontal = 24.dp, vertical = 28.dp),
                verticalArrangement = Arrangement.spacedBy(20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Text("Analyst AI", style = MaterialTheme.typography.titleMedium, color = LocalSpectrumPalette.current.cyan)
                SpatialIcon(if (errorMessage != null) "error" else "profile", Modifier.size(164.dp),
                    state = when { loading -> SpatialState.Loading; errorMessage != null -> SpatialState.Attention; else -> SpatialState.Idle },
                    motionAllowed = LocalSpectrumMotionPreference.current.enabled,
                    description = if (loading) loadingLabel else if (errorMessage != null) "Вход требует внимания" else "Вход через Telegram")
                Text("Капитал.\nПод вашим контролем.", style = MaterialTheme.typography.headlineLarge,
                    fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
                Text("Портфель, решения и спокойный взгляд вперёд.", textAlign = TextAlign.Center,
                    style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                SpectrumCard(emphasized = true) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        SpatialIcon("messages", Modifier.size(32.dp), state = if (loading) SpatialState.Loading else SpatialState.Selected)
                        Text("1. Вход через Telegram", style = MaterialTheme.typography.labelMedium)
                    }
                    Text("После входа: подключение счёта и первая загрузка портфеля.", style = MaterialTheme.typography.bodySmall)
                    Text("Войти в своё пространство", style = MaterialTheme.typography.titleLarge)
                    Text("Подтвердите вход через Telegram. Пароль остаётся в Telegram.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                    errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) }
                    if (loading) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            SpatialIcon("sources", Modifier.size(32.dp), state = SpatialState.Loading)
                            Text(loadingLabel, Modifier.weight(1f).semantics { liveRegion = LiveRegionMode.Polite })
                        }
                    } else SpectrumPrimaryButton("Войти через Telegram", onLoginClick, Modifier.fillMaxWidth(), symbol = SpectrumSymbol.Messages)
                }
                Text("Личное приложение для приглашённых пользователей", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
            }
        }
    }
}
