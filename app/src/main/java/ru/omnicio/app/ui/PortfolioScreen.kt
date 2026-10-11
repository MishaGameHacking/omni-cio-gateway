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
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import ru.omnicio.app.BuildConfig
import ru.omnicio.app.ui.theme.OmniSpacing

private const val T_INVEST_URL = "https://www.tbank.ru/invest/"

@Composable
internal fun PortfolioScreen(
    dataAvailable: Boolean,
    onOpenPosition: (String) -> Unit,
) {
    if (!dataAvailable) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            verticalArrangement = Arrangement.spacedBy(OmniSpacing.sm),
        ) {
            item { StatusPill("ЛОКАЛЬНЫЕ ДАННЫЕ УДАЛЕНЫ") }
            item {
                Text(
                    text = "Портфель",
                    style = MaterialTheme.typography.headlineMedium,
                    modifier = Modifier.semantics { heading() },
                )
            }
            item {
                InfoCard(
                    title = "Портфель удалён с устройства",
                    body = "OMNICIO не подменяет удалённые данные нулевыми позициями. Демо-набор можно восстановить в настройках.",
                )
            }
        }
        return
    }

    var query by rememberSaveable { mutableStateOf("") }
    var showQa by rememberSaveable { mutableStateOf(false) }
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
            StatusPill("ДЕМО · " + positions.size + " позиций")
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
                text = "Все локально известные позиции без тарифного лимита. Одинаковый инструмент по счетам объединяется.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        item {
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                label = { Text("Поиск по своему портфелю") },
                supportingText = {
                    Text("Название, тикер, ISIN или UID · только локальный демо-набор")
                },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
        }
        if (BuildConfig.DEBUG) {
            item {
                TextButton(onClick = { showQa = !showQa }) {
                    Text(if (showQa) "Скрыть QA" else "Демо-набор")
                }
            }
            if (showQa) {
                item {
                    PortfolioFixtureSelector(
                        selected = fixtureSize,
                        onSelected = { fixtureSizeName = it.name },
                    )
                }
            }
        }
        if (filtered.isEmpty()) {
            item {
                InfoCard(
                    title = if (positions.isEmpty()) "Портфель пуст" else "Ничего не найдено",
                    body = if (positions.isEmpty()) {
                        "Это подтверждённый пустой демо-набор. Ноль позиций не означает ошибку источника."
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
                text = "Устаревшая или отсутствующая цена всегда подписана текстом. Отсутствующая цена не создаёт фиктивную стоимость.",
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
            text = "QA · размер демо-набора",
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
                PositionIdentity(
                    position = position,
                    modifier = Modifier.weight(1f),
                )
                Text(
                    text = formatMoney(
                        position.currentValueMinor,
                        position.currency,
                        hidden = false,
                    ),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    textAlign = TextAlign.End,
                )
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    text = formatQuantity(position.quantity) +
                        " · доступно " + formatQuantity(position.availableQuantity),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.weight(1f),
                )
                Text(
                    text = formatShare(position.shareBasisPoints),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text(
                text = position.priceStatus.label + " · " + position.riskStatus.label,
                style = MaterialTheme.typography.labelMedium,
                color = if (position.priceStatus == PriceStatus.CURRENT) {
                    MaterialTheme.colorScheme.tertiary
                } else {
                    MaterialTheme.colorScheme.onSurfaceVariant
                },
            )
        }
    }
}

@Composable
private fun PositionIdentity(
    position: PortfolioPosition,
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier) {
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
}

@Composable
internal fun PositionDetailScreen(
    instrumentUid: String,
    dataAvailable: Boolean,
    onBack: () -> Unit,
) {
    val position = if (dataAvailable) portfolioPositionByUid(instrumentUid) else null
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
            body = "UID не найден в текущем демо-наборе. Неизвестная позиция не подменяется пустой карточкой.",
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
        title = "Подтверждённые общие факты · демо",
        body = position.issuerFacts.joinToString(separator = "\n"),
    )

    AccountSourcesCard(position)

    InfoCard(
        title = "Концентрация",
        body = formatShare(position.shareBasisPoints) +
            ". Это доля текущей известной оценки локального демо-набора, а не рекомендация.",
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
            DetailLine("Состояние риска и данных", position.riskStatus.label)
        }
    }
}

@Composable
private fun PriceSourceCard(position: PortfolioPosition) {
    InfoCard(
        title = "Источник цены",
        body = position.priceSource + "\nОбновление: " + position.priceUpdatedLabel,
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
    if (shouldStackDetailLine(LocalDensity.current.fontScale)) {
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(OmniSpacing.xxs),
        ) {
            Text(
                text = label,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(text = value)
        }
    } else {
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
}

private fun identifierLine(position: PortfolioPosition): String = listOfNotNull(
    position.ticker,
    position.isin,
    position.instrumentUid,
).joinToString(separator = " · ")
