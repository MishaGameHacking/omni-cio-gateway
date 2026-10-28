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
import ru.omnicio.app.ui.spatial.SpatialIcon
import ru.omnicio.app.ui.spatial.SpatialState
import ru.omnicio.app.ui.AnalystMenuButton

val LocalCurrencyChoice = staticCompositionLocalOf<(PortfolioCurrency) -> Unit> { {} }
val LocalPortfolioDestination = staticCompositionLocalOf<(PortfolioDestination) -> Unit> { {} }
data class PortfolioDestination(val section: Int = 1, val accountId: String? = null,
    val query: String = "", val sector: String? = null, val kind: String? = null,
    val operationId: String? = null, val operationDate: String? = null)

val workspaceGap: androidx.compose.ui.unit.Dp
    @Composable get() = if (LocalWorkspacePreferences.current.value.density == InterfaceDensity.COMPACT) 8.dp else 12.dp

@Composable
fun PrivateValue(value: String): String = if (LocalWorkspacePreferences.current.value.hideHomeBalance) "•••" else value

@Composable
fun BalanceVisibilityButton() {
    val prefs = LocalWorkspacePreferences.current
    SpectrumTextButton(if (prefs.value.hideHomeBalance) "Показать суммы" else "Скрыть суммы",
        onClick = { prefs.update(prefs.value.copy(hideHomeBalance = !prefs.value.hideHomeBalance)) },
        modifier = Modifier.semantics { stateDescription = if (prefs.value.hideHomeBalance) "Суммы скрыты" else "Суммы видны" },
        symbol = SpectrumSymbol.Profile)
}

@Composable
fun CurrencyChoice(currency: String) {
    var open by rememberSaveable { mutableStateOf(false) }
    val select = LocalCurrencyChoice.current
    SpectrumTextButton("Валюта: $currency", onClick = { open = true }, symbol = SpectrumSymbol.Currency)
    if (open) WorkspaceDialog("Валюта оценки", onDismiss = { open = false }) {
        Text("Выберите валюту оценки брокера.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        WorkspaceChoices("Валюта", PortfolioCurrency.entries.map { it.name },
            PortfolioCurrency.entries.indexOfFirst { it.name == currency }) { index ->
            select(PortfolioCurrency.entries[index]);open = false
        }
        SpectrumSecondaryButton("Закрыть", { open = false }, Modifier.fillMaxWidth())
    }
}

@Composable
fun DetailFold(title: String, modifier: Modifier = Modifier, initiallyOpen: Boolean = false,
    headerModifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit) {
    var expanded by rememberSaveable(title) { mutableStateOf(initiallyOpen) }
    Column(modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SpectrumTextButton(title, onClick = { expanded = !expanded },
            modifier = Modifier.fillMaxWidth().then(headerModifier).semantics { stateDescription = if (expanded) "Развёрнуто" else "Свёрнуто" },
            symbol = if (expanded) SpectrumSymbol.ChevronUp else SpectrumSymbol.ChevronDown)
        if (expanded) content()
    }
}

@Composable
fun WorkspaceEmpty(title: String, detail: String, action: String? = null, onAction: () -> Unit = {}, loading: Boolean = false) {
    SpectrumCard {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
            if (loading) SpectrumLoadingIndicator(Modifier.size(40.dp), title)
            else SpatialIcon("sources", Modifier.size(40.dp), state = SpatialState.Idle)
            Text(title, Modifier.weight(1f), style = MaterialTheme.typography.titleLarge)
        }
        Text(detail, color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
        if (action != null) SpectrumSecondaryButton(action, onAction, Modifier.fillMaxWidth())
    }
}

/** Keep the full page context in the scrollable body when the header yields space. */
@Composable
internal fun WorkspacePageHeading(title: String, subtitle: String) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(title, Modifier.semantics { heading() }, style = MaterialTheme.typography.titleLarge)
        if (subtitle.isNotBlank()) Text(subtitle, style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
fun WorkspaceHeader(title: String, subtitle: String, onBack: () -> Unit, symbol: SpectrumSymbol? = null,
    onOpenMenu: (() -> Unit)? = null) {
    Column(Modifier.fillMaxWidth().windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Top + WindowInsetsSides.Horizontal))
        .padding(horizontal = 12.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            SpectrumIconButton(SpectrumSymbol.Back, "Назад", onBack)
            Text(title, Modifier.weight(1f).semantics { heading() }, style = MaterialTheme.typography.titleLarge)
            if (symbol != null) SpectrumIcon(symbol, Modifier.size(32.dp), motionAllowed = false)
        }
        if (subtitle.isNotBlank()) Text(subtitle, Modifier.padding(start = 56.dp, end = 8.dp),
            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
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

