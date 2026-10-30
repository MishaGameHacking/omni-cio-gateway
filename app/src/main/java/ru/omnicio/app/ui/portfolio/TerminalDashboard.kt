package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import org.json.JSONObject
import java.math.BigDecimal
import java.time.LocalDate
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.ui.terminal.*
import ru.omnicio.app.ui.workspace.*

private const val HIDDEN_AMOUNTS = "Суммы скрыты"

/** Authenticated readers feed a single dashboard; charts themselves perform no network work. */
@Composable
internal fun TerminalDashboard(state: PortfolioUiState, currency: PortfolioCurrency, refreshing: Boolean,
    error: String?, refresh: () -> Unit, settings: () -> Unit, connect: () -> Unit) {
    val session=LocalWorkspaceSession.current
    val snapshot=(state as? PortfolioUiState.Ready)?.snapshot
    var period by rememberSaveable(session.userId) { mutableIntStateOf(5) }
    var accountId by rememberSaveable(session.userId) { mutableStateOf<String?>(null) }
    var picker by rememberSaveable { mutableStateOf(false) }
    val accounts=snapshot?.accounts.orEmpty().filter { accountId==null || it.id==accountId }
    LaunchedEffect(snapshot?.accounts?.map { it.id }) {
        if(snapshot != null && accountId != null && snapshot.accounts.none { it.id==accountId }) accountId=null
    }
    val today=LocalDate.now(Moscow)
    val start=when(period) { 0 -> today.minusDays(6); 1 -> today.minusMonths(1); 2 -> today.minusMonths(3); 3 -> today.minusMonths(6); 4 -> today.minusYears(1); else -> null }
    val selectedPeriod=PortfolioPeriod(start?.toString(),null)
    val requests=accounts.map { account -> key("terminal-history:"+account.id) {
        rememberAccountData(session.token,account.id,"analytics",selectedPeriod.parameters()+("currency" to currency.name),interval=60_000)
    } }
    val payments=accounts.map { account -> key("terminal-payments:"+account.id) {
        rememberAccountData(session.token,account.id,"payments",interval=60_000)
    } }
    val corpus=rememberWorkspaceResource("/workspace/osint/status")
    val automation=rememberWorkspaceResource("/automation/status")
    val confirmedAutomation=automation.copy(data=automation.data?.takeIf { it.optInt("schema_version")==1 })
    val foreground=workspaceForeground()
    val reload by rememberUpdatedState({ corpus.refresh(); automation.refresh() })
    LaunchedEffect(foreground) { if(foreground) while(isActive) { delay(30_000); reload() } }
    val selected=snapshot?.let { full -> if(accountId==null) full else accounts.singleOrNull()?.let { a ->
        full.copy(totalValue=a.totalValue,expectedYieldAmount=null,expectedYieldPercent=a.expectedYieldPercent,
            accounts=listOf(a),allocations=a.allocations)
    } }
    TerminalDashboardContent(selected,requests,payments,period,{ period=it },accountId?.let { accounts.singleOrNull()?.name } ?: "Все счета",
        { picker=true },refreshing,error ?: (state as? PortfolioUiState.Error)?.message,
        state==PortfolioUiState.NotConnected,corpus,confirmedAutomation,
        LocalWorkspaceSnapshot.current?.optJSONObject("sections")?.optJSONObject("ai")?.optJSONObject("data"),
        { refresh(); corpus.refresh(); automation.refresh() },settings,connect,
        ChatContext(accountId=accountId,start=selectedPeriod.start,end=selectedPeriod.end))
    if(picker) WorkspaceDialog("Счета",{ picker=false }) {
        TerminalAction("Все счета",{ accountId=null; picker=false },Modifier.fillMaxWidth(),selected=accountId==null)
        snapshot?.accounts.orEmpty().forEach { account ->
            TerminalAction(account.name,{ accountId=account.id; picker=false },Modifier.fillMaxWidth(),selected=accountId==account.id)
        }
    }
}

@Composable
internal fun TerminalDashboardContent(snapshot: PortfolioSnapshot?, requests: List<AccountData>, payments: List<AccountData>,
    period: Int, selectPeriod: (Int)->Unit, accountName: String, chooseAccount: ()->Unit,
    refreshing: Boolean, error: String?, disconnected: Boolean, corpus: WorkspaceResource, automation: WorkspaceResource,
    ai: JSONObject?, refresh: ()->Unit, settings: ()->Unit, connect: ()->Unit, context: ChatContext = ChatContext()) {
    val navigate=LocalWorkspaceNavigator.current
    val ask=LocalAskAnalyst.current
    var currencyPicker by rememberSaveable { mutableStateOf(false) }
    val chooseCurrency=LocalCurrencyChoice.current
    val privacy=LocalWorkspacePreferences.current.value.hideHomeBalance
    LazyColumn(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)
        .windowInsetsPadding(WindowInsets.safeDrawing).testTag("terminal-dashboard")
        .semantics { testTagsAsResourceId=true },contentPadding=PaddingValues(12.dp),verticalArrangement=Arrangement.spacedBy(10.dp)) {
        item("terminal-header") {
            Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically) {
                TerminalGlyph("capital",Modifier.size(25.dp),TerminalPurple)
                Spacer(Modifier.width(8.dp))
                Column(Modifier.weight(1f)) {
                    Text("ANALYST AI",fontSize=18.sp,fontWeight=FontWeight.Bold,letterSpacing=1.sp)
                    TerminalLabel("ЛИЧНЫЙ ИНВЕСТИЦИОННЫЙ ПУЛЬТ")
                }
                TerminalIconButton("notifications","События",{ navigate(WorkspaceRoute.Messages) })
                TerminalIconButton("settings","Настройки",settings)
            }
        }
        item("capital") { TerminalCapital(snapshot,accountName,chooseAccount,refreshing,error,disconnected,refresh,connect) }
        item("value") {
            TerminalPanel("ДИНАМИКА СТОИМОСТИ",trailing={ TerminalAction((snapshot?.totalValue?.currency ?: "RUB")+" ▾",{ currencyPicker=true }) }) {
                Row(Modifier.horizontalScroll(rememberScrollState())) {
                    listOf("1Н","1М","3М","6М","1Г","ВСЁ").forEachIndexed { index,label ->
                        TerminalAction(label,{ selectPeriod(index) },selected=period==index)
                    }
                }
                val ready=snapshot != null && requests.size==snapshot.accounts.size && requests.isNotEmpty() &&
                    requests.all { it.json!=null && it.error==null && !it.showingPreviousQuery && it.json.optString("currency").equals(snapshot.totalValue.currency,true) }
                when {
                    privacy -> TerminalChartEmpty(HIDDEN_AMOUNTS)
                    ready -> TerminalValuePlot(joinedAnalyticsHistory(requests.mapNotNull { it.json }),snapshot.totalValue.currency)
                    requests.any { it.error!=null } -> TerminalChartEmpty("История недоступна · обновите данные")
                    requests.any { it.showingPreviousQuery } -> TerminalChartEmpty("Получаем выбранный период…")
                    snapshot==null -> TerminalChartEmpty("История появится после получения портфеля")
                    else -> TerminalChartEmpty("Получаем сохранённую историю…")
                }
                TerminalAction("Объяснить динамику ↗",{ ask(context.copy(title="Динамика портфеля")) })
            }
        }
        item("allocation") { TerminalStructure(snapshot,privacy) }
        item("holdings") { TerminalHoldings(snapshot) }
        item("payments") { TerminalPaymentPanel(payments,privacy) }
        item("system") { TerminalSystem(corpus,automation,ai,privacy) }
        item("assistant") {
            TerminalPanel("ИИ · ОБЪЯСНЕНИЯ",trailing={ TerminalGlyph("analyst",Modifier.size(20.dp)) }) {
                Text("Разобрать портфель, изменения и риски по сохранённым данным.",style=MaterialTheme.typography.bodySmall,
                    color=MaterialTheme.colorScheme.onSurfaceVariant)
                Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
                    TerminalAction("Спросить ИИ ↗",{ ask(context) })
                    TerminalAction("Стратегия",{ navigate(WorkspaceRoute.Strategies) })
                }
            }
        }
        item("terminal-footer") { TerminalLabel("Т‑ИНВЕСТИЦИИ · "+(snapshot?.asOf?.let { dateText(it,"dd.MM.yy HH:mm") } ?: "СНИМОК НЕ ПОЛУЧЕН")+" · МСК") }
    }
    if(currencyPicker) WorkspaceDialog("Валюта оценки",{ currencyPicker=false }) {
        PortfolioCurrency.entries.forEach { currency ->
            TerminalAction(currency.name,{ chooseCurrency(currency); currencyPicker=false },Modifier.fillMaxWidth())
        }
    }
}

@Composable
private fun TerminalCapital(snapshot: PortfolioSnapshot?, accountName: String, chooseAccount: ()->Unit,
    refreshing: Boolean, error: String?, disconnected: Boolean, refresh: ()->Unit, connect: ()->Unit) {
    TerminalPanel("ПОРТФЕЛЬ",trailing={
        Row(verticalAlignment=Alignment.CenterVertically) {
            TerminalAction(accountName+" ▾",chooseAccount,enabled=snapshot!=null)
            TerminalIconButton("update","Обновить данные",refresh)
        }
    }) {
        Text(snapshot?.totalValue.moneyText(),fontSize=34.sp,lineHeight=42.sp,fontWeight=FontWeight.SemiBold,letterSpacing=(-1).sp)
        val gain=snapshot?.expectedYieldAmount
        if(gain!=null) Text(PrivateValue(gain.moneyText(signed=true)+"  ("+snapshot.expectedYieldPercent.percentText()+")"),
            color=if(gain.value.toBigDecimal().signum()<0) TerminalRed else TerminalLime,style=MaterialTheme.typography.titleSmall)
        TerminalLabel("РЕЗУЛЬТАТ ОТКРЫТЫХ ПОЗИЦИЙ")
        HorizontalDivider(color=MaterialTheme.colorScheme.outlineVariant)
        BoxWithConstraints(Modifier.fillMaxWidth()) {
            val small=maxWidth<300.dp*LocalDensity.current.fontScale
            val content: @Composable ()->Unit={
                val currency=snapshot?.totalValue?.currency.orEmpty()
                val daily=snapshot?.let { terminalSum(it.accounts.map { a -> a.dailyYieldAmount },currency) }
                val cash=snapshot?.let { s -> terminalSum(s.accounts.flatMap { it.positions }.filter { it.instrumentType in listOf("cash","currency") }.map { it.currentValue },currency) }
                TerminalMetric("СЕГОДНЯ",daily?.let { PrivateValue(decimalText(it)+" "+currencySymbol(currency)) } ?: "Нет оценки",if(daily?.signum()==-1) TerminalRed else TerminalLime)
                TerminalMetric("ДЕНЕЖНЫЕ ПОЗИЦИИ",cash?.let { PrivateValue(decimalText(it)+" "+currencySymbol(currency)) } ?: "Нет оценки",TerminalPurple)
            }
            if(small) Column(verticalArrangement=Arrangement.spacedBy(10.dp)) { content() }
            else Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) { content() }
        }
        if(error!=null) Text(error,color=TerminalAmber,style=MaterialTheme.typography.bodySmall)
        if(disconnected) TerminalAction("Подключить Т‑Инвестиции ↗",connect)
        else TerminalLabel(if(refreshing) "ОБНОВЛЕНИЕ…" else snapshot?.asOf?.let { "СНИМОК · "+dateText(it,"dd.MM HH:mm") } ?: "ОЖИДАНИЕ ДАННЫХ")
    }
}

@Composable
private fun TerminalMetric(title: String,value: String,color: Color) {
    Column(verticalArrangement=Arrangement.spacedBy(4.dp)) {
        TerminalLabel(title)
        Text(value,color=color,fontSize=17.sp,fontWeight=FontWeight.Medium)
    }
}

@Composable
private fun TerminalStructure(snapshot: PortfolioSnapshot?, hidden: Boolean) {
    TerminalPanel("СТРУКТУРА АКТИВОВ") {
        val rows=snapshot?.let { terminalAllocation(it.allocations) }
        if(hidden) TerminalChartEmpty(HIDDEN_AMOUNTS)
        else if(rows==null) TerminalChartEmpty("Распределение пока не получено")
        else BoxWithConstraints(Modifier.fillMaxWidth()) {
            val legend: @Composable ()->Unit={
                Column(verticalArrangement=Arrangement.spacedBy(12.dp)) {
                    rows.forEachIndexed { index,row ->
                        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp),verticalAlignment=Alignment.CenterVertically) {
                            Box(Modifier.size(7.dp).background(TerminalSeries[index%TerminalSeries.size]))
                            Text(row.label,Modifier.weight(1f),style=MaterialTheme.typography.bodySmall)
                            Text(decimalText(row.percent,1)+"%",style=MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
            if(maxWidth>=320.dp*LocalDensity.current.fontScale) Row(verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(18.dp)) {
                TerminalDonut(rows); Box(Modifier.weight(1f)) { legend() }
            } else Column(Modifier.fillMaxWidth(),horizontalAlignment=Alignment.CenterHorizontally,verticalArrangement=Arrangement.spacedBy(14.dp)) {
                TerminalDonut(rows); legend()
            }
        }
    }
}

@Composable
private fun TerminalHoldings(snapshot: PortfolioSnapshot?) {
    var expanded by rememberSaveable { mutableStateOf(false) }
    val open=LocalPortfolioDestination.current
    val rows=snapshot?.accounts.orEmpty().flatMap { a -> a.positions.map { a to it } }
        .sortedByDescending { it.second.currentValue?.takeIf { v -> v.currency==snapshot?.totalValue?.currency }?.value?.toBigDecimal() }
    TerminalPanel("МОИ АКТИВЫ",trailing={ TerminalLabel(rows.size.toString()) }) {
        if(rows.isEmpty()) Text("Позиции пока не получены",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
        rows.take(if(expanded) rows.size else 5).forEach { (account,position) ->
            Column(Modifier.fillMaxWidth().clickable(role=Role.Button) { open(PortfolioDestination(accountId=account.id,query=position.id)) }
                .padding(vertical=6.dp),verticalArrangement=Arrangement.spacedBy(5.dp)) {
                Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                    Text(position.ticker ?: position.title,Modifier.weight(1f),fontWeight=FontWeight.SemiBold,fontSize=14.sp,color=TerminalPurple)
                    Text(position.currentValue.moneyText(),fontSize=14.sp)
                }
                Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                    Text(position.title,Modifier.weight(1f),style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(PrivateValue(position.expectedYieldPercent.percentText()),style=MaterialTheme.typography.bodySmall,
                        color=if(position.expectedYieldPercent?.toBigDecimal()?.signum()==-1) TerminalRed else TerminalLime)
                }
            }
            HorizontalDivider(color=MaterialTheme.colorScheme.outlineVariant)
        }
        if(rows.size>5) TerminalAction(if(expanded) "Свернуть ↑" else "Все активы · ${rows.size} ↓",{ expanded=!expanded })
    }
}

@Composable
private fun TerminalPaymentPanel(requests: List<AccountData>,hidden: Boolean) {
    TerminalPanel("ОЖИДАЕМЫЕ ВЫПЛАТЫ") {
        val ready=requests.isNotEmpty() && requests.all { it.json!=null && it.error==null && !it.showingPreviousQuery }
        if(hidden) TerminalChartEmpty(HIDDEN_AMOUNTS)
        else if(!ready) TerminalChartEmpty(if(requests.any { it.error!=null }) "Календарь временно недоступен" else "Получаем календарь выплат…")
        else {
            val data=terminalPayments(requests.mapNotNull { it.json })
            if(data.rows.isEmpty()) TerminalChartEmpty(if(data.complete && data.missingAmounts==0) "Объявленных выплат нет" else "Суммы выплат пока не подтверждены")
            data.rows.groupBy { it.currency }.forEach { (currency,rows) -> TerminalPaymentPlot(rows.take(12),currency) }
            if(data.missingAmounts>0 || !data.complete) Text("Часть выплат без подтверждённой суммы",color=TerminalAmber,style=MaterialTheme.typography.bodySmall)
            TerminalLabel("ОЦЕНКА ПО ТЕКУЩЕМУ КОЛИЧЕСТВУ БУМАГ")
        }
    }
}

@Composable
private fun TerminalSystem(corpus: WorkspaceResource, automation: WorkspaceResource, ai: JSONObject?, hidden: Boolean) {
    val navigate=LocalWorkspaceNavigator.current
    TerminalPanel("ДАННЫЕ И АНАЛИЗ",trailing={ TerminalAction("Подробнее ↗",{ navigate(WorkspaceRoute.AnalysisTimeline) }) }) {
        val sources=corpus.data?.records("sources").orEmpty()
        val checked=sources.count { it.text("state","") in setOf("ready", "not_modified") && !it.optBoolean("stale") && it.optInt("target_failures")==0 &&
            it.optJSONObject("coverage")?.optBoolean("truncated")!=true && it.optJSONObject("coverage")?.optBoolean("empty_index")!=true }
        val docs=corpus.data?.opt("documents")?.toString()?.takeUnless { it=="null" }
        Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {
            TerminalMetric("МАТЕРИАЛЫ В БАЗЕ",docs ?: "Нет данных",TerminalCyan)
            if(sources.isNotEmpty()) TerminalMetric("ИСТОЧНИКИ",sources.size.toString(),TerminalPurple)
        }
        if(sources.isNotEmpty()) {
            val fraction=checked.toFloat()/sources.size
            LinearProgressIndicator(progress={ fraction },modifier=Modifier.fillMaxWidth().height(4.dp),color=TerminalCyan,
                trackColor=MaterialTheme.colorScheme.outlineVariant)
            TerminalLabel("ПОЛНОСТЬЮ ДОСТУПНЫ: $checked / ${sources.size}")
        }
        val blockers=automation.data?.records("blockers").orEmpty()
        val status=when(automation.data?.text("state","")) {
            "collecting" -> "Идёт сбор данных"; "paused" -> "Анализ приостановлен"
            "not_connected" -> "Нужен доступ к счёту"; "disabled" -> "Фоновая работа выключена"
            "waiting" -> "Ожидаем следующую проверку"; "attention" -> "Требуется внимание"
            "current" -> "Последний результат сохранён"; else -> "Состояние уточняется"
        }
        Text(status,color=if(blockers.isEmpty()) TerminalCyan else TerminalAmber,style=MaterialTheme.typography.titleSmall)
        blockers.firstOrNull()?.let { Text(it.text("message"),style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant) }
        val execution=automation.data?.optJSONObject("execution")
        if(execution?.text("mode", "") == "read_only" && execution.opt("real_orders_enabled") == false)
            TerminalLabel("АНАЛИЗ · РЕАЛЬНЫЕ СДЕЛКИ ВЫКЛЮЧЕНЫ")
        if(corpus.error!=null || automation.error!=null) Text("Не все состояния обновились",style=MaterialTheme.typography.bodySmall,color=TerminalAmber)
        ai?.optJSONObject("budget")?.let { budget ->
            val spent=budget.text("estimated_and_reserved_rub","").toBigDecimalOrNull()
            val cap=budget.text("daily_cap_rub","").toBigDecimalOrNull()
            if(!hidden && spent!=null && cap!=null && cap.signum()>0) {
                TerminalLabel("ИИ СЕГОДНЯ · ${decimalText(spent)} / ${decimalText(cap,0)} ₽")
                LinearProgressIndicator(progress={ spent.divide(cap,java.math.MathContext.DECIMAL64).toFloat().coerceIn(0f,1f) },
                    modifier=Modifier.fillMaxWidth().height(4.dp),color=TerminalPurple,trackColor=MaterialTheme.colorScheme.outlineVariant)
            }
        }
        Row(Modifier.horizontalScroll(rememberScrollState())) {
            TerminalAction("Документы ↗",{ navigate(WorkspaceRoute.Library) })
            TerminalAction("Подбор активов ↗",{ navigate(WorkspaceRoute.Discovery) })
        }
    }
}
