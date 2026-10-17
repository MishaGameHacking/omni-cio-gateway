package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.*
import androidx.compose.ui.unit.dp
import java.time.Duration
import java.time.Instant
import ru.omnicio.app.data.portfolio.PortfolioCurrency
import ru.omnicio.app.ui.spectrum.*

val LocalCurrencyChoice = staticCompositionLocalOf<(PortfolioCurrency) -> Unit> { {} }
val LocalPortfolioDestination = staticCompositionLocalOf<(PortfolioDestination) -> Unit> { {} }
data class PortfolioDestination(val section: Int = 1, val accountId: String? = null,
    val query: String = "", val sector: String? = null, val kind: String? = null)

val workspaceGap: androidx.compose.ui.unit.Dp
    @Composable get() = if (LocalWorkspacePreferences.current.value.density == InterfaceDensity.COMPACT) 8.dp else 14.dp

@Composable
fun PrivateValue(value: String): String = if (LocalWorkspacePreferences.current.value.hideHomeBalance) "•••" else value

@Composable
fun BalanceVisibilityButton() {
    val prefs = LocalWorkspacePreferences.current
    TextButton(onClick = { prefs.update(prefs.value.copy(hideHomeBalance = !prefs.value.hideHomeBalance)) },
        modifier = Modifier.heightIn(min = 48.dp)) {
        Text(if (prefs.value.hideHomeBalance) "Показать суммы" else "Скрыть суммы")
    }
}

@Composable
fun CurrencyChoice(currency: String) {
    var open by rememberSaveable { mutableStateOf(false) }
    val select = LocalCurrencyChoice.current
    TextButton(onClick = { open = true }, modifier = Modifier.heightIn(min = 48.dp)) { Text("$currency ▾") }
    if (open) AlertDialog(onDismissRequest = { open = false }, title = { Text("Валюта оценки") },
        text = { Column { PortfolioCurrency.entries.forEach { choice ->
            TextButton(onClick = { select(choice); open = false }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                Text(if (choice.name == currency) "${choice.name} · выбрана" else choice.name)
            }
        } } }, confirmButton = { TextButton(onClick = { open = false }) { Text("Закрыть") } })
}

@Composable
fun DetailFold(title: String, modifier: Modifier = Modifier, initiallyOpen: Boolean = false,
    content: @Composable ColumnScope.() -> Unit) {
    var expanded by rememberSaveable(title) { mutableStateOf(initiallyOpen) }
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        TextButton(onClick = { expanded = !expanded }, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)
            .semantics { stateDescription = if (expanded) "Развёрнуто" else "Свёрнуто" }) {
            Text(title, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
            Text(if (expanded) "−" else "+")
        }
        if (expanded) content()
    }
}

@Composable
fun WorkspaceEmpty(title: String, detail: String, action: String? = null, onAction: () -> Unit = {}, loading: Boolean = false) {
    SpectrumCard {
        Text(title, style = MaterialTheme.typography.titleLarge)
        Text(detail, color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
        if (loading) LinearProgressIndicator(Modifier.fillMaxWidth())
        if (action != null) SpectrumSecondaryButton(action, onAction, Modifier.fillMaxWidth())
    }
}

@Composable
fun WorkspaceHeader(title: String, subtitle: String, onBack: () -> Unit, symbol: SpectrumSymbol? = null) {
    Row(Modifier.fillMaxWidth().windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Top + WindowInsetsSides.Horizontal))
        .padding(horizontal = 12.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        TextButton(onClick = onBack, modifier = Modifier.heightIn(min = 48.dp)) { Text("‹ Назад") }
        if (symbol != null) SpectrumIcon(symbol, Modifier.size(24.dp), motionAllowed = false)
        Column(Modifier.weight(1f).padding(horizontal = 8.dp)) {
            Text(title, style = MaterialTheme.typography.titleLarge)
            if (subtitle.isNotBlank()) Text(subtitle, style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

internal fun relativeObservation(raw: String?, now: Instant = Instant.now()): String {
    val instant = runCatching { Instant.parse(raw) }.getOrNull() ?: return "время не получено"
    val minutes = Duration.between(instant, now).toMinutes()
    return when {
        minutes < 0 -> "время требует проверки"
        minutes == 0L -> "только что"
        minutes < 60 -> "$minutes мин назад"
        minutes < 1440 -> "${minutes / 60} ч назад"
        else -> "${minutes / 1440} дн назад"
    }
}

/** Unknown and failed checks never masquerade as disconnected accounts. */
enum class BrokerConnectionState(val title: String) {
    Checking("Проверяем подключение"), Connected("Подключено"), Missing("Не подключено"), Unknown("Статус не получен")
}
val LocalBrokerConnection = staticCompositionLocalOf<BrokerConnectionState?> { null }
