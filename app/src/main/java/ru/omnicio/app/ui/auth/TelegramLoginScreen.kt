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
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.*

@Composable
fun TelegramLoginScreen(loading: Boolean, errorMessage: String?, onLoginClick: () -> Unit,
    modifier: Modifier = Modifier) {
    SpectrumBackground(modifier.fillMaxSize()) {
        Scaffold(containerColor = Color.Transparent, contentWindowInsets = WindowInsets.safeDrawing) { padding ->
            Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)
                .verticalScroll(rememberScrollState()).padding(horizontal = 24.dp, vertical = 28.dp),
                verticalArrangement = Arrangement.spacedBy(20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Text("Analyst AI", style = MaterialTheme.typography.titleMedium, color = LocalSpectrumPalette.current.cyan)
                SpectrumCapitalOrbit(Modifier.size(184.dp))
                Text("Капитал.\nПод вашим контролем.", style = MaterialTheme.typography.headlineLarge,
                    fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
                Text("Портфель, решения и спокойный взгляд вперёд.", textAlign = TextAlign.Center,
                    style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
                SpectrumCard(emphasized = true) {
                    Text("Войти в своё пространство", style = MaterialTheme.typography.titleLarge)
                    Text("Подтвердите вход через Telegram. Пароль остаётся в Telegram.",
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                    errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                    if (loading) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            CircularProgressIndicator(Modifier.size(24.dp), strokeWidth = 2.dp)
                            Text("Проверяем сохранённый сеанс…", Modifier.weight(1f))
                        }
                    } else SpectrumPrimaryButton("Войти через Telegram", onLoginClick, Modifier.fillMaxWidth(), symbol = SpectrumSymbol.Messages)
                }
                Text("Личное приложение для приглашённых пользователей", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
            }
        }
    }
}
