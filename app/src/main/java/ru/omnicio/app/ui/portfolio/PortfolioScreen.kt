package ru.omnicio.app.ui.portfolio

import ru.omnicio.app.ui.spectrum.SpectrumAlertDialog as AlertDialog

import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton

import ru.omnicio.app.ui.spatial.SpatialBackHandler as BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.ExperimentalSharedTransitionApi
import androidx.compose.animation.SharedTransitionLayout
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.animation.core.tween
import kotlinx.coroutines.launch
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.runtime.saveable.Saver
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.ui.workspace.*
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette
import ru.omnicio.app.ui.spectrum.SpectrumBackground
import ru.omnicio.app.ui.spectrum.SpectrumCard
import ru.omnicio.app.ui.spectrum.SpectrumSymbol
import ru.omnicio.app.ui.spectrum.SpectrumTextButton

private const val OperationsTitle = "Операции"
private const val AnalyticsTitle = "Аналитика"
private const val CashTitle = "Денежные средства"

private val PositionSelectionSaver = Saver<PositionSelection?, List<String>>(
    save = { it?.let { value -> listOf(value.accountId, value.positionId, value.virtual.toString()) } ?: emptyList() },
    restore = { if (it.size == 3) PositionSelection(it[0], it[1], it[2].toBooleanStrictOrNull() ?: false) else null },
)

private fun matchingPositions(accounts: List<PortfolioAccount>, positionId: String, accountId: String?): List<PositionSelection> =
    accounts.filter { accountId == null || it.id == accountId }.flatMap { account ->
        account.positions.filter { it.id == positionId }.map { PositionSelection(account.id, it.id) }
    }

@Composable
@OptIn(ExperimentalSharedTransitionApi::class)
fun PortfolioScreen(
    state: PortfolioUiState,
    onProfileClick: () -> Unit,
    selectedCurrency: PortfolioCurrency = PortfolioCurrency.RUB,
    modifier: Modifier = Modifier,
    accessToken: String = "",
    refreshing: Boolean = false,
    refreshError: String? = null,
    lastUpdatedMillis: Long? = null,
    onConnect: () -> Unit = onProfileClick,
    destination: PortfolioDestination? = null,
    onDestinationConsumed: () -> Unit = {},
    initialPositionId: String? = null,
    initialHistoryDate: String? = null,
    initialHistoryStart: String? = null,
    initialHistoryEnd: String? = null,
    initialHistoryResolution: String? = null,
) {
    var accountId by rememberSaveable { mutableStateOf<String?>(null) }
    var section by rememberSaveable { mutableIntStateOf(0) }
    var overviewSection by rememberSaveable { mutableIntStateOf(1) }
    var assetQuery by rememberSaveable { mutableStateOf("") }
    var assetSector by rememberSaveable { mutableStateOf<String?>(null) }
    var assetKind by rememberSaveable { mutableStateOf<String?>(null) }
    var assetAccountId by rememberSaveable { mutableStateOf<String?>(null) }
    var historyDate by rememberSaveable(initialHistoryDate) { mutableStateOf(initialHistoryDate) }
    var historyStart by rememberSaveable(initialHistoryStart) { mutableStateOf(initialHistoryStart) }
    var historyEnd by rememberSaveable(initialHistoryEnd) { mutableStateOf(initialHistoryEnd) }
    var historyResolution by rememberSaveable(initialHistoryResolution) { mutableStateOf(initialHistoryResolution) }
    var operationId by rememberSaveable { mutableStateOf<String?>(null) }
    var operationDate by rememberSaveable { mutableStateOf<String?>(null) }
    var operationRequestKey by rememberSaveable { mutableIntStateOf(0) }
    var routeError by rememberSaveable { mutableStateOf<String?>(null) }
    var selectForSection by rememberSaveable { mutableStateOf<Int?>(null) }
    var positionDetails by rememberSaveable(accessToken, stateSaver = PositionSelectionSaver) { mutableStateOf<PositionSelection?>(null) }
    val snapshot = (state as? PortfolioUiState.Ready)?.snapshot
    val account = snapshot?.accounts?.firstOrNull { it.id == accountId }
    val listState = rememberLazyListState()
    val listScope = rememberCoroutineScope()
    var initialPositionHandled by rememberSaveable(initialPositionId) { mutableStateOf(false) }
    LaunchedEffect(initialPositionId, snapshot) {
        if (!initialPositionHandled && initialPositionId != null && snapshot != null) {
            val candidates = matchingPositions(snapshot.accounts, initialPositionId, destination?.accountId)
            if (candidates.size == 1) positionDetails = candidates.single()
            else { assetQuery = initialPositionId; accountId = null; overviewSection = 1 }
            initialPositionHandled = true
        }
    }
    LaunchedEffect(destination, snapshot?.accounts?.map { it.id }) {
        destination?.let { target ->
            when {
                target.operationId != null -> {
                val accounts = snapshot?.accounts ?: return@LaunchedEffect
                operationId = target.operationId; operationDate = target.operationDate
                operationRequestKey++
                val targetAccount = accounts.firstOrNull { it.id == target.accountId }
                when {
                    targetAccount != null -> { accountId = targetAccount.id; section = 1 }
                    target.accountId != null -> { routeError = "Счёт этой операции отсутствует в текущем подтверждённом снимке. Операцию другого счёта не подставляем."; operationId = null; operationDate = null }
                    accounts.size == 1 -> { accountId = accounts.single().id; section = 1 }
                    else -> selectForSection = 1
                }
            }
                target.query.isNotBlank() -> {
                val accounts = snapshot?.accounts ?: return@LaunchedEffect
                val exact = matchingPositions(accounts, target.query, target.accountId)
                assetQuery = target.query; assetSector = target.sector; assetKind = target.kind; assetAccountId = target.accountId
                accountId = null; overviewSection = 1
                if (exact.size == 1) positionDetails = exact.single()
            }
                target.section > 2 -> {
                val accounts = snapshot?.accounts ?: return@LaunchedEffect
                if (target.accountId == null && accounts.size > 1) selectForSection = target.section
                else { accountId = target.accountId ?: accounts.firstOrNull()?.id; section = target.section }
            }
                else -> {
                overviewSection = target.section; accountId = target.accountId
                if (target.accountId != null) section = target.section
                assetQuery = target.query; assetSector = target.sector; assetKind = target.kind; assetAccountId = null
            }
            }
            onDestinationConsumed()
        }
    }
    BackHandler(accountId != null && positionDetails == null) { accountId = null; section = 0 }
    BackHandler(positionDetails != null) { positionDetails = null }

    PortfolioTransition(positionDetails, snapshot, modifier, { positionDetails = null }) {
        SpectrumBackground(modifier.fillMaxSize()) {
                Scaffold(
                    modifier = Modifier.fillMaxSize(),
                    containerColor = Color.Transparent,
                    contentWindowInsets = WindowInsets.safeDrawing,
                    bottomBar = { AnalystBottomBar(AnalystTab.Portfolio, { accountId = null }, onProfileClick) },
                ) { insets ->
                    if (account != null) {
                        AccountScreen(account, accessToken, section, { section = it },
                            { accountId = null; section = 0 }, snapshot.asOf, refreshError,
                            Modifier.padding(insets).consumeWindowInsets(insets), snapshot.accounts,
                            { accountId = it; operationId = null; operationDate = null }, { positionDetails = it }, historyDate,
                            { date -> historyDate = date; historyStart = null; historyEnd = null; historyResolution = null; section = 3 },
                            historyStart = historyStart, historyEnd = historyEnd, historyResolution = historyResolution,
                            initialOperationId = operationId, initialOperationDate = operationDate, operationRequestKey = operationRequestKey)
                    } else {
                        PortfolioDashboard(
                            state = state,
                            selectedCurrency = selectedCurrency,
                            refreshing = refreshing,
                            refreshError = refreshError,
                            lastUpdatedMillis = lastUpdatedMillis,
                            accessToken = accessToken,
                            selectedSection = overviewSection,
                            onSelectSection = { overviewSection = it; listScope.launch { listState.scrollToItem(0) } },
                            listState = listState,
                            onProfileClick = onConnect,
                            assetQuery = assetQuery, assetSector = assetSector, assetKind = assetKind, assetAccountId = assetAccountId,
                            onOpenAccount = { accountId = it.id; section = 0 },
                            onOpenSection = { target ->
                                if (snapshot?.accounts?.size == 1) {
                                    accountId = snapshot.accounts.first().id
                                    section = target
                                } else selectForSection = target
                            },
                            onPositionClick = { id, position -> positionDetails = PositionSelection(id, position.id) },
                            modifier = Modifier.padding(insets).consumeWindowInsets(insets),
                        )
                    }
                }
            }
    }
    if (selectForSection != null && snapshot != null) {
        AlertDialog(onDismissRequest = { selectForSection = null }, title = { Text("Выберите счёт") },
            containerColor = LocalSpectrumPalette.current.card,
            text = { Column { snapshot.accounts.forEach { item ->
                TextButton(onClick = { accountId = item.id; section = selectForSection ?: 0; selectForSection = null }) { Text(item.name) }
            } } }, confirmButton = { TextButton(onClick = { selectForSection = null }) { Text("Отмена") } })
    }
    routeError?.let { message -> AlertDialog(onDismissRequest = { routeError = null }, title = { Text("Ссылка на операцию") },
        text = { Text(message) }, confirmButton = { TextButton(onClick = { routeError = null }) { Text("Закрыть") } }) }
}

@Composable
private fun LivePositionDetails(selection: PositionSelection?, accounts: List<PortfolioAccount>?, embedded: Boolean = false, close: () -> Unit) {
    if (selection == null) return
    val position = resolveSelectedPosition(selection, accounts, PortfolioAccount::id,
        { account, virtual -> if (virtual) account.virtualPositions else account.positions }, PortfolioPosition::id)
    if (position != null) {
        InstrumentDetailsScreen(position, close, accounts?.firstOrNull { it.id == selection.accountId }?.name,
            embedded = embedded, sharedKey = "${selection.accountId}:${selection.positionId}", accountId = selection.accountId)
    } else {
        AlertDialog(onDismissRequest = close, containerColor = LocalSpectrumPalette.current.card,
            title = { Text("Данные позиции изменились") },
            text = { Text("Эта позиция больше не найдена однозначно в текущих данных счёта. Старую цену и количество не показываем. Это само по себе не подтверждает продажу бумаги.") },
            confirmButton = { TextButton(onClick = close) { Text("Закрыть") } })
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
private fun AccountScreen(
    account: PortfolioAccount, token: String, section: Int, onSection: (Int) -> Unit,
    onBack: () -> Unit, asOf: String?, error: String?, modifier: Modifier,
    accounts: List<PortfolioAccount>, onAccount: (String) -> Unit, onPosition: (PositionSelection) -> Unit,
    initialHistoryDate: String? = null,
    onHistory: (String) -> Unit = {},
    historyStart: String? = null,
    historyEnd: String? = null,
    historyResolution: String? = null,
    initialOperationId: String? = null,
    initialOperationDate: String? = null,
    operationRequestKey: Int = 0,
) {
    Column(modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            SpectrumTextButton("Назад", onBack, symbol = SpectrumSymbol.Back)
            AccountSelector(accounts, account.id, onAccount, Modifier.weight(1f))
        }
        Box(Modifier.padding(horizontal = 20.dp)) { ChoiceRow(listOf("Обзор", OperationsTitle, "Заявки", AnalyticsTitle, "Выплаты"), section, onSection) }
        when (section) {
            1 -> key(account.id, operationRequestKey) { AccountOperations(token, account, onPosition, onHistory, initialOperationId, initialOperationDate) }
            2 -> AccountOrders(token, account)
            3 -> AccountAnalytics(token, account, initialDate = initialHistoryDate,
                initialStart = historyStart, initialEnd = historyEnd, initialResolution = historyResolution)
            4 -> AccountPayments(token, account)
            else -> AccountOverview(account, onSection, asOf, error, onPosition)
        }
    }
}

@Composable
private fun AccountOverview(account: PortfolioAccount, onSection: (Int) -> Unit, asOf: String?, error: String?, onPosition: (PositionSelection) -> Unit) {
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
        item(key = "value") {
            SpectrumCard(emphasized = true) {
                Text("Капитал счёта", color = LocalSpectrumPalette.current.cyan, style = MaterialTheme.typography.labelLarge)
                CurrencyChoice(account.totalValue.currency)
                Text(account.totalValue.moneyText(),
                    fontWeight = FontWeight.Bold, style = MaterialTheme.typography.headlineLarge)
                DataRow("Текущая доходность брокера", account.expectedYieldPercent.percentText())
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
            PositionLine(position, total = account.totalValue, sharedKey = "${account.id}:${position.id}") { onPosition(PositionSelection(account.id, position.id)) }
        }
        if (account.positions.isEmpty()) item { Notice("Позиции отсутствуют") }
        if (account.virtualPositions.isNotEmpty()) item { DetailFold("Виртуальные позиции (${account.virtualPositions.size})") {
            account.virtualPositions.forEach { position ->
                PositionLine(position, total = account.totalValue, sharedKey = "${account.id}:${position.id}") { onPosition(PositionSelection(account.id, position.id, virtual = true)) }
            }
        } }
        item { CompactCard { SectionHeading("Баланс активов"); AccountStructure(account) } }
        item {
            CompactCard {
                DetailFold("Сведения о счёте") {
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
    }
}

@Composable
internal fun AssetStructure(allocations: List<PortfolioAllocation>, total: MoneyAmount) {
    val destination = LocalPortfolioDestination.current
    var unlinked by remember { mutableStateOf<String?>(null) }
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
    } else StructureChart(slices, total.moneyText(), "По классам активов") { title ->
        val kind = allocationKind(title)
        if (kind != null) destination(PortfolioDestination(kind = kind)) else unlinked = title
    }
    unlinked?.let { Notice("Категория «$it» не сопоставлена с отдельными позициями в ответе API. Её состав не выводится из остатка диаграммы.") }
}

internal fun allocationKind(title: String): String? = when (title) {
    "Акции" -> "share"; "Облигации" -> "bond"; "Фонды" -> "etf"; "Валюта и деньги", "Деньги", "Валюта" -> "cash"
    "Фьючерсы" -> "futures"; "Опционы" -> "option"; "Прочие активы" -> "other"
    else -> null
}

@Composable
internal fun AccountStructure(account: PortfolioAccount) {
    var mode by rememberSaveable(account.id) { mutableIntStateOf(0) }
    var selectedGroup by rememberSaveable(account.id, mode) { mutableStateOf<String?>(null) }
    val destination = LocalPortfolioDestination.current
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
        if (mode == 3) "Валюта оценки позиций" else "По доступным данным позиций") { selectedGroup = it }
    selectedGroup?.let { group ->
        DetailFold("Состав: $group", initiallyOpen = true) {
            groups[group].orEmpty().forEach { position ->
                PositionLine(position, account.totalValue, sharedKey = "${account.id}:${position.id}") {
                    destination(PortfolioDestination(accountId = account.id, query = position.id))
                }
            }
        }
    }
    if (mode == 1) Notice("Группировка по названиям инструментов/компаний API; единая структура эмитентов для всех типов активов ещё уточняется.")
}

@Composable
@OptIn(ExperimentalSharedTransitionApi::class)
private fun PortfolioTransition(positionDetails: PositionSelection?, snapshot: PortfolioSnapshot?,
    modifier: Modifier, onCloseDetails: () -> Unit, content: @Composable () -> Unit) {
    val savedPages = rememberSaveableStateHolder()
    val motionDuration = portfolioMotionDuration(180, 80)
    SharedTransitionLayout(modifier.fillMaxSize()) {
        AnimatedContent(positionDetails, transitionSpec = { fadeIn(tween(motionDuration)) togetherWith fadeOut(tween(motionDuration)) },
            label = "portfolio-instrument-transition") { detail ->
        CompositionLocalProvider(LocalInstrumentTransition provides InstrumentTransition(this@SharedTransitionLayout, this@AnimatedContent)) {
        savedPages.SaveableStateProvider(detail?.let { "${it.accountId}:${it.positionId}" } ?: "portfolio") {
        if (detail != null) {
            LivePositionDetails(detail, snapshot?.accounts, embedded = true) { onCloseDetails() }
        } else {
        content()
        }
        }
        }
        }
        }
}
