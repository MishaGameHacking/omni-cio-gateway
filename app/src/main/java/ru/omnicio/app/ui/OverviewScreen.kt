package ru.omnicio.app.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.theme.OmniSpacing

@Composable
internal fun OverviewScreen(
    uiState: AppUiState,
    onToggleAmounts: () -> Unit,
    onCurrency: (DisplayCurrency) -> Unit,
    onMode: (OverviewMode) -> Unit,
) {
    val snapshot = overviewSnapshot(uiState.overviewMode, uiState.displayCurrency)

    StatusPill("ДЕМО · UI-02 · " + snapshot.freshnessLabel)

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.Top,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = formatMoney(
                    snapshot.totalMinor,
                    uiState.displayCurrency,
                    uiState.amountsHidden,
                ),
                style = MaterialTheme.typography.displaySmall,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.semantics { heading() },
            )
            Text(
                text = "Общая оценка портфеля · демо",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        TextButton(onClick = onToggleAmounts) {
            Text(if (uiState.amountsHidden) "Показать" else "Скрыть")
        }
    }

    CurrencySelector(
        selected = uiState.displayCurrency,
        onCurrency = onCurrency,
    )

    DataSourceCard(snapshot)

    MoneyBreakdown(
        snapshot = snapshot,
        currency = uiState.displayCurrency,
        hidden = uiState.amountsHidden,
    )

    AttentionCard(snapshot)

    PayoutsSection(
        snapshot = snapshot,
        currency = uiState.displayCurrency,
        hidden = uiState.amountsHidden,
    )

    DemoStateSelector(
        selected = uiState.overviewMode,
        onMode = onMode,
    )

    Text(
        text = "Пополнение не показывается как доходность. Неизвестное значение не заменяется нулём.",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    Text(
        text = "ID устройства " + installationIdLabel(uiState.installationId),
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

@Composable
private fun CurrencySelector(
    selected: DisplayCurrency,
    onCurrency: (DisplayCurrency) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(OmniSpacing.xs)) {
        Text(
            text = "Валюта отображения",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Row(
            modifier = Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(OmniSpacing.xs),
        ) {
            DisplayCurrency.entries.forEach { currency ->
                FilterChip(
                    selected = currency == selected,
                    onClick = { onCurrency(currency) },
                    label = { Text(currency.code) },
                )
            }
        }
    }
}

@Composable
private fun DataSourceCard(snapshot: OverviewSnapshot) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface,
        ),
    ) {
        Column(
            modifier = Modifier.padding(OmniSpacing.md),
            verticalArrangement = Arrangement.spacedBy(OmniSpacing.xs),
        ) {
            Text("Данные", fontWeight = FontWeight.SemiBold)
            LabelValue("Источник", snapshot.sourceLabel)
            LabelValue("Обновление", snapshot.updatedLabel)
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
private fun MoneyBreakdown(
    snapshot: OverviewSnapshot,
    currency: DisplayCurrency,
    hidden: Boolean,
) {
    BoxWithConstraints(modifier = Modifier.fillMaxWidth()) {
        val fontScale = LocalDensity.current.fontScale
        val values = listOf(
            Triple(
                "Доступно",
                snapshot.availableMinor,
                "Деньги отдельно от общей стоимости",
            ),
            Triple(
                "Резерв",
                snapshot.reserveMinor,
                "Не входит в бюджет сценария",
            ),
            Triple(
                "Бюджет сценария",
                snapshot.scenarioBudgetMinor,
                "Выбранная часть доступных денег",
            ),
        )

        if (!shouldStackMetricCards(maxWidth.value.toInt(), fontScale)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(OmniSpacing.sm),
            ) {
                values.forEach { (title, value, detail) ->
                    MetricCard(
                        title = title,
                        value = formatMoney(value, currency, hidden),
                        detail = detail,
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        } else {
            Column(verticalArrangement = Arrangement.spacedBy(OmniSpacing.sm)) {
                values.forEach { (title, value, detail) ->
                    MetricCard(
                        title = title,
                        value = formatMoney(value, currency, hidden),
                        detail = detail,
                    )
                }
            }
        }
    }
}

@Composable
private fun AttentionCard(snapshot: OverviewSnapshot) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer,
        ),
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
                color = MaterialTheme.colorScheme.onPrimaryContainer,
            )
        }
    }
}

@Composable
private fun PayoutsSection(
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
        items = snapshot.expectedPayouts,
        currency = currency,
        hidden = hidden,
    )
    PayoutGroup(
        title = "Получено",
        items = snapshot.receivedPayouts,
        currency = currency,
        hidden = hidden,
    )
}

@Composable
private fun PayoutGroup(
    title: String,
    items: List<PayoutFixture>,
    currency: DisplayCurrency,
    hidden: Boolean,
) {
    Column(verticalArrangement = Arrangement.spacedBy(OmniSpacing.xs)) {
        Text(
            text = title,
            style = MaterialTheme.typography.labelLarge,
        )
        if (items.isEmpty()) {
            Text(
                text = "Нет выплат в выбранном демо-состоянии",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        } else {
            items.forEach { payout ->
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surface,
                    ),
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
                            Text(
                                text = payout.title,
                                fontWeight = FontWeight.SemiBold,
                            )
                            Text(
                                text = payout.dateLabel,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        Text(
                            text = formatMoney(
                                payout.amountMinor,
                                currency,
                                hidden,
                            ),
                            textAlign = TextAlign.End,
                        )
                    }
                }
            }
        }
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
        Text(
            text = "Переключатель существует только для проверки UI-02 на демо-данных.",
            style = MaterialTheme.typography.bodySmall,
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

@Composable
private fun MetricCard(
    title: String,
    value: String,
    detail: String,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface,
        ),
    ) {
        Column(
            modifier = Modifier.padding(OmniSpacing.md),
            verticalArrangement = Arrangement.spacedBy(OmniSpacing.xs),
        ) {
            Text(
                text = title,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = value,
                style = MaterialTheme.typography.headlineSmall,
            )
            Text(
                text = detail,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
