package ru.omnicio.app.ui.portfolio

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette
import ru.omnicio.app.ui.spectrum.SpectrumBackground

private const val OperationsTitle = "Операции"
private const val AnalyticsTitle = "Аналитика"
private const val CashTitle = "Денежные средства"

@Composable
fun PortfolioScreen(
    state: PortfolioUiState,
    onProfileClick: () -> Unit,
    selectedCurrency: PortfolioCurrency = PortfolioCurrency.RUB,
    onCurrencyClick: () -> Unit = {},
    modifier: Modifier = Modifier,
    accessToken: String = "",
    refreshing: Boolean = false,
    refreshError: String? = null,
    lastUpdatedMillis: Long? = null,
) {
    var accountId by rememberSaveable { mutableStateOf<String?>(null) }
    var section by rememberSaveable { mutableIntStateOf(0) }
    var selectForSection by remember { mutableStateOf<Int?>(null) }
    var positionDetails by remember { mutableStateOf<PortfolioPosition?>(null) }
    val snapshot = (state as? PortfolioUiState.Ready)?.snapshot
    val account = snapshot?.accounts?.firstOrNull { it.id == accountId }
    val listState = rememberLazyListState()
    BackHandler(accountId != null) { accountId = null; section = 0 }

    SpectrumBackground(modifier.fillMaxSize()) {
        Scaffold(Modifier.fillMaxSize(), containerColor = Color.Transparent,
            contentWindowInsets = WindowInsets.safeDrawing,
            bottomBar = { AnalystBottomBar(AnalystTab.Portfolio, { accountId = null }, onProfileClick) },
        ) { insets ->
            if (account != null) {
                AccountScreen(account, accessToken, section, { section = it }, onCurrencyClick,
                    { accountId = null; section = 0 }, snapshot.asOf, refreshError,
                    Modifier.padding(insets))
            } else {
                LazyColumn(Modifier.fillMaxSize().padding(insets), state = listState,
                    contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    item(key = "header") {
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                            Column {
                                Notice("Analyst AI")
                                Text("Портфель", fontSize = 32.sp, fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                    if (snapshot == null) {
                        item(key = "initial-state") { InitialPortfolioState(state, onProfileClick) }
                    } else {
                        item(key = "total") {
                            PortfolioSummary(snapshot, selectedCurrency, refreshing, refreshError, lastUpdatedMillis, onCurrencyClick) { target ->
                                if (snapshot.accounts.size == 1) {
                                    accountId = snapshot.accounts.first().id
                                    section = target
                                } else selectForSection = target
                            }
                        }
                        if (snapshot.accounts.isEmpty()) {
                            item(key = "no-accounts") { CompactCard { Text("Доступных счетов не найдено") } }
                        }
                        items(snapshot.accounts, key = { "account:${it.id}" }) { item ->
                            AccountPreviewCard(item,
                                onOpen = { accountId = item.id; section = 0 },
                                onSection = { target -> accountId = item.id; section = target },
                                onPosition = { positionDetails = it })
                        }
                        item(key = "structure") {
                            CompactCard {
                                SectionHeading("Структура портфеля")
                                AssetStructure(snapshot.allocations, snapshot.totalValue)
                            }
                        }
                        if (snapshot.warnings.isNotEmpty()) {
                            item(key = "warnings") { Notice(snapshot.warnings.joinToString("\n")) }
                        }
                    }
                }
            }
        }
    }
    positionDetails?.let { PositionDetails(it) { positionDetails = null } }
    if (selectForSection != null && snapshot != null) {
        AlertDialog(onDismissRequest = { selectForSection = null }, title = { Text("Выберите счёт") },
            containerColor = LocalSpectrumPalette.current.card,
            text = { Column(Modifier.verticalScroll(rememberScrollState())) { snapshot.accounts.forEach { item ->
                TextButton(onClick = { accountId = item.id; section = selectForSection ?: 0; selectForSection = null }) { Text(item.name) }
            } } }, confirmButton = { TextButton(onClick = { selectForSection = null }) { Text("Отмена") } })
    }
}

@Composable
private fun AccountPreviewCard(
    account: PortfolioAccount, onOpen: () -> Unit,
    onSection: (Int) -> Unit, onPosition: (PortfolioPosition) -> Unit,
) {
    CompactCard {
        AccountSummaryHeading(account, onOpen)
        account.positions.take(5).forEach { position -> PositionLine(position) { onPosition(position) } }
        if (account.positions.size > 5 || account.virtualPositions.isNotEmpty()) {
            TextButton(onClick = onOpen, modifier = Modifier.heightIn(min = 48.dp)) {
                Text("Все позиции (${account.positions.size})")
            }
        }
        if (account.positions.isEmpty()) Notice("Позиции отсутствуют")
        PortfolioShortcuts(onSection = onSection)
    }
}

@Composable
private fun PortfolioShortcuts(onSection: (Int) -> Unit, enabled: Boolean = true) {
    val fontScale = LocalDensity.current.fontScale
    val choices = listOf(OperationsTitle to 1, AnalyticsTitle to 3)
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        if (portfolioStackedLayout(maxWidth.value, fontScale)) {
            Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                choices.forEach { (title, target) ->
                    FilledTonalButton(onClick = { onSection(target) }, enabled = enabled,
                        modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text(title) }
                }
            }
        } else {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                choices.forEach { (title, target) ->
                    FilledTonalButton(onClick = { onSection(target) }, enabled = enabled,
                        modifier = Modifier.weight(1f).heightIn(min = 48.dp)) { Text(title) }
                }
            }
        }
    }
}

@Composable
private fun ReturnSummaryRow(title: String, amount: MoneyAmount?, percent: ApiDecimal?) {
    val fontScale = LocalDensity.current.fontScale
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        if (portfolioStackedLayout(maxWidth.value, fontScale)) {
            Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(title, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
                SignedAmount(amount, percent)
            }
        } else {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.Top) {
                Text(title, modifier = Modifier.weight(1f), color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodyMedium)
                Box(Modifier.weight(1f), contentAlignment = Alignment.TopEnd) { SignedAmount(amount, percent) }
            }
        }
    }
}

@Composable
private fun AccountSummaryHeading(account: PortfolioAccount, open: () -> Unit) {
    val fontScale = LocalDensity.current.fontScale
    BoxWithConstraints(Modifier.fillMaxWidth().heightIn(min = 48.dp).clickable(role = Role.Button, onClick = open)) {
        if (portfolioStackedLayout(maxWidth.value, fontScale)) {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                AccountHeadingText(account)
                account.expectedYieldPercent?.let { SignedAmount(null, it) }
            }
        } else {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.Top) {
                Column(Modifier.weight(1f)) { AccountHeadingText(account) }
                account.expectedYieldPercent?.let { SignedAmount(null, it) }
            }
        }
    }
}

@Composable
private fun AccountHeadingText(account: PortfolioAccount) {
    Text(account.totalValue.moneyText(), fontSize = 23.sp, fontWeight = FontWeight.Bold)
    Text(account.name + " ›", style = MaterialTheme.typography.bodyLarge)
}

@Composable
private fun AccountScreen(
    account: PortfolioAccount, token: String, section: Int, onSection: (Int) -> Unit,
    onCurrency: () -> Unit, onBack: () -> Unit, asOf: String?, error: String?, modifier: Modifier,
) {
    Column(modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = onBack) { Text("‹ Назад") }
            Text(account.name, Modifier.weight(1f), fontWeight = FontWeight.SemiBold)
        }
        Box(Modifier.padding(horizontal = 16.dp)) { ChoiceRow(listOf("Обзор", OperationsTitle, "Заявки", AnalyticsTitle, "Выплаты"), section, onSection) }
        when (section) {
            1 -> AccountOperations(token, account)
            2 -> AccountOrders(token, account)
            3 -> AccountAnalytics(token, account, onCurrency)
            4 -> AccountPayments(token, account)
            else -> AccountOverview(account, onCurrency, onSection, asOf, error)
        }
    }
}

@Composable
private fun AccountOverview(account: PortfolioAccount, onCurrency: () -> Unit, onSection: (Int) -> Unit, asOf: String?, error: String?) {
    var selected by remember { mutableStateOf<PortfolioPosition?>(null) }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item(key = "value") {
            CompactCard {
                Text(account.totalValue.moneyText(), Modifier.heightIn(min = 48.dp).clickable(role = Role.Button, onClick = onCurrency), fontWeight = FontWeight.Bold, fontSize = 30.sp)
                DataRow("Текущая доходность API", account.expectedYieldPercent.percentText())
                ReturnSummaryRow("За день", account.dailyYieldAmount, account.dailyYieldPercent)
                Notice(error ?: "Получено ${dateText(asOf)} · автообновление")
                if (account.limitsLoading) Notice("Брокер ещё обновляет лимиты. Данные могут измениться.")
                Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TextButton(onClick = { onSection(1) }) { Text(OperationsTitle) }
                    TextButton(onClick = { onSection(3) }) { Text(AnalyticsTitle) }
                    TextButton(onClick = { onSection(4) }) { Text("Выплаты") }
                }
            }
        }
        item { SectionHeading("Активы и деньги") }
        items(account.positions, key = { "position:${it.id}" }) { position ->
            Surface(color = LocalSpectrumPalette.current.card, shape = RoundedCornerShape(24.dp),
                border = BorderStroke(1.dp, LocalSpectrumPalette.current.cyan.copy(alpha = 0.24f))) {
                Box(Modifier.padding(horizontal = 12.dp)) { PositionLine(position) { selected = position } }
            }
        }
        if (account.positions.isEmpty()) item { Notice("Позиции отсутствуют") }
        if (account.virtualPositions.isNotEmpty()) {
            item { SectionHeading("Виртуальные позиции") }
            items(account.virtualPositions, key = { "virtual:${it.id}" }) { position -> PositionLine(position) { selected = position } }
        }
        item {
            CompactCard { SectionHeading("Структура портфеля"); AccountStructure(account) }
        }
        item {
            CompactCard {
                SectionHeading("Сведения о счёте")
                DataRow("Название", account.name)
                DataRow("Идентификатор", account.id)
                DataRow("Открыт", dateText(account.openedAt, "dd.MM.yyyy"))
                DataRow("Тип", when (account.accountType) {
                    "ACCOUNT_TYPE_TINKOFF_IIS" -> "ИИС"
                    "ACCOUNT_TYPE_INVEST_BOX" -> "Инвесткопилка"
                    else -> "Брокерский счёт"
                })
                Notice("Доступ только для чтения. Пополнение, вывод и торговые поручения выполняются в приложении брокера.")
            }
        }
    }
    selected?.let { PositionDetails(it) { selected = null } }
}

@Composable
internal fun AssetStructure(allocations: List<PortfolioAllocation>, total: MoneyAmount) {
    if (total.value.toBigDecimal().signum() <= 0 || allocations.any { it.sharePercent.toBigDecimal().signum() < 0 }) {
        allocations.forEach { DataRow(it.title, it.sharePercent.percentText()) }
        Notice("Круговая диаграмма не используется для нулевой стоимости или отрицательных долей.")
        return
    }
    val slices = allocations.map { ChartSlice(it.title, it.sharePercent.toBigDecimal().toFloat()) }.toMutableList()
    val missing = 100f - slices.sumOf { it.weight.toDouble() }.toFloat()
    if (missing > 0.1f) slices += ChartSlice("Прочее / не распределено API", missing)
    if (missing < -0.1f) {
        allocations.forEach { DataRow(it.title, it.sharePercent.percentText()) }
        Notice("Сумма долей превышает 100%; показаны значения API без нормализации.")
    } else StructureChart(slices, total.moneyText(), "По классам активов")
}

@Composable
internal fun AccountStructure(account: PortfolioAccount) {
    var mode by rememberSaveable(account.id) { mutableIntStateOf(0) }
    ChoiceRow(listOf("Активы", "Компании", "Отрасли", "Валюта"), mode) { mode = it }
    if (mode == 0) { AssetStructure(account.allocations, account.totalValue); return }
    val positions = account.positions
    val currencies = positions.mapNotNull { it.currentValue?.currency }.distinct()
    if (currencies.size != 1 || positions.any { it.currentValue == null || it.currentValue.value.toBigDecimal().signum() < 0 }) {
        Notice("Для общей диаграммы не хватает сопоставимой оценки всех позиций в одной валюте. Несопоставимые суммы не складываются.")
        positions.groupBy { when (mode) {
            1 -> if (it.instrumentType == "cash") CashTitle else it.company ?: it.title
            2 -> if (it.instrumentType == "cash") CashTitle else it.sector ?: "Отрасль не указана"
            else -> it.currentValue?.currency ?: "Валюта не определена"
        } }.forEach { (title, rows) ->
            Text(title, fontWeight = FontWeight.SemiBold)
            rows.forEach { DataRow(it.ticker ?: it.title, it.currentValue.moneyText()) }
        }
        return
    }
    val groups = positions.groupBy { when (mode) {
        1 -> if (it.instrumentType == "cash") CashTitle else it.company ?: it.title
        2 -> if (it.instrumentType == "cash") CashTitle else it.sector ?: "Отрасль не указана"
        else -> it.currentValue?.currency ?: "Не определена"
    } }
    val totals = groups.mapValues { (_, rows) -> rows.sumOf { it.currentValue!!.value.toBigDecimal() } }
    val total = totals.values.fold(java.math.BigDecimal.ZERO, java.math.BigDecimal::add)
    StructureChart(totals.map { ChartSlice(it.key, it.value.toFloat()) }, decimalText(total) + " " + currencySymbol(currencies.first()),
        if (mode == 3) "Валюта оценки позиций" else "По доступным данным позиций")
    if (mode == 1) Notice("Группировка по названиям инструментов/компаний API; единая структура эмитентов для всех типов активов ещё уточняется.")
}


@Composable
private fun InitialPortfolioState(state: PortfolioUiState, onProfile: () -> Unit) {
    CompactCard {
        when (state) {
            PortfolioUiState.Loading -> {
                CircularProgressIndicator(Modifier.size(24.dp), strokeWidth = 2.dp)
                Text("Получаем ваш портфель…")
            }
            is PortfolioUiState.Error -> {
                Text(state.message)
                Notice("Повторная проверка выполняется автоматически, пока приложение открыто.")
            }
            else -> {
                SectionHeading("Подключите T‑API")
                Notice("Счета и позиции появятся после подключения вашего read-only токена. Демонстрационных сумм здесь нет.")
                TextButton(onClick = onProfile) { Text("Открыть профиль") }
            }
        }
    }
}

@Composable
private fun PortfolioSummary(
    snapshot: PortfolioSnapshot, selectedCurrency: PortfolioCurrency, refreshing: Boolean,
    error: String?, lastUpdatedMillis: Long?, onCurrency: () -> Unit, openSection: (Int) -> Unit,
) {
    CompactCard {
        Text(snapshot.totalValue.moneyText(), Modifier.heightIn(min = 48.dp).clickable(role = Role.Button, onClick = onCurrency), fontSize = 32.sp, fontWeight = FontWeight.Bold)
        snapshot.expectedYieldPercent?.let {
            ReturnSummaryRow("Текущая доходность API", null, it)
        }
        val waiting = refreshing && snapshot.totalValue.currency != selectedCurrency.name
        Notice(if (waiting) "Получаем оценку в ${selectedCurrency.name}…" else "Нажмите на сумму: ₽ → $ → €")
        PortfolioShortcuts(onSection = openSection, enabled = snapshot.accounts.isNotEmpty())
        val observed = snapshot.asOf ?: lastUpdatedMillis?.let { java.time.Instant.ofEpochMilli(it).toString() }
        Notice(error ?: "Получено ${dateText(observed)} · автообновление")
    }
}
