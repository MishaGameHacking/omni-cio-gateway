package ru.omnicio.app.ui.auth

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spatial.SpatialIcon
import ru.omnicio.app.ui.spatial.SpatialState
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.theme.LocalSpectrumMotionPreference

@Composable
fun TelegramLoginScreen(loading: Boolean, errorMessage: String?, onLoginClick: () -> Unit,
    modifier: Modifier = Modifier, loadingLabel: String = "Проверяем сохранённый сеанс…") {
    SpectrumBackground(modifier.fillMaxSize()) {
        Scaffold(containerColor = Color.Transparent, contentWindowInsets = WindowInsets.safeDrawing) { padding ->
            Column(
                Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)
                    .verticalScroll(rememberScrollState()).padding(horizontal = 24.dp, vertical = 32.dp),
                verticalArrangement = Arrangement.spacedBy(20.dp),
                horizontalAlignment = Alignment.Start,
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    SpatialIcon("brain", Modifier.size(56.dp),
                        tint = MaterialTheme.colorScheme.primary, motionAllowed = true)
                    Text("Analyst AI", style = MaterialTheme.typography.titleLarge,
                        color = MaterialTheme.colorScheme.primary)
                }
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("Ваш портфель.\nЯсная картина.", style = MaterialTheme.typography.headlineLarge,
                        modifier = Modifier.semantics { heading() })
                    Text("Стоимость, выплаты и аналитика на основе данных вашего счёта Т-Инвестиций.",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    listOf(SpectrumSymbol.Portfolio to "Активы", SpectrumSymbol.Capital to "Риски",
                        SpectrumSymbol.Growth to "Стратегия").forEach { (symbol, label) ->
                        Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            SpectrumIcon(symbol, Modifier.size(56.dp), motionAllowed = false)
                            Text(label, style = MaterialTheme.typography.labelMedium)
                        }
                    }
                }
                SpectrumCard {
                    errorMessage?.let {
                        Text(it, color = MaterialTheme.colorScheme.error,
                            modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
                    }
                    if (loading) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(12.dp),
                        ) {
                            SpatialIcon("sources", Modifier.size(28.dp), state = SpatialState.Loading,
                                tint = MaterialTheme.colorScheme.primary,
                                motionAllowed = LocalSpectrumMotionPreference.current.enabled)
                            Text(loadingLabel, Modifier.weight(1f).semantics {
                                liveRegion = LiveRegionMode.Polite
                            })
                        }
                    } else {
                        SpectrumPrimaryButton("Войти через Telegram", onLoginClick, Modifier.fillMaxWidth())
                        Text("Подтвердите вход в Telegram. Токен брокера подключается отдельно после входа.",
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

