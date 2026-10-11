package ru.omnicio.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import ru.omnicio.app.BuildConfig
import ru.omnicio.app.ui.theme.OmniSpacing

private enum class OverviewTab(val label: String) {
    SUMMARY("Обзор"),
    PAYOUTS("Выплаты"),
    SCENARIOS("Сценарии"),
    EVENTS("События"),
}

@Composable
internal fun OverviewScreen(
    uiState: AppUiState,
    onToggleAmounts: () -> Unit,
    onCurrency: (DisplayCurrency) -> Unit,
    onMode: (OverviewMode) -> Unit,
) {
    val snapshot = overviewSnapshot(uiState.overviewMode, uiState.displayCurrency)
    var tabName by rememberSaveable { mutableStateOf(OverviewTab.SUMMARY.name) }
    val selectedTab = runCatching { OverviewTab.valueOf(tabName) }
        .getOrDefault(OverviewTab.SUMMARY)
    var showQa by rememberSaveable { mutableStateOf(false) }

    OverviewTabs(
        selected = selectedTab,
        onSelected = { tabName = it.name },
    )

    when (selectedTab) {
        OverviewTab.SUMMARY -> {
            PortfolioHeroCard(
                snapshot = snapshot,
                currency = uiState.displayCurrency,
                hidden = uiState.amountsHidden,
                onToggleAmounts = onToggleAmounts,
                onCurrency = onCurrency,
            )
            AttentionCard(snapshot)
            PayoutPreview(
                snapshot = snapshot,
                currency = uiState.displayCurrency,
                hidden = uiState.amountsHidden,
            )
        }
        OverviewTab.PAYOUTS -> {
            PayoutsSection(
                snapshot = snapshot,
                currency = uiState.displayCurrency,
                hidden = uiState.amountsHidden,
            )
        }
        OverviewTab.SCENARIOS -> {
            Text(
                text = "Сценарии портфеля",
                style = MaterialTheme.typography.headlineSmall,
                modifier = Modifier.semantics { heading() },
            )
            MoneyBreakdown(
                snapshot = snapshot,
                currency = uiState.displayCurrency,
                hidden = uiState.amountsHidden,
            )
            InfoCard(
                title = "Локальный расчёт",
                body = "Резерв и бюджет сценария остаются на устройстве. Демо-режим не создаёт брокерскую заявку.",
            )
        }
        OverviewTab.EVENTS -> {
            AttentionCard(snapshot)
            DataSourceCard(snapshot)
        }
    }

    if (BuildConfig.DEBUG) {
        TextButton(onClick = { showQa = !showQa }) {
            Text(if (showQa) "Скрыть демо-состояния" else "Демо-состояния")
        }
        if (showQa) {
            DemoStateSelector(
                selected = uiState.overviewMode,
                onMode = onMode,
            )
        }
    }

    Text(
        text = "Демо-данные · " + snapshot.updatedLabel,
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

@Composable
private fun OverviewTabs(
    selected: OverviewTab,
    onSelected: (OverviewTab) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(OmniSpacing.xs),
    ) {
        OverviewTab.entries.forEach { tab ->
            Column(
                modifier = Modifier.widthIn(min = 76.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                TextButton(onClick = { onSelected(tab) }) {
                    Text(
                        text = tab.label,
                        color = if (tab == selected) {
                            MaterialTheme.colorScheme.onBackground
                        } else {
                            MaterialTheme.colorScheme.onSurfaceVariant
                        },
                        fontWeight = if (tab == selected) FontWeight.SemiBold else FontWeight.Normal,
                    )
                }
                HorizontalDivider(
                    thickness = 3.dp,
                    color = if (tab == selected) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        Color.Transparent
                    },
                )
            }
        }
    }
}

@Composable
private fun PortfolioHeroCard(
    snapshot: OverviewSnapshot,
    currency: DisplayCurrency,
    hidden: Boolean,
    onToggleAmounts: () -> Unit,
    onCurrency: (DisplayCurrency) -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Column(
            modifier = Modifier.padding(OmniSpacing.md),
            verticalArrangement = Arrangement.spacedBy(OmniSpacing.sm),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column {
                    Text(
                        text = "Стоимость портфеля",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        text = formatMoney(snapshot.totalMinor, currency, hidden),
                        style = MaterialTheme.typography.displaySmall,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.semantics { heading() },
                    )
                }
                TextButton(onClick = onToggleAmounts) {
                    Text(if (hidden) "Показать" else "Скрыть")
                }
            }

            PortfolioSparkline()

            CompactMoneyRow(
                snapshot = snapshot,
                currency = currency,
                hidden = hidden,
            )

            Row(
                modifier = Modifier.horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(OmniSpacing.xs),
            ) {
                DisplayCurrency.entries.forEach { item ->
                    FilterChip(
                        selected = item == currency,
                        onClick = { onCurrency(item) },
                        label = { Text(item.code) },
                    )
                }
            }

            Text(
                text = snapshot.sourceLabel + " · " + snapshot.freshnessLabel,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun PortfolioSparkline() {
    val lineColor = MaterialTheme.colorScheme.tertiary
    Canvas(
        modifier = Modifier
            .fillMaxWidth()
            .height(54.dp),
    ) {
        val points = listOf(
            0.58f, 0.54f, 0.56f, 0.49f, 0.47f, 0.45f, 0.39f,
            0.42f, 0.34f, 0.31f, 0.27f, 0.29f, 0.21f, 0.17f, 0.11f,
        )
        val path = Path()
        points.forEachIndexed { index, value ->
            val x = size.width * index / (points.size - 1)
            val y = size.height * value
            if (index == 0) path.moveTo(x, y) else path.lineTo(x, y)
        }
        drawPath(
            path = path,
            color = lineColor,
            style = Stroke(width = 3.dp.toPx()),
        )
    }
}

@Composable
private fun CompactMoneyRow(
    snapshot: OverviewSnapshot,
    currency: DisplayCurrency,
    hidden: Boolean,
) {
    BoxWithConstraints(modifier = Modifier.fillMaxWidth()) {
        val fontScale = LocalDensity.current.fontScale
        val stack = maxWidth < 340.dp || fontScale >= 1.4f
        val values = listOf(
            "Доступно" to snapshot.availableMinor,
            "Резерв" to snapshot.reserveMinor,
            "Бюджет" to snapshot.scenarioBudgetMinor,
        )
        if (stack) {
            Column(verticalArrangement = Arrangement.spacedBy(OmniSpacing.xs)) {
                values.forEach { (label, value) ->
                    CompactMetricLine(
                        label = label,
                        value = formatMoney(value, currency, hidden),
                    )
                }
            }
        } else {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(OmniSpacing.sm),
            ) {
                values.forEach { (label, value) ->
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = label,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Text(
                            text = formatMoney(value, currency, hidden),
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun CompactMetricLine(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun AttentionCard(snapshot: OverviewSnapshot) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
    ) {
        Column(
            modifier = Modifier.padding(OmniSpacing.md),
            verticalArrangement = Arrangement.spacedBy(OmniSpacing.xs),
        ) {
            Text(
                text = snapshot.noticeTitle,
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
            )
            Text(
                text = snapshot.noticeBody,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
            )
        }
    }
}

@Composable
private fun PayoutPreview(
    snapshot: OverviewSnapshot,
    currency: DisplayCurrency,
    hidden: Boolean,
) {
    Text(
        text = "Ближайшие выплаты",
        style = MaterialTheme.typography.headlineSmall,
        modifier = Modifier.semantics { heading() },
    )
    PayoutGroup(
        title = "Ожидается",
        items = snapshot.expectedPayouts.take(2),
        currency = currency,
        hidden = hidden,
    )
}

@Composable
private fun PayoutsSection(
    snapshot: OverviewSnapshot,
    currency: DisplayCurrency,
    hidden: Boolean,
) {
    Text(
        text = "Выплаты",
        style = MaterialTheme.typography.headlineSmall,
        modifier = Modifier.semantics { heading() },
    )
    PayoutGroup("Ожидается", snapshot.expectedPayouts, currency, hidden)
    PayoutGroup("Получено", snapshot.receivedPayouts, currency, hidden)
}

@Composable
private fun PayoutGroup(
    title: String,
    items: List<PayoutFixture>,
    currency: DisplayCurrency,
    hidden: Boolean,
) {
    Column(verticalArrangement = Arrangement.spacedBy(OmniSpacing.xs)) {
        Text(text = title, style = MaterialTheme.typography.labelLarge)
        if (items.isEmpty()) {
            Text(
                text = "Нет выплат в выбранном демо-состоянии",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        } else {
            items.forEach { payout ->
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(OmniSpacing.md),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(
                            modifier = Modifier.weight(1f),
                            verticalArrangement = Arrangement.spacedBy(OmniSpacing.xxs),
                        ) {
                            Text(payout.title, fontWeight = FontWeight.SemiBold)
                            Text(
                                payout.dateLabel,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        Text(
                            text = formatMoney(payout.amountMinor, currency, hidden),
                            textAlign = TextAlign.End,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun MoneyBreakdown(
    snapshot: OverviewSnapshot,
    currency: DisplayCurrency,
    hidden: Boolean,
) {
    val rows = listOf(
        "Доступно" to snapshot.availableMinor,
        "Резерв" to snapshot.reserveMinor,
        "Бюджет сценария" to snapshot.scenarioBudgetMinor,
    )
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Column(
            modifier = Modifier.padding(OmniSpacing.md),
            verticalArrangement = Arrangement.spacedBy(OmniSpacing.sm),
        ) {
            rows.forEach { (label, value) ->
                CompactMetricLine(label, formatMoney(value, currency, hidden))
            }
        }
    }
}

@Composable
private fun DataSourceCard(snapshot: OverviewSnapshot) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Column(
            modifier = Modifier.padding(OmniSpacing.md),
            verticalArrangement = Arrangement.spacedBy(OmniSpacing.xs),
        ) {
            Text("Состояние данных", fontWeight = FontWeight.SemiBold)
            LabelValue("Источник", snapshot.sourceLabel)
            LabelValue("Обновлено", snapshot.updatedLabel)
            LabelValue("Актуальность", snapshot.freshnessLabel)
        }
    }
}

@Composable
private fun LabelValue(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(
            text = label,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.weight(1f),
        )
        Text(
            text = value,
            textAlign = TextAlign.End,
            modifier = Modifier.weight(1.5f),
        )
    }
}

@Composable
private fun DemoStateSelector(
    selected: OverviewMode,
    onMode: (OverviewMode) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(OmniSpacing.xs)) {
        Text(
            text = "QA · состояние данных",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Row(
            modifier = Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(OmniSpacing.xs),
        ) {
            OverviewMode.entries.forEach { mode ->
                FilterChip(
                    selected = mode == selected,
                    onClick = { onMode(mode) },
                    label = { Text(mode.label) },
                )
            }
        }
    }
}
