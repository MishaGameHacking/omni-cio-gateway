package ru.omnicio.app.ui.home

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import ru.omnicio.app.data.backend.AnalystUser
import ru.omnicio.app.data.portfolio.PortfolioCurrency
import ru.omnicio.app.data.portfolio.PortfolioSnapshot
import ru.omnicio.app.data.portfolio.PortfolioUiState
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.portfolio.moneyText
import ru.omnicio.app.ui.portfolio.percentText
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.theme.LocalSpectrumMotionPreference

/** Native dashboard: balance -> four shortcuts -> analyst, not a giant portfolio form. */
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
                modifier = Modifier
                    .fillMaxSize()
                    .padding(insets)
                    .consumeWindowInsets(insets),
                contentPadding = PaddingValues(horizontal = 20.dp, vertical = 14.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                item(key = "brand-header") { HomeHeader(user, onOpenMessages) }
                item(key = "portfolio-hero") {
                    BalanceCard(
                        state,
                        snapshot,
                        selectedCurrency,
                        refreshing,
                        refreshError,
                        lastUpdatedMillis,
                        onCurrencyClick,
                        onOpenProfile,
                    )
                }
                item(key = "capabilities") {
                    HomeQuickActions(
                        onOpenPortfolio,
                        onOpenRecommendations,
                        onOpenRisk,
                        onOpenMessages,
                    )
                }
                item(key = "assistant") {
                    AnalystSummaryCard(snapshot, refreshError, onOpenRecommendations)
                }
                if (snapshot != null) {
                    item(key = "allocation") { AllocationOverview(snapshot, onOpenPortfolio) }
                }
                item(key = "education") {
                    SpectrumActionTile(
                        "Обучение",
                        "Инвестиции простыми словами",
                        SpectrumSymbol.Education,
                        onOpenEducation,
                        Modifier.fillMaxWidth(),
                        LocalSpectrumPalette.current.cyan,
                    )
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
        Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        SpectrumBrandOrb(Modifier.size(46.dp), compact = true)
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text("Главная", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text("Analyst AI", color = palette.cyan, style = MaterialTheme.typography.labelLarge)
            val name = user.name?.trim().orEmpty()
            if (name.isNotBlank()) {
                Text(
                    name,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
        Surface(
            onClick = onMessagesClick,
            modifier = Modifier.size(48.dp),
            shape = RoundedCornerShape(16.dp),
            color = palette.cardStrong,
            border = BorderStroke(1.dp, palette.blue.copy(alpha = 0.4f)),
        ) {
            SpectrumLiveFeatureIcon(
                feature = SpectrumLiveFeature.Notifications,
                modifier = Modifier.padding(8.dp),
                motionAllowed = LocalSpectrumMotionPreference.current.enabled,
            )
        }
    }
}

@Composable
private fun BalanceCard(
    state: PortfolioUiState,
    snapshot: PortfolioSnapshot?,
    currency: PortfolioCurrency,
    refreshing: Boolean,
    refreshError: String?,
    updatedMillis: Long?,
    onCurrencyClick: () -> Unit,
    onOpenProfile: () -> Unit,
) {
    val palette = LocalSpectrumPalette.current
    SpectrumCard(emphasized = true) {
        if (snapshot == null) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                SpectrumBrandOrb(Modifier.size(70.dp))
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(
                        "Ваш инвестиционный мир",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        stateText(state),
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            }
            SpectrumPrimaryButton(
                if (state == PortfolioUiState.NotConnected) "Подключить портфель" else "Открыть профиль",
                onOpenProfile,
                Modifier.fillMaxWidth(),
                symbol = SpectrumSymbol.Portfolio,
            )
        } else {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    "Общий баланс",
                    Modifier.weight(1f),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodyMedium,
                )
                SpectrumBadge(currency.name, accent = palette.cyan)
            }
            Column(
                Modifier
                    .fillMaxWidth()
                    .heightIn(min = 56.dp)
                    .clickable(
                        role = Role.Button,
                        onClickLabel = "Сменить валюту баланса",
                        onClick = onCurrencyClick,
                    ),
                verticalArrangement = Arrangement.spacedBy(3.dp),
            ) {
                Text(
                    snapshot.totalValue.moneyText(),
                    fontSize = 32.sp,
                    lineHeight = 38.sp,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    "Нажмите на сумму: ₽ → $ → €",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            val yield = snapshot.expectedYieldPercent
            Text(
                "Доходность: ${yield.percentText()}",
                color = yieldColor(snapshot),
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
            )
            // This line describes the actual snapshot; it is not a fabricated historical curve.
            Text(
                lastUpdatedText(snapshot, updatedMillis),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        when {
            refreshError != null -> SpectrumBadge(
                "Не обновлено · сохранённые данные",
                accent = MaterialTheme.colorScheme.error,
            )
            refreshing -> SpectrumBadge("Обновляем данные", accent = palette.cyan)
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
    val motion = LocalSpectrumMotionPreference.current
    val fontScale = LocalDensity.current.fontScale
    val mood = when {
        refreshError != null -> AnalystAvatarMood.Attention
        snapshot == null -> AnalystAvatarMood.Waiting
        snapshot.warnings.isNotEmpty() -> AnalystAvatarMood.Attention
        else -> AnalystAvatarMood.Ready
    }
    val summary = when {
        refreshError != null -> "Обновить данные не удалось. Показываем сохранённый портфель, а не новые предположения."
        snapshot == null -> "Подключите портфель. Я помогу разобраться в его структуре и существенных изменениях."
        snapshot.warnings.isNotEmpty() -> snapshot.warnings.first()
        snapshot.allocations.isEmpty() -> "Портфель получен. Источник ещё не вернул его структуру."
        else -> {
            val largest = snapshot.allocations.maxByOrNull { it.sharePercent.toBigDecimal() }
            if (largest == null) {
                "Портфель получен. Следующая проверка уточнит его структуру."
            } else {
                "Крупнейшая категория — ${largest.title}: ${largest.sharePercent.percentText()}. Оцените её вместе с горизонтом и резервом."
            }
        }
    }

    SpectrumCard(emphasized = true) {
        BoxWithConstraints(Modifier.fillMaxWidth()) {
            val stacked = maxWidth < 310.dp || fontScale > 1.35f
            if (stacked) {
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    SpectrumAnalystAvatar(
                        mood = mood,
                        motionAllowed = motion.enabled,
                        modifier = Modifier
                            .size(118.dp)
                            .testTag("spectrum-ai-analyst"),
                    )
                    Column(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(3.dp),
                    ) {
                        Text(
                            "Привет!",
                            fontWeight = FontWeight.Bold,
                            style = MaterialTheme.typography.titleLarge,
                        )
                        Text(
                            "Я ваш AI‑аналитик",
                            style = MaterialTheme.typography.bodyMedium,
                            color = palette.cyan,
                        )
                    }
                }
            } else {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(14.dp),
                ) {
                    SpectrumAnalystAvatar(
                        mood = mood,
                        motionAllowed = motion.enabled,
                        modifier = Modifier
                            .size(104.dp)
                            .testTag("spectrum-ai-analyst"),
                    )
                    Column(
                        modifier = Modifier.weight(1f),
                        verticalArrangement = Arrangement.spacedBy(3.dp),
                    ) {
                        Text(
                            "Привет!",
                            fontWeight = FontWeight.Bold,
                            style = MaterialTheme.typography.titleLarge,
                        )
                        Text(
                            "Я ваш AI‑аналитик",
                            style = MaterialTheme.typography.bodyMedium,
                            color = palette.cyan,
                        )
                        Text(
                            "Анализирую только подтверждённые данные вашего портфеля.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
        Text(summary, style = MaterialTheme.typography.bodyMedium)
        Text(
            "Вывод по фактам портфеля",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        SpectrumPrimaryButton(
            "Показать рекомендации",
            onOpenRecommendations,
            Modifier.fillMaxWidth(),
            symbol = SpectrumSymbol.Ideas,
        )
    }
}

@Composable
private fun AllocationOverview(snapshot: PortfolioSnapshot, onOpenPortfolio: () -> Unit) {
    val palette = LocalSpectrumPalette.current
    SpectrumCard {
        Text(
            "Структура портфеля",
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
        )
        Text(
            "Счетов: ${snapshot.accounts.size} · Позиции: ${snapshot.accounts.sumOf { it.positions.size + it.virtualPositions.size }}",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        val entries = snapshot.allocations
            .filter { it.sharePercent.toBigDecimal().signum() >= 0 }
            .sortedByDescending { it.sharePercent.toBigDecimal() }
            .take(5)
        val colors = listOf(palette.blue, palette.emerald, palette.violet, palette.amber, palette.rose)
        if (entries.isEmpty()) {
            Text(
                "Сопоставимые доли пока не получены.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        entries.forEachIndexed { index, entry ->
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(entry.title, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
                Text(
                    entry.sharePercent.percentText(),
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            SpectrumProgressBar(
                entry.sharePercent.toBigDecimal().toFloat() / 100f,
                accent = colors[index % colors.size],
            )
        }
        SpectrumSecondaryButton(
            "Открыть мой портфель",
            onOpenPortfolio,
            Modifier.fillMaxWidth(),
        )
    }
}

@Composable
private fun DecisionGuardrail() {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        SpectrumIcon(
            SpectrumSymbol.Risk,
            Modifier.size(26.dp),
            selected = true,
            tile = false,
            motionAllowed = false,
        )
        Text(
            "Решение остаётся за вами. Analyst AI объясняет данные и ограничения, не обещает доходность и не выставляет сделки.",
            Modifier.weight(1f),
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            style = MaterialTheme.typography.bodySmall,
        )
    }
}

private fun stateText(state: PortfolioUiState): String = when (state) {
    PortfolioUiState.NotConnected -> "Подключите T‑API с доступом только для чтения."
    PortfolioUiState.ApiConnected -> "Получаем счета и позиции."
    PortfolioUiState.Loading -> "Загружаем портфель."
    is PortfolioUiState.Error -> state.message
    is PortfolioUiState.Ready -> "Портфель готов"
}

private fun lastUpdatedText(snapshot: PortfolioSnapshot, lastUpdatedMillis: Long?): String {
    snapshot.asOf
        ?.takeIf { it.isNotBlank() }
        ?.let { return "Данные: ${it.take(19).replace('T', ' ')}" }
    val millis = lastUpdatedMillis ?: return "Время обновления не указано"
    return "Обновлено в ${
        SimpleDateFormat("HH:mm", Locale.forLanguageTag("ru-RU")).format(Date(millis))
    }"
}

@Composable
private fun yieldColor(snapshot: PortfolioSnapshot): Color = when (
    snapshot.expectedYieldPercent?.toBigDecimal()?.signum() ?: 0
) {
    1 -> LocalSpectrumPalette.current.emerald
    -1 -> MaterialTheme.colorScheme.error
    else -> MaterialTheme.colorScheme.onSurfaceVariant
}
