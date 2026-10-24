package ru.omnicio.app.ui.home

import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.pulltorefresh.rememberPullToRefreshState
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.backend.AnalystUser
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.data.market.rememberWorkspaceRequest
import ru.omnicio.app.data.workspace.PersonalWorkspaceController
import ru.omnicio.app.data.market.WorkspaceRequest
import androidx.compose.foundation.lazy.LazyItemScope
import ru.omnicio.app.data.workspace.rememberPersonalWorkspace
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.portfolio.*
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.theme.LocalSpectrumMotionPreference
import ru.omnicio.app.ui.workspace.*

/** A decision workspace: capital, next destination and actual allocation. */
@Composable
@OptIn(ExperimentalFoundationApi::class, ExperimentalMaterial3Api::class)
fun HomeScreen(user: AnalystUser, state: PortfolioUiState, selectedCurrency: PortfolioCurrency,
    refreshing: Boolean, refreshError: String?, lastUpdatedMillis: Long?, onCurrencyClick: () -> Unit,
    onOpenPortfolio: () -> Unit, onOpenRecommendations: () -> Unit, onOpenRisk: () -> Unit,
    onOpenMessages: () -> Unit, onOpenProfile: () -> Unit,
    modifier: Modifier = Modifier, onConnect: () -> Unit = onOpenProfile,
    onOpenPayments: () -> Unit = onOpenPortfolio) {
    val snapshot = (state as? PortfolioUiState.Ready)?.snapshot
    val waiting = state == PortfolioUiState.Loading || state == PortfolioUiState.ApiConnected
    val prefs = LocalWorkspacePreferences.current.value
    val itemMotion = prefs.motion != MotionLevel.OFF && android.animation.ValueAnimator.areAnimatorsEnabled()
    val itemDuration = if (prefs.motion == MotionLevel.SUBDUED) 100 else 220
    val navigate = LocalWorkspaceNavigator.current
    val personal = rememberPersonalWorkspace()
    val listState = rememberLazyListState()
    var collapsed by rememberSaveable { mutableStateOf(false) }
    var editing by rememberSaveable { mutableStateOf(false) }
    var previewOrder by rememberSaveable { mutableStateOf<List<String>?>(null) }
    var savingOrder by rememberSaveable { mutableStateOf<List<String>?>(null) }
    var undoOrder by rememberSaveable { mutableStateOf<List<String>?>(null) }
    val savedOrder = normalizedDashboardOrder(personal.dashboardOrder)
    val order = previewOrder ?: savedOrder
    LaunchedEffect(personal.dashboardOrder, savingOrder) {
        if (savingOrder != null && savedOrder == savingOrder) { savingOrder = null; previewOrder = null; editing = false }
    }
    val attributionToday = remember { java.time.LocalDate.now(ru.omnicio.app.ui.portfolio.Moscow) }
    var attributionStart by rememberSaveable { mutableStateOf<String?>(attributionToday.minusMonths(1).toString()) }
    var attributionEnd by rememberSaveable { mutableStateOf<String?>(attributionToday.toString()) }
    val attributionPeriod = PortfolioPeriod(attributionStart, attributionEnd)
    val workspace = rememberWorkspaceRequest(parameters = attributionPeriod.parameters() + ("currency" to selectedCurrency.name),
        refreshKey = LocalWorkspaceRefreshKey.current)
    val refresh = LocalPortfolioRefresh.current
    val pullState = rememberPullToRefreshState()
    var requested by remember { mutableStateOf(false) }
    var sawLoading by remember { mutableStateOf(false) }
    var beforeRefresh by remember { mutableStateOf<String?>(null) }
    var refreshMessage by remember { mutableStateOf<String?>(null) }
    val refreshNow = {
        if (!refreshing) { beforeRefresh = financialFingerprint(snapshot); requested = true; sawLoading = false; refreshMessage = null; refresh() }
    }
    LaunchedEffect(refreshing, refreshError, snapshot, requested) {
        if (requested && refreshing) sawLoading = true
        if (requested && !refreshing && (sawLoading || refreshError != null)) {
            refreshMessage = when {
                refreshError != null -> "Обновление не завершено: $refreshError"
                financialFingerprint(snapshot) == beforeRefresh -> "Проверено: новых значений в портфеле нет"
                else -> "Портфель обновлён по данным брокера"
            }
            requested = false; workspace.refresh()
        }
    }
    SpectrumBackground(modifier.fillMaxSize()) {
        Scaffold(containerColor = Color.Transparent, contentWindowInsets = WindowInsets.safeDrawing,
            bottomBar = { AnalystBottomBar(AnalystTab.Home, onOpenPortfolio, onOpenProfile) }) { padding ->
            PullToRefreshBox(isRefreshing = refreshing, onRefresh = refreshNow, state = pullState,
                modifier = Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding), indicator = {
                    HomePullIndicator(refreshing, pullState.distanceFraction)
                }) {
            LazyColumn(Modifier.fillMaxSize(), state = listState,
                contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
                stickyHeader(key = "compact-capital") {
                    CompactCapital(snapshot, collapsed, listState.firstVisibleItemIndex > 1, onCurrencyClick) { collapsed = !collapsed }
                }
                item(key = "brand-header") { HomeHeader(user, onOpenMessages) }
                item(key = "portfolio-hero") {
                    HomeCapitalBlock(state, snapshot, selectedCurrency, refreshing, refreshError, lastUpdatedMillis,
                        prefs.hideHomeBalance, collapsed, waiting, refreshMessage, onCurrencyClick, onConnect,
                        refreshNow) { collapsed = !collapsed }
                }
                if (!snapshot?.warnings.isNullOrEmpty()) {
                    item(key = "attention") { HomeWarningCard(checkNotNull(snapshot).warnings) }
                }
                item(key = "capabilities") { HomeQuickActions(onOpenPortfolio, onOpenPayments) }
                if (personal.loaded && !personal.releaseDismissed(ru.omnicio.app.BuildConfig.VERSION_NAME)) item(key = "release-introduction") {
                    SpectrumCard {
                        Text("Что нового в 0.12", style = MaterialTheme.typography.titleMedium)
                        Text("Новый 2D-дизайн, цветные живые иконки и быстрый доступ к ассистенту. Все привычные данные и настройки сохранены.", style = MaterialTheme.typography.bodyMedium)
                        TextButton(onClick = { navigate(WorkspaceRoute.NewFeatures) }) { Text("Посмотреть возможности") }
                        TextButton(onClick = { personal.dismissRelease(ru.omnicio.app.BuildConfig.VERSION_NAME) }, enabled = !personal.busy) { Text("Больше не показывать") }
                    }
                }
                item(key = "order-controls") {
                    HomeOrderControls(personal.loaded, personal.busy, undoOrder != null,
                        previewOrder != null && previewOrder != savedOrder,
                        { previewOrder = savedOrder; editing = true },
                        { undoOrder?.let(personal::saveDashboardOrder); undoOrder = null })
                }
                items(order, key = { "dashboard:$it" }) { key ->
                    HomeAnimatedCard(itemMotion, itemDuration) {
                        HomeDashboardCard(key, state, snapshot, refreshError, waiting, personal, workspace, attributionPeriod,
                            { attributionStart = it.start; attributionEnd = it.end }, onConnect, onOpenRisk,
                            onOpenRecommendations, onOpenPayments, onOpenPortfolio)
                    }
                }
            }
            }
        }
    }
    if (editing) DashboardOrderEditor(order, savedOrder, personal.busy, personal.error,
        onPreview = { previewOrder = it }, onSave = { undoOrder = savedOrder; savingOrder = order; personal.saveDashboardOrder(order) },
        onClose = { editing = false; previewOrder = null })
}

@Composable
private fun HomeHeader(user: AnalystUser, onMessagesClick: () -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        SpectrumBrandOrb(Modifier.size(42.dp), compact = true)
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text("Analyst AI", modifier = Modifier.semantics { contentDescription = user.name?.let { "Analyst AI · $it" } ?: "Analyst AI" },
                style = MaterialTheme.typography.labelLarge, color = LocalSpectrumPalette.current.cyan)
            Text("Ваш капитал", style = MaterialTheme.typography.headlineMedium)
            LiveSyncLabel()
        }
        BadgedBox(badge = { AttentionBadge() }) {
        SpectrumIconButton(SpectrumSymbol.Notifications, "Уведомления", onMessagesClick, Modifier.size(48.dp))
        }
    }
}

@Composable
private fun CapitalHero(state: PortfolioUiState, snapshot: PortfolioSnapshot?, currency: PortfolioCurrency,
    refreshing: Boolean, error: String?, updated: Long?, hidden: Boolean, onCurrency: () -> Unit,
    onConnect: () -> Unit) {
    SpectrumCard(emphasized = true) {
        if (snapshot == null) {
            Text("Всё начинается с вашего счёта", style = MaterialTheme.typography.headlineSmall)
            Text(when (state) {
                PortfolioUiState.NotConnected -> "Подключите портфель Т-Инвестиций"
                is PortfolioUiState.Error -> state.message
                else -> "Получаем счета и позиции…"
            }, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (state == PortfolioUiState.Loading || state == PortfolioUiState.ApiConnected) {
                SpectrumLoadingIndicator(description = "Получаем счета и позиции")
            } else SpectrumPrimaryButton("Подключение счёта", onConnect, Modifier.fillMaxWidth())
        } else {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text("Всего в портфеле", Modifier.weight(1f), color = MaterialTheme.colorScheme.onSurfaceVariant)
                SpectrumTextButton(currency.name, onCurrency, symbol = SpectrumSymbol.Expand)
            }
            InteractiveBalance(snapshot.totalValue, hidden, onCurrency)
            BalanceVisibilityButton()
            if (snapshot.totalValue.currency != currency.name) Text("Показана предыдущая оценка в ${snapshot.totalValue.currency}. Запрошена ${currency.name}.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (!hidden) {
                SignedAmount(snapshot.expectedYieldAmount, snapshot.expectedYieldPercent)
                Text("Текущий результат брокера", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.height(4.dp))
            val observed = snapshot.asOf ?: updated?.let { java.time.Instant.ofEpochMilli(it).toString() }
            Text("Данные: ${relativeObservation(observed)}${if (refreshing) " · обновляем" else ""}",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (error != null) SpectrumBadge("Сохранённые данные · обновление не удалось", accent = MaterialTheme.colorScheme.error)
        }
    }
}

@Composable
internal fun InteractiveBalance(amount: MoneyAmount, hidden: Boolean, onCurrency: () -> Unit) {
    HoldToRevealBalance(amount, hidden, onCurrency)
    Text(if (hidden) "Нажмите для смены валюты. Удерживайте, чтобы увидеть только эту сумму; отпустите, чтобы скрыть." else "Нажмите на сумму: RUB → USD → EUR",
        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    WorkspaceGestureHint("balance-currency", "Валюта одним касанием", "Касание суммы меняет валюту RUB → USD → EUR. Скрытую сумму можно увидеть только на время удержания; настройка приватности сохраняется.")
}

@Composable
internal fun HoldToRevealBalance(amount: MoneyAmount, hidden: Boolean, onCurrency: () -> Unit, modifier: Modifier = Modifier) {
    var revealed by remember { mutableStateOf(false) }
    val active = workspaceForeground()
    val select by rememberUpdatedState(onCurrency)
    LaunchedEffect(active, hidden) { revealed = false }
    val text = if (hidden && !(revealed && active)) "••• •••" else
        "${decimalText(amount.value.toBigDecimal())} ${currencySymbol(amount.currency)}"
    Text(text, style = MaterialTheme.typography.headlineLarge, fontWeight = FontWeight.Bold,
        modifier = modifier.fillMaxWidth().heightIn(min = 56.dp).semantics {
            onClick("Следующая валюта оценки") { select(); true }
        }.pointerInput(hidden, active) {
            detectTapGestures(onTap = { select() }, onLongPress = { if (hidden && active) revealed = true },
                onPress = { try { tryAwaitRelease() } finally { revealed = false } })
        })
}

@Composable
private fun AllocationOverview(snapshot: PortfolioSnapshot, onOpenPortfolio: () -> Unit) {
    SpectrumCard {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text("Распределение", Modifier.weight(1f), style = MaterialTheme.typography.titleLarge)
            SpectrumTextButton("Подробнее", onOpenPortfolio, symbol = SpectrumSymbol.Forward)
        }
        if (LocalWorkspacePreferences.current.value.hideHomeBalance) { Text("Структура скрыта"); return@SpectrumCard }
        AssetStructure(snapshot.allocations, snapshot.totalValue)
        Text("Счетов: ${snapshot.accounts.size}", style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun HomeNextStep(state: PortfolioUiState, snapshot: PortfolioSnapshot?, refreshError: String?, waiting: Boolean,
    onConnect: () -> Unit, onOpenRisk: () -> Unit, onOpenRecommendations: () -> Unit) {
                    SpectrumCard(emphasized = true) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            SpectrumAnalystAvatar(
                                mood = when {
                                    refreshError != null || snapshot?.warnings?.isNotEmpty() == true -> AnalystAvatarMood.Attention
                                    snapshot == null -> AnalystAvatarMood.Waiting
                                    else -> AnalystAvatarMood.Ready
                                },
                                motionAllowed = LocalSpectrumMotionPreference.current.enabled,
                                modifier = Modifier.size(64.dp).testTag("spectrum-ai-analyst"))
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text("Следующий шаг", style = MaterialTheme.typography.titleLarge)
                                Text(when { waiting -> "Получаем данные счёта"; state is PortfolioUiState.Error -> "Проверьте доступ к данным"; snapshot == null -> "Подключите счёт, чтобы начать"; snapshot.warnings.isNotEmpty() -> "Проверьте ограничения данных ниже"; else -> "Ознакомьтесь с последним анализом" },
                                    color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
                            }
                        }
                        SpectrumPrimaryButton(when {
                            waiting -> "Получаем данные…"
                            state is PortfolioUiState.Error -> "Проверить подключение"
                            snapshot == null -> "Подключить портфель"
                            snapshot.warnings.isNotEmpty() -> "Посмотреть риски"
                            else -> "Посмотреть анализ"
                        },
                            when {
                                snapshot == null -> onConnect
                                snapshot.warnings.isNotEmpty() -> onOpenRisk
                                else -> onOpenRecommendations
                            }, Modifier.fillMaxWidth(), enabled = !waiting)
                    }
}

@Composable
private fun BoxScope.HomePullIndicator(refreshing: Boolean, distanceFraction: Float) {
    if (distanceFraction > 0f || refreshing)
        SpectrumCard(Modifier.align(Alignment.TopCenter).padding(8.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                SpectrumIcon(SpectrumSymbol.Sources, Modifier.size(32.dp), selected = refreshing)
                Text(
                    if (refreshing) "Запрашиваем данные…"
                    else if (distanceFraction >= 1f) "Отпустите для обновления"
                    else "Потяните для обновления"
                )
            }
        }
}

@Composable
private fun CompactCapital(
    snapshot: PortfolioSnapshot?,
    collapsed: Boolean,
    scrolled: Boolean,
    onCurrencyClick: () -> Unit,
    onToggle: () -> Unit,
) {
    if (snapshot != null && (collapsed || scrolled))
        ru.omnicio.app.ui.spatial.SpatialSurface(color = MaterialTheme.colorScheme.surface) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = onCurrencyClick, modifier = Modifier.weight(1f)) {
                    Text(
                        snapshot.totalValue.moneyText(),
                        style = MaterialTheme.typography.titleMedium,
                    )
                }
                TextButton(onClick = onToggle) { Text(if (collapsed) "Развернуть" else "Свернуть") }
            }
        }
}

@Composable
private fun HomeCapitalBlock(
    state: PortfolioUiState,
    snapshot: PortfolioSnapshot?,
    selectedCurrency: PortfolioCurrency,
    refreshing: Boolean,
    refreshError: String?,
    lastUpdatedMillis: Long?,
    hidden: Boolean,
    collapsed: Boolean,
    waiting: Boolean,
    refreshMessage: String?,
    onCurrencyClick: () -> Unit,
    onConnect: () -> Unit,
    refreshNow: () -> Unit,
    onToggle: () -> Unit,
) {
    if (!collapsed)
        CapitalHero(
            state,
            snapshot,
            selectedCurrency,
            refreshing,
            refreshError,
            lastUpdatedMillis,
            hidden,
            onCurrencyClick,
            onConnect,
        )
    Row(Modifier.fillMaxWidth()) {
        if (snapshot != null)
            TextButton(onClick = onToggle) {
                Text(if (collapsed) "Развернуть капитал" else "Свернуть капитал")
            }
        TextButton(onClick = refreshNow, enabled = !refreshing && !waiting) { Text("Обновить") }
    }
    refreshMessage?.let {
        Text(
            it,
            Modifier.semantics { liveRegion = LiveRegionMode.Polite },
            style = MaterialTheme.typography.bodySmall,
        )
    }
}

@Composable
private fun HomeWarningCard(warnings: List<String>) {
    SpectrumCard {
        Text("Требует внимания", style = MaterialTheme.typography.titleMedium)
        warnings.take(2).forEach { Text(it) }
        if (warnings.size > 2)
            DetailFold("Все ограничения (${warnings.size})") {
                warnings.drop(2).forEach { Text(it) }
            }
    }
}

@Composable
private fun HomeOrderControls(
    loaded: Boolean,
    busy: Boolean,
    canUndo: Boolean,
    previewing: Boolean,
    onEdit: () -> Unit,
    onUndo: () -> Unit,
) {
    Row {
        TextButton(onClick = onEdit, enabled = loaded) { Text("Настроить главный экран") }
        if (canUndo) TextButton(onClick = onUndo, enabled = !busy) { Text("Отменить порядок") }
    }
    if (previewing) Text("Просмотр нового порядка · ещё не сохранён")
}

@Composable
private fun HomeDashboardCard(
    key: String,
    state: PortfolioUiState,
    snapshot: PortfolioSnapshot?,
    refreshError: String?,
    waiting: Boolean,
    personal: PersonalWorkspaceController,
    workspace: WorkspaceRequest,
    attributionPeriod: PortfolioPeriod,
    onAttribution: (PortfolioPeriod) -> Unit,
    onConnect: () -> Unit,
    onOpenRisk: () -> Unit,
    onOpenRecommendations: () -> Unit,
    onOpenPayments: () -> Unit,
    onOpenPortfolio: () -> Unit,
) {
    val prefs = LocalWorkspacePreferences.current.value
    when (key) {
        "assistant" ->
            HomeNextStep(
                state,
                snapshot,
                refreshError,
                waiting,
                onConnect,
                onOpenRisk,
                onOpenRecommendations,
            )
        "changes" -> if (snapshot != null) ChangesSinceVisit(snapshot, personal)
        "composition" -> if (snapshot != null) CapitalComposition(snapshot, workspace.json)
        "attribution" ->
            if (snapshot != null)
                Column {
                    WorkspaceRequestNotice(workspace)
                    if (!workspace.showingPreviousQuery)
                        HomeAttribution(workspace.json, attributionPeriod, onAttribution)
                    else PeriodControls(attributionPeriod, onAttribution)
                }
        "payouts" -> if (snapshot != null) HomePayoutTimeline(workspace.json, onOpenPayments)
        "goal" -> if (snapshot != null) HomeGoalProgress(workspace.json)
        "monitoring" -> ObservationSummary(onOpenRisk)
        "allocation" ->
            if (snapshot != null && prefs.homeStructure)
                AllocationOverview(snapshot, onOpenPortfolio)
    }
}

@Composable
@OptIn(ExperimentalFoundationApi::class)
private fun LazyItemScope.HomeAnimatedCard(
    itemMotion: Boolean,
    itemDuration: Int,
    content: @Composable () -> Unit,
) {
    Box(
        Modifier.animateItem(
            fadeInSpec =
                if (itemMotion) androidx.compose.animation.core.tween(itemDuration) else null,
            placementSpec =
                if (itemMotion) androidx.compose.animation.core.tween(itemDuration) else null,
            fadeOutSpec =
                if (itemMotion) androidx.compose.animation.core.tween(itemDuration) else null,
        )
    ) {
        content()
    }
}
