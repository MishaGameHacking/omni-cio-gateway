package ru.omnicio.app.ui.home

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import ru.omnicio.app.data.backend.AnalystUser
import ru.omnicio.app.data.portfolio.PortfolioAllocation
import ru.omnicio.app.data.portfolio.PortfolioCurrency
import ru.omnicio.app.data.portfolio.PortfolioSnapshot
import ru.omnicio.app.data.portfolio.PortfolioUiState
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.portfolio.moneyText
import ru.omnicio.app.ui.portfolio.percentText
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette
import ru.omnicio.app.ui.spectrum.SpectrumActionTile
import ru.omnicio.app.ui.spectrum.SpectrumBackground
import ru.omnicio.app.ui.spectrum.SpectrumBadge
import ru.omnicio.app.ui.spectrum.SpectrumBrandOrb
import ru.omnicio.app.ui.spectrum.SpectrumCard
import ru.omnicio.app.ui.spectrum.SpectrumIcon
import ru.omnicio.app.ui.spectrum.SpectrumMetricPill
import ru.omnicio.app.ui.spectrum.SpectrumPrimaryButton
import ru.omnicio.app.ui.spectrum.SpectrumProgressBar
import ru.omnicio.app.ui.spectrum.SpectrumSecondaryButton
import ru.omnicio.app.ui.spectrum.SpectrumSymbol

@Composable
fun HomeScreen(
    user: AnalystUser,
    state: PortfolioUiState,
    selectedCurrency: PortfolioCurrency,
    refreshing: Boolean,
    refreshError: String?,
    lastUpdatedMillis: Long?,
    onCurrencyClick: () -> Unit,
    onOpenPortfolio: () -> Unit,
    onOpenRecommendations: () -> Unit,
    onOpenRisk: () -> Unit,
    onOpenMessages: () -> Unit,
    onOpenEducation: () -> Unit,
    onOpenProfile: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val snapshot = (state as? PortfolioUiState.Ready)?.snapshot
    SpectrumBackground(modifier.fillMaxSize()) {
        Scaffold(
            modifier = Modifier.fillMaxSize(),
            containerColor = Color.Transparent,
            contentWindowInsets = WindowInsets.safeDrawing,
            bottomBar = {
                AnalystBottomBar(
                    selected = AnalystTab.Home,
                    onPortfolioClick = onOpenPortfolio,
                    onProfileClick = onOpenProfile,
                )
            },
        ) { insets ->
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(insets).consumeWindowInsets(insets),
                contentPadding = PaddingValues(horizontal = 20.dp, vertical = 18.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                item(key = "brand-header") {
                    HomeHeader(user = user, onMessagesClick = onOpenMessages)
                }
                item(key = "portfolio-hero") {
                    PortfolioHero(
                        state = state,
                        snapshot = snapshot,
                        selectedCurrency = selectedCurrency,
                        refreshing = refreshing,
                        refreshError = refreshError,
                        lastUpdatedMillis = lastUpdatedMillis,
                        onCurrencyClick = onCurrencyClick,
                        onOpenPortfolio = onOpenPortfolio,
                        onOpenProfile = onOpenProfile,
                    )
                }
                item(key = "capabilities-title") {
                    SectionTitle(
                        title = "Возможности Analyst AI",
                        subtitle = "Основные задачи собраны на одном экране",
                    )
                }
                item(key = "capabilities") {
                    QuickActions(
                        onOpenPortfolio = onOpenPortfolio,
                        onOpenRecommendations = onOpenRecommendations,
                        onOpenRisk = onOpenRisk,
                        onOpenMessages = onOpenMessages,
                        onOpenEducation = onOpenEducation,
                    )
                }
                item(key = "assistant") {
                    AnalystSummaryCard(
                        snapshot = snapshot,
                        refreshError = refreshError,
                        onOpenRecommendations = onOpenRecommendations,
                    )
                }
                if (snapshot != null) {
                    item(key = "allocation") {
                        AllocationOverview(snapshot = snapshot, onOpenPortfolio = onOpenPortfolio)
                    }
                }
                item(key = "guardrail") { DecisionGuardrail() }
            }
        }
    }
}

@Composable
private fun HomeHeader(user: AnalystUser, onMessagesClick: () -> Unit) {
    val palette = LocalSpectrumPalette.current
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        SpectrumBrandOrb(Modifier.size(54.dp), compact = true)
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text("Analyst AI", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text(
                greeting(user),
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodySmall,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        Surface(
            onClick = onMessagesClick,
            modifier = Modifier.size(52.dp),
            shape = androidx.compose.foundation.shape.RoundedCornerShape(18.dp),
            color = palette.cardStrong.copy(alpha = 0.78f),
            border = BorderStroke(1.dp, palette.violet.copy(alpha = 0.38f)),
        ) {
            SpectrumIcon(
                symbol = SpectrumSymbol.Notifications,
                modifier = Modifier.padding(11.dp),
                selected = true,
                tile = false,
                motionAllowed = false,
            )
        }
    }
}

@Composable
private fun PortfolioHero(
    state: PortfolioUiState,
    snapshot: PortfolioSnapshot?,
    selectedCurrency: PortfolioCurrency,
    refreshing: Boolean,
    refreshError: String?,
    lastUpdatedMillis: Long?,
    onCurrencyClick: () -> Unit,
    onOpenPortfolio: () -> Unit,
    onOpenProfile: () -> Unit,
) {
    val palette = LocalSpectrumPalette.current
    SpectrumCard(emphasized = true) {
        BoxWithConstraints(Modifier.fillMaxWidth()) {
            if (maxWidth < 340.dp) {
                Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    HeroCopy(
                        state = state,
                        snapshot = snapshot,
                        selectedCurrency = selectedCurrency,
                        refreshing = refreshing,
                        refreshError = refreshError,
                        lastUpdatedMillis = lastUpdatedMillis,
                        onCurrencyClick = onCurrencyClick,
                    )
                    SpectrumBrandOrb(Modifier.fillMaxWidth().heightIn(max = 150.dp))
                }
            } else {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    HeroCopy(
                        state = state,
                        snapshot = snapshot,
                        selectedCurrency = selectedCurrency,
                        refreshing = refreshing,
                        refreshError = refreshError,
                        lastUpdatedMillis = lastUpdatedMillis,
                        onCurrencyClick = onCurrencyClick,
                        modifier = Modifier.weight(1f),
                    )
                    SpectrumBrandOrb(Modifier.size(118.dp))
                }
            }
        }
        if (snapshot != null) {
            Metrics(snapshot)
            SpectrumPrimaryButton(
                text = "Открыть мой портфель",
                onClick = onOpenPortfolio,
                modifier = Modifier.fillMaxWidth(),
                symbol = SpectrumSymbol.Portfolio,
            )
        } else {
            SpectrumPrimaryButton(
                text = if (state == PortfolioUiState.NotConnected) "Подключить T‑API" else "Открыть профиль",
                onClick = onOpenProfile,
                modifier = Modifier.fillMaxWidth(),
                symbol = SpectrumSymbol.Profile,
            )
        }
        when {
            refreshError != null -> SpectrumBadge("Обновление не завершено", accent = MaterialTheme.colorScheme.error)
            refreshing -> SpectrumBadge("Обновляем реальные данные", accent = palette.cyan)
        }
    }
}

@Composable
private fun HeroCopy(
    state: PortfolioUiState,
    snapshot: PortfolioSnapshot?,
    selectedCurrency: PortfolioCurrency,
    refreshing: Boolean,
    refreshError: String?,
    lastUpdatedMillis: Long?,
    onCurrencyClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SpectrumBadge(
            text = when {
                refreshing -> "Обновление"
                refreshError != null -> "Последние сохранённые данные"
                snapshot != null -> "Портфель подключён"
                state == PortfolioUiState.NotConnected -> "Нужно подключение"
                else -> "Подготовка данных"
            },
            accent = when {
                refreshError != null -> MaterialTheme.colorScheme.error
                snapshot != null -> LocalSpectrumPalette.current.emerald
                else -> LocalSpectrumPalette.current.cyan
            },
        )
        Text("Главная", style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold)
        Text(
            if (snapshot == null) stateText(state) else "Общий баланс",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            style = MaterialTheme.typography.bodyMedium,
        )
        if (snapshot != null) {
            Surface(
                modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)
                    .clickable(role = Role.Button, onClick = onCurrencyClick),
                color = Color.Transparent,
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(
                        snapshot.totalValue.moneyText(),
                        fontSize = 34.sp,
                        lineHeight = 38.sp,
                        fontWeight = FontWeight.Bold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        "Нажмите, чтобы сменить валюту · ${selectedCurrency.name}",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
            Text(
                "Доходность: ${snapshot.expectedYieldPercent.percentText()}",
                color = yieldColor(snapshot),
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                lastUpdatedText(snapshot, lastUpdatedMillis),
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
private fun Metrics(snapshot: PortfolioSnapshot) {
    val positions = snapshot.accounts.sumOf { it.positions.size + it.virtualPositions.size }
    val largest = snapshot.allocations.maxByOrNull { it.sharePercent.toBigDecimal() }
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        if (maxWidth < 330.dp) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                SpectrumMetricPill("Счета", snapshot.accounts.size.toString(), Modifier.fillMaxWidth())
                SpectrumMetricPill("Позиции", positions.toString(), Modifier.fillMaxWidth(), LocalSpectrumPalette.current.violet)
                largest?.let {
                    SpectrumMetricPill(
                        "Крупнейшая категория",
                        it.sharePercent.percentText(),
                        Modifier.fillMaxWidth(),
                        LocalSpectrumPalette.current.emerald,
                    )
                }
            }
        } else {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                SpectrumMetricPill("Счета", snapshot.accounts.size.toString(), Modifier.weight(1f))
                SpectrumMetricPill("Позиции", positions.toString(), Modifier.weight(1f), LocalSpectrumPalette.current.violet)
                largest?.let {
                    SpectrumMetricPill(
                        "Макс. доля",
                        it.sharePercent.percentText(),
                        Modifier.weight(1f),
                        LocalSpectrumPalette.current.emerald,
                    )
                }
            }
        }
    }
}

@Composable
private fun QuickActions(
    onOpenPortfolio: () -> Unit,
    onOpenRecommendations: () -> Unit,
    onOpenRisk: () -> Unit,
    onOpenMessages: () -> Unit,
    onOpenEducation: () -> Unit,
) {
    val palette = LocalSpectrumPalette.current
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        if (maxWidth < 350.dp) {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                SpectrumActionTile("Мой портфель", "Счета, позиции и структура", SpectrumSymbol.Portfolio, onOpenPortfolio, Modifier.fillMaxWidth(), palette.blue)
                SpectrumActionTile("Рекомендации", "Проверенные направления", SpectrumSymbol.Ideas, onOpenRecommendations, Modifier.fillMaxWidth(), palette.rose)
                SpectrumActionTile("Риски", "Сводка и предупреждения", SpectrumSymbol.Risk, onOpenRisk, Modifier.fillMaxWidth(), palette.emerald)
                SpectrumActionTile("Сообщения", "Важные выводы Analyst AI", SpectrumSymbol.Messages, onOpenMessages, Modifier.fillMaxWidth(), palette.violet)
                SpectrumActionTile("Обучение", "Инвестиции простыми словами", SpectrumSymbol.Education, onOpenEducation, Modifier.fillMaxWidth(), palette.cyan)
            }
        } else {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    SpectrumActionTile("Портфель", "Счета и позиции", SpectrumSymbol.Portfolio, onOpenPortfolio, Modifier.weight(1f), palette.blue)
                    SpectrumActionTile("Рекомендации", "Направления", SpectrumSymbol.Ideas, onOpenRecommendations, Modifier.weight(1f), palette.rose)
                }
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    SpectrumActionTile("Риски", "Сводка", SpectrumSymbol.Risk, onOpenRisk, Modifier.weight(1f), palette.emerald)
                    SpectrumActionTile("Сообщения", "Выводы", SpectrumSymbol.Messages, onOpenMessages, Modifier.weight(1f), palette.violet)
                }
                SpectrumActionTile("Обучение", "Пошаговые уроки и официальные источники", SpectrumSymbol.Education, onOpenEducation, Modifier.fillMaxWidth(), palette.cyan)
            }
        }
    }
}

@Composable
private fun AnalystSummaryCard(
    snapshot: PortfolioSnapshot?,
    refreshError: String?,
    onOpenRecommendations: () -> Unit,
) {
    val palette = LocalSpectrumPalette.current
    val summary = when {
        refreshError != null -> "Свежую загрузку завершить не удалось. Analyst AI сохраняет предыдущие данные и не подменяет их догадками."
        snapshot == null -> "Подключите портфель, чтобы Analyst AI мог объяснять структуру и существенные изменения."
        snapshot.warnings.isNotEmpty() -> snapshot.warnings.first()
        snapshot.allocations.isEmpty() -> "Портфель получен. Структура ещё не рассчитана источником данных."
        else -> {
            val largest = snapshot.allocations.maxByOrNull { it.sharePercent.toBigDecimal() }
            if (largest == null) {
                "Портфель получен. Следующая проверка уточнит структуру и ограничения."
            } else {
                "Крупнейшая категория сейчас — ${largest.title}: ${largest.sharePercent.percentText()}. Оцените её роль вместе с горизонтом и резервом."
            }
        }
    }
    SpectrumCard(emphasized = true) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            SpectrumIcon(SpectrumSymbol.Analyst, Modifier.size(64.dp), selected = true, tile = true)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("Ваш AI‑аналитик", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleLarge)
                SpectrumBadge("Вывод по фактам", accent = palette.violet)
            }
        }
        Text(summary, style = MaterialTheme.typography.bodyLarge)
        SpectrumPrimaryButton(
            text = "Показать рекомендации",
            onClick = onOpenRecommendations,
            modifier = Modifier.fillMaxWidth(),
            symbol = SpectrumSymbol.Ideas,
        )
    }
}

@Composable
private fun AllocationOverview(snapshot: PortfolioSnapshot, onOpenPortfolio: () -> Unit) {
    val palette = LocalSpectrumPalette.current
    SpectrumCard {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            SpectrumIcon(SpectrumSymbol.Allocation, Modifier.size(52.dp), selected = true, tile = true)
            Column(Modifier.weight(1f)) {
                Text("Структура портфеля", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleLarge)
                Text(
                    "Доли из текущих данных T‑Invest",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
        val entries = snapshot.allocations
            .filter { it.sharePercent.toBigDecimal().signum() >= 0 }
            .sortedByDescending { it.sharePercent.toBigDecimal() }
            .take(5)
        if (entries.isEmpty()) {
            Text(
                "Источник пока не вернул сопоставимые доли. Нули не подставляются.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        } else {
            val colors = listOf(palette.blue, palette.emerald, palette.violet, palette.amber, palette.rose)
            entries.forEachIndexed { index, allocation ->
                AllocationBar(allocation, colors[index % colors.size])
            }
        }
        SpectrumSecondaryButton("Подробнее о портфеле", onOpenPortfolio, Modifier.fillMaxWidth())
    }
}

@Composable
private fun AllocationBar(allocation: PortfolioAllocation, accent: Color) {
    val fraction = runCatching { allocation.sharePercent.toBigDecimal().toFloat() / 100f }.getOrDefault(0f)
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(allocation.title, modifier = Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(allocation.sharePercent.percentText(), fontWeight = FontWeight.SemiBold)
        }
        SpectrumProgressBar(fraction = fraction, accent = accent)
    }
}

@Composable
private fun DecisionGuardrail() {
    SpectrumCard {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            SpectrumIcon(SpectrumSymbol.Risk, Modifier.size(46.dp), selected = true, tile = true)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("Решение остаётся за вами", fontWeight = FontWeight.Bold)
                Text(
                    "Analyst AI объясняет данные и ограничения, но не обещает доходность и не выставляет сделки.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }
}

@Composable
private fun SectionTitle(title: String, subtitle: String) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        Text(subtitle, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
    }
}

private fun greeting(user: AnalystUser): String {
    val name = user.name?.trim().orEmpty()
    return if (name.isBlank()) "Ваш личный инвестиционный аналитик" else "$name · персональная аналитика"
}

private fun stateText(state: PortfolioUiState): String = when (state) {
    PortfolioUiState.NotConnected -> "Подключите read‑only T‑API, чтобы увидеть реальные счета и позиции."
    PortfolioUiState.ApiConnected -> "T‑API подключён. Получаем портфель."
    PortfolioUiState.Loading -> "Получаем актуальные данные портфеля."
    is PortfolioUiState.Error -> state.message
    is PortfolioUiState.Ready -> "Портфель готов"
}

private fun lastUpdatedText(snapshot: PortfolioSnapshot, lastUpdatedMillis: Long?): String {
    snapshot.asOf?.takeIf { it.isNotBlank() }?.let {
        return "Данные источника: ${it.take(19).replace('T', ' ')}"
    }
    val millis = lastUpdatedMillis ?: return "Время обновления не указано"
    return "Обновлено в ${SimpleDateFormat("HH:mm", Locale.forLanguageTag("ru-RU")).format(Date(millis))}"
}

@Composable
private fun yieldColor(snapshot: PortfolioSnapshot): Color {
    val sign = snapshot.expectedYieldPercent?.toBigDecimal()?.signum() ?: 0
    return when {
        sign > 0 -> LocalSpectrumPalette.current.emerald
        sign < 0 -> MaterialTheme.colorScheme.error
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
}
