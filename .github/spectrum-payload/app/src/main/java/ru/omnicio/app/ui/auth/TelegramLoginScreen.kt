package ru.omnicio.app.ui.auth

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.*

/** Presentation only. The existing Telegram callback and encrypted session flow are unchanged. */
@Composable
fun TelegramLoginScreen(loading: Boolean, errorMessage: String?, onLoginClick: () -> Unit, modifier: Modifier = Modifier) {
    SpectrumBackground(modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().safeDrawingPadding().verticalScroll(rememberScrollState()).padding(horizontal = 24.dp, vertical = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
            SpectrumBrain(Modifier.size(100.dp))
            Text("Analyst AI", style = MaterialTheme.typography.displayMedium, fontWeight = FontWeight.Bold)
            Text("Умные инвестиции\nдля каждого", textAlign = TextAlign.Center,
                color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.titleMedium)
            SpectrumGlobe(Modifier.fillMaxWidth().height(180.dp))
            SpectrumCard(Modifier.fillMaxWidth(), emphasized = true) {
                Text("Ваш личный аналитик", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text("Портфель, рекомендации и риски — простым языком, на основе ваших данных.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                SpectrumButton(onClick = onLoginClick, enabled = !loading, modifier = Modifier.fillMaxWidth()) {
                    if (loading) {
                        CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
                        Spacer(Modifier.width(10.dp))
                        Text("Подтверждаем вход…")
                    } else Text("Войти через Telegram", fontWeight = FontWeight.Bold)
                }
                Text("Подтвердите вход в Telegram. Пароль Telegram приложению не передаётся.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
            }
            Text("Analyst AI не совершает сделки за вас.", color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodySmall, textAlign = TextAlign.Center)
        }
    }
}
