package ru.omnicio.app.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import ru.omnicio.app.ui.theme.OmniSpacing

private const val T_INVEST_URL = "https://www.tbank.ru/invest/"

@Composable
internal fun PortfolioScreen(
    onOpenPosition: (String) -> Unit,
) {
    var query by rememberSaveable { mutableStateOf("") }
    var fixtureSizeName by rememberSaveable { mutableStateOf(PortfolioFixtureSize.DEFAULT.name) }
    val fixtureSize = runCatching {
        PortfolioFixtureSize.valueOf(fixtureSizeName)
    }.getOrDefault(PortfolioFixtureSize.DEFAULT)
    val positions = portfolioFixture(fixtureSize)
    val filtered = filterPortfolio(positions, query)

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(OmniSpacing.sm),
    ) {
        item {
            StatusPill("ДЕМО · UI-03 · " + positions.size + " позиций")
        }
        item {
            Text(
                text = "Портфель",
                style = MaterialTheme.typography.headlineMedium,
                modifier = Modifier.semantics { heading() },
            )
        }
        item {
            Text(
                text = "Все локально известные позиции показаны без тарифного лимита. Одинаковый инструмент по счетам объединяется с раскрытием источников.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        item {
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                label = { Text("Поиск по своему портфелю") },
                supportingText = {
                    Text("Название, тикер, ISIN или UID · только локальный fixture")
                },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
        }
        item {
            PortfolioFixtureSelector(
                selected = fixtureSize,
                onSelected = { fixtureSizeName = it.name },
            )
        }
        if (filtered.isEmpty()) {
            item {
                InfoCard(
                    title = if (positions.isEmpty()) "Портфель пуст" else "Ничего не найдено",
                    body = if (positions.isEmpty()) {
                        "Это подтверждённый empty fixture. Ноль позиций не означает ошибку источника."
                    } else {
                        "Поиск выполняется только по локально известным позициям."
                    },
                )
            }
        } else {
            items(
                items = filtered,
                key = { it.instrumentUid },
            ) { position ->
                PortfolioPositionRow(
                    position = position,
                    onClick = { onOpenPosition(position.instrumentUid) },
                )
            }
        }
        item {
            Text(
                text = "Stale и missing price всегда подписаны текстом. Отсутствующая цена не создаёт фиктивную стоимость.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun PortfolioFixtureSelector(
    selected: PortfolioFixtureSize,
    onSelected: (PortfolioFixtureSize) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(OmniSpacing.xs)) {
        Text(
            text = "QA · размер fixture",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Row(
            modifier = Modifier.horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(OmniSpacing.xs),
        ) {
            PortfolioFixtureSize.entries.forEach { size ->
                FilterChip(
                    selected = size == selected,
                    onClick = { onSelected(size) },
                    label = { Text(size.label) },
                )
            }
        }
    }
}

@Composable
private fun PortfolioPositionRow(
    position: PortfolioPosition,
    onClick: () -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface,
        ),
    ) {
        Column(
            modifier = Modifier.padding(OmniSpacing.md),
            verticalArrangement = Arrangement.spacedBy(OmniSpacing.xs),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = position.name,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        text = identifierLine(position),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Text(
                    text = formatMoney(
                        position.currentValueMinor,
                        position.currency,
                        hidden = false,
                    ),
                    style = MaterialTheme.typography.titleMedium,
                    textAlign = TextAlign.End,
                )
            }
            Text(
                text = formatQuantity(position.quantity) +
                    " · доступно " + formatQuantity(position.availableQuantity) +
                    " · заблокировано " + formatQuantity(position.blockedQuantity),
                style = MaterialTheme.typography.bodySmall,
            )
            Text(
                text = formatShare(position.shareBasisPoints),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = position.priceStatus.label + " · " + position.riskStatus.label,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
internal fun PositionDetailScreen(
    instrumentUid: String,
    onBack: () -> Unit,
) {
    val position = portfolioPositionByUid(instrumentUid)
    val uriHandler = LocalUriHandler.current
    var selectedScenario by rememberSaveable { mutableStateOf("Без действия") }

    if (position == null) {
        Text(
            text = "Позиция недоступна",
            style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.semantics { heading() },
        )
        InfoCard(
            title = "Нет локальных данных",
            body = "UID не найден в текущем fixture. Неизвестная позиция не подменяется пустой карточкой.",
        )
        Button(onClick = onBack) {
            Text("Назад к портфелю")
        }
        return
    }

    TextButton(onClick = onBack) {
        Text("← Назад к портфелю")
    }
    StatusPill("ДЕМО · КАРТОЧКА ПОЗИЦИИ")
    Text(
        text = position.name,
        style = MaterialTheme.typography.headlineMedium,
        modifier = Modifier.semantics { heading() },
    )
    Text(
        text = identifierLine(position),
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )

    PositionMetrics(position)
    PriceSourceCard(position)

    InfoCard(
        title = "Выплаты",
        body = position.payoutLabel,
    )

    InfoCard(
        title = "Подтверждённые общие факты · fixture",
        body = position.issuerFacts.joinToString(separator = "
"),
    )

    AccountSourcesCard(position)

    InfoCard(
        title = "Концентрация",
        body = formatShare(position.shareBasisPoints) +
            ". Это доля текущей известной оценки локального fixture, а не рекомендация.",
    )

    ScenarioActionCard(
        selected = selectedScenario,
        onSelected = { selectedScenario = it },
    )

    InfoCard(
        title = "Поиск в Т‑Инвестициях",
        body = "Используйте идентификаторы выше. Внешний переход открывает брокера/браузер и не создаёт заявку, сделку или перевод.",
    )
    Button(
        onClick = { uriHandler.openUri(T_INVEST_URL) },
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text("Открыть Т‑Инвестиции")
    }
}

@Composable
private fun PositionMetrics(position: PortfolioPosition) {
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
            DetailLine("Количество", formatQuantity(position.quantity))
            DetailLine("Доступно", formatQuantity(position.availableQuantity))
            DetailLine("Заблокировано", formatQuantity(position.blockedQuantity))
            DetailLine(
                "Текущая оценка",
                formatMoney(position.currentValueMinor, position.currency, hidden = false),
            )
            DetailLine(
                "Цена",
                formatMoney(position.currentPriceMinor, position.currency, hidden = false),
            )
            DetailLine("Доля", formatShare(position.shareBasisPoints).removePrefix("доля: "))
            DetailLine("Лот", position.lotSize.toString() + " шт.")
            DetailLine("Валюта", position.currency.code)
            DetailLine("Состояние цены", position.priceStatus.label)
            DetailLine("Risk/data status", position.riskStatus.label)
        }
    }
}

@Composable
private fun PriceSourceCard(position: PortfolioPosition) {
    InfoCard(
        title = "Источник цены",
        body = position.priceSource + "
Обновление: " + position.priceUpdatedLabel,
    )
}

@Composable
private fun AccountSourcesCard(position: PortfolioPosition) {
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
            Text(
                text = "Локальные источники позиции",
                fontWeight = FontWeight.SemiBold,
            )
            position.accounts.forEach { account ->
                Text(
                    text = account.accountLabel + ": " +
                        formatQuantity(account.quantity) +
                        ", доступно " + formatQuantity(account.availableQuantity) +
                        ", заблокировано " + formatQuantity(account.blockedQuantity),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun ScenarioActionCard(
    selected: String,
    onSelected: (String) -> Unit,
) {
    val actions = listOf(
        "Без действия",
        "Сценарий покупки",
        "Сценарий сокращения",
    )
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
            Text(
                text = "Сценарное действие",
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                text = "Выбор остаётся локальным. UI‑03 не создаёт брокерскую заявку.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(
                modifier = Modifier.horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(OmniSpacing.xs),
            ) {
                actions.forEach { action ->
                    FilterChip(
                        selected = action == selected,
                        onClick = { onSelected(action) },
                        label = { Text(action) },
                    )
                }
            }
            Text(
                text = "Выбрано: " + selected,
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
private fun DetailLine(label: String, value: String) {
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
            modifier = Modifier.weight(1.2f),
        )
    }
}

private fun identifierLine(position: PortfolioPosition): String = listOfNotNull(
    position.ticker,
    position.isin,
    position.instrumentUid,
).joinToString(separator = " · ")
