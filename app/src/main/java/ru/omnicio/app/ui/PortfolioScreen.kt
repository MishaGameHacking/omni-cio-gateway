package ru.omnicio.app.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp
import ru.omnicio.app.R

private const val NO_POSITION_DATA = "Нет данных"

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun PortfolioScreen(
    state: AppUiState, sync: () -> Unit = {}, toggleAmounts: () -> Unit = {},
    loadAccounts: () -> Unit = {}, selectAccount: (String) -> Unit = {}, connect: () -> Unit = {},
) {
    var search by remember { mutableStateOf("") }
    var selected by remember { mutableStateOf<String?>(null) }
    var sheet by remember { mutableStateOf<String?>(null) }
    val workspace = state.workspace
    LaunchedEffect(workspace?.connection?.accountId) { selected = null; sheet = null; search = "" }
    val portfolio = workspace?.portfolio
    val positions = portfolio?.positions.orEmpty().filter {
        it.name.contains(search, true) || it.ticker.contains(search, true)
    }
    LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text("Портфель", Modifier.weight(1f), style = MaterialTheme.typography.headlineLarge)
                IconButton(onClick = toggleAmounts) {
                    OmniIcon(R.drawable.ic_eye, if (state.amountsHidden) "Показать суммы" else "Скрыть суммы")
                }
            }
        }
        if (workspace?.connection?.connected == true) {
            item {
                TextButton(onClick = { sheet = "accounts"; loadAccounts() }, enabled = !state.busy) {
                    Text("${workspace.connection.name ?: "Счёт"} • ${workspace.connection.accountId?.takeLast(4).orEmpty()}")
                    OmniIcon(R.drawable.ic_chevron)
                }
            }
            item {
                OmniCard {
                    Text(money(portfolio?.total, state.amountsHidden), style = MaterialTheme.typography.displaySmall)
                    Text(statusLabel(portfolio?.freshness) + " · " + timestampLabel(portfolio?.capturedAt),
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                        TextButton(onClick = sync, enabled = !state.busy) { Text("Обновить") }
                        TextButton(onClick = { sheet = "analytics" }) { Text("Аналитика") }
                        TextButton(onClick = { sheet = "cash" }) { Text("Деньги") }
                    }
                }
            }
            item {
                OutlinedTextField(search, { search = it }, singleLine = true,
                    label = { Text("Найти актив в портфеле") }, modifier = Modifier.fillMaxWidth())
            }
            if (portfolio == null) item {
                EmptyState(if (state.busy) "Получаем портфель" else "Снимок пока не получен",
                    "Данные загружаются из вашего счёта. Нажмите «Обновить», чтобы повторить запрос.")
            } else {
                if (positions.isEmpty() && search.isNotBlank()) item { Text("Совпадений нет.") }
                items(positions, key = { it.uid }) { position ->
                    PositionCard(position, state.amountsHidden) { selected = position.uid }
                }
                if (search.isBlank()) item {
                    ListItem(headlineContent = { Text("Рубли") },
                        supportingContent = { Text("Деньги на счёте") },
                        trailingContent = { Text(money(portfolio.cash, state.amountsHidden)) },
                        modifier = Modifier.clickable { sheet = "cash" },
                        colors = ListItemDefaults.colors(containerColor = MaterialTheme.colorScheme.surface))
                }
            }
        } else item {
            EmptyState(if (workspace == null) "Данные не получены" else "Подключите счёт",
                "Выберите свой счёт Т-Инвестиций в профиле.", R.drawable.ic_bank)
            TextButton(onClick = connect) { Text("Открыть профиль") }
        }
    }
    val detail = portfolio?.positions?.find { it.uid == selected }
    if (detail != null) ModalBottomSheet(onDismissRequest = { selected = null },
        properties = sheetProperties(state.screenshotsBlocked)) {
        Box(Modifier.fillMaxHeight(0.9f)) { PositionDetail(detail, portfolio, state.amountsHidden) { selected = null } }
    }
    if (sheet != null) ModalBottomSheet(onDismissRequest = { sheet = null },
        properties = sheetProperties(state.screenshotsBlocked)) {
        when (sheet) {
            "accounts" -> AccountPicker(state, loadAccounts, selectAccount) { sheet = null }
            "analytics" -> Box(Modifier.fillMaxHeight(0.9f)) {
                OverviewScreen(state, toggleAmounts, sync, connect)
            }
            else -> Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                SectionTitle("Деньги на счёте")
                MetricRow("Всего", money(portfolio?.cash, state.amountsHidden))
                MetricRow("Не заблокировано", money(portfolio?.freeCash, state.amountsHidden))
                MetricRow("Заблокировано", money(portfolio?.blockedCash, state.amountsHidden))
                Spacer(Modifier.height(24.dp))
            }
        }
    }
}

@Composable
private fun AccountPicker(state: AppUiState, loadAccounts: () -> Unit,
    selectAccount: (String) -> Unit, dismiss: () -> Unit) {
    LazyColumn(contentPadding = PaddingValues(20.dp)) {
        item { SectionTitle("Выберите счёт") }
        if (state.accounts.isEmpty()) item {
            Text(if (state.busy) "Загружаем счета…" else "Список счетов не получен.")
            TextButton(onClick = loadAccounts, enabled = !state.busy) { Text("Повторить") }
        }
        items(state.accounts, key = { it.id }) { account ->
            ListItem(headlineContent = { Text(account.name) },
                supportingContent = { Text("•• ${account.id.takeLast(4)}") },
                trailingContent = { if (account.id == state.workspace?.connection?.accountId) Text("Выбран") },
                modifier = Modifier.clickable(enabled = !state.busy && account.status == "ACCOUNT_STATUS_OPEN") {
                    dismiss()
                    if (account.id != state.workspace?.connection?.accountId) selectAccount(account.id)
                })
        }
    }

}

@Composable
private fun PositionDetail(detail: PortfolioPosition, portfolio: ServerPortfolio, hidden: Boolean, back: () -> Unit) {
    LazyColumn(contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item { TextButton(onClick = back) { OmniIcon(R.drawable.ic_back); Text("Все позиции") } }
        item {
            OmniCard {
                Text(detail.name.ifBlank { detail.ticker.ifBlank { "Инструмент" } }, style = MaterialTheme.typography.headlineMedium)
                Text(detail.ticker, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(money(detail.value, hidden), style = MaterialTheme.typography.headlineLarge)
                MetricRow("Количество", if (hidden) "••••" else detail.quantity?.toPlainString() ?: NO_POSITION_DATA)
                MetricRow("Текущая цена", if (detail.currency == null) NO_POSITION_DATA else money(detail.price, hidden, detail.currency.uppercase()))
                MetricRow("Доля портфеля", if (hidden) "••••" else detail.share?.let { "$it %" } ?: NO_POSITION_DATA)
                MetricRow("Блокировка", if (detail.blocked) "Есть ограничение брокера" else "В снимке не отмечена")
                SelectionContainer { Text("Тикер: ${detail.ticker}\nИдентификатор: ${detail.uid}", style = MaterialTheme.typography.bodySmall) }
                Text(timestampLabel(portfolio.capturedAt), style = MaterialTheme.typography.bodySmall)
                Text(statusLabel(portfolio.freshness), style = MaterialTheme.typography.bodySmall)
            }
        }
        item { BrokerInstrumentAction(detail) }
        item { SourcesCard(portfolio.sources) }
    }
}

@Composable
private fun BrokerInstrumentAction(position: PortfolioPosition) {
    val uri = LocalUriHandler.current
    var unavailable by remember(position.uid) { mutableStateOf(false) }
    val link = brokerInstrumentUrl(position)
    OmniCard {
        if (link != null) OutlinedButton(onClick = { unavailable = runCatching { uri.openUri(link) }.isFailure }) {
            Text("Открыть в Т-Инвестициях")
        }
        if (link == null || unavailable) Text("Карточка недоступна. Скопируйте тикер долгим нажатием и найдите инструмент в Т-Инвестициях.")
        Text("Android откроет приложение брокера или его сайт. Проверьте название инструмента; переход не означает совершение сделки.",
            style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun PositionCard(position: PortfolioPosition, hidden: Boolean, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
        Surface(shape = androidx.compose.foundation.shape.CircleShape,
            color = MaterialTheme.colorScheme.secondaryContainer) {
            Box(Modifier.size(42.dp), contentAlignment = Alignment.Center) {
                Text(position.ticker.take(2).ifBlank { "•" }, style = MaterialTheme.typography.titleMedium)
            }
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(position.name.ifBlank { position.ticker.ifBlank { "Инструмент" } },
                style = MaterialTheme.typography.titleMedium, maxLines = 2)
            Text(if (hidden) "Количество скрыто" else
                "${position.quantity?.stripTrailingZeros()?.toPlainString() ?: "—"} шт. · ${position.ticker}",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (position.blocked) Text("Ограничение брокера", style = MaterialTheme.typography.bodySmall)
        }
        Column(horizontalAlignment = Alignment.End, verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(money(position.value, hidden), style = MaterialTheme.typography.titleMedium)
            if (!hidden && position.share != null) Text("${position.share.stripTrailingZeros().toPlainString()} %",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}
