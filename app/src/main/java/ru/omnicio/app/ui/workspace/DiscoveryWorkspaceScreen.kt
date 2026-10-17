package ru.omnicio.app.ui.workspace

import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.data.backend.BackendResult
import ru.omnicio.app.data.market.*
import ru.omnicio.app.data.market.records
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.data.research.ResearchClient
import ru.omnicio.app.data.workspace.rememberPersonalWorkspace
import ru.omnicio.app.ui.portfolio.*
import ru.omnicio.app.ui.research.ResearchSnapshot
import ru.omnicio.app.ui.spectrum.*
import java.time.LocalDate
import java.time.YearMonth

private data class SearchPage(val title: String, val terms: String, val route: WorkspaceRoute)
private val discoveryPages = listOf(
    SearchPage("ИИ-помощник", "чат вопрос анализ исследование", WorkspaceRoute.Assistant),
    SearchPage("Стратегия", "цель риск ограничения распределение", WorkspaceRoute.Strategies),
    SearchPage("Отрасли и география", "рынок страна валюта структура глобус", WorkspaceRoute.Market),
    SearchPage("Сообщения", "уведомление событие внимание", WorkspaceRoute.Messages),
    SearchPage("Внешний вид", "настройки тема анимация 3d движение размер", WorkspaceRoute.Appearance),
    SearchPage("Правила уведомлений", "настройки порог расписание тишина", WorkspaceRoute.NotificationSettings),
    SearchPage("Устройства и сеансы", "настройки безопасность авторизация", WorkspaceRoute.Devices),
    SearchPage("История действий", "обновление задание журнал", WorkspaceRoute.ActivityHistory),
    SearchPage("Цели и резерв", "настройки капитал накопления", WorkspaceRoute.Goals),
    SearchPage("Сохранённые исследования", "архив заметка офлайн", WorkspaceRoute.Library),
    SearchPage("Разборы во времени", "анализ изменение решение", WorkspaceRoute.AnalysisTimeline),
    SearchPage("Обучение", "помощь термины жесты", WorkspaceRoute.Education),
)

/** Searches authenticated holdings, published events and user notes; it does not invent market coverage. */
@Composable
fun DiscoveryWorkspaceScreen(state: PortfolioUiState, onBack: () -> Unit) {
    val snapshot = (state as? PortfolioUiState.Ready)?.snapshot
    val session = LocalWorkspaceSession.current
    val personal = rememberPersonalWorkspace()
    val navigate = LocalWorkspaceNavigator.current
    val destination = LocalPortfolioDestination.current
    var query by rememberSaveable(session.userId) { mutableStateOf("") }
    var category by rememberSaveable(session.userId) { mutableIntStateOf(0) }
    var shown by rememberSaveable(query, category) { mutableIntStateOf(30) }
    var selectedKey by rememberSaveable(session.userId) { mutableStateOf<String?>(null) }
    var standaloneUid by rememberSaveable(session.userId) { mutableStateOf<String?>(null) }
    var selectedArchive by rememberSaveable(session.userId) { mutableStateOf<String?>(null) }
    var chosenKeys by rememberSaveable(session.userId) { mutableStateOf(arrayListOf<String>()) }
    var compare by remember { mutableStateOf(false) }
    var selectedResearch by remember { mutableStateOf<JSONObject?>(null) }
    val rows = snapshot?.accounts?.flatMap { account -> account.positions.map { PortfolioRow(account, it) } }.orEmpty()
    val selected = rows.firstOrNull { portfolioRowKey(it) == selectedKey }
    val chosen = rows.filter { portfolioRowKey(it) in chosenKeys }
    val request = rememberWorkspaceRequest(parameters = mapOf("currency" to (snapshot?.totalValue?.currency ?: "RUB")),
        refreshKey = LocalWorkspaceRefreshKey.current)
    var research by remember(session.userId) { mutableStateOf<JSONObject?>(null) }
    var researchError by remember(session.userId) { mutableStateOf<String?>(null) }
    var researchLoading by remember(session.userId) { mutableStateOf(false) }
    val foreground = workspaceForeground()
    LaunchedEffect(session.token, foreground, LocalWorkspaceRefreshKey.current) {
        if (session.token.isBlank() || !foreground) return@LaunchedEffect
        researchLoading = true
        try {
            when (val result = withContext(Dispatchers.IO) { ResearchClient().read(session.token) }) {
                is BackendResult.Success -> { research = result.value; researchError = null }
                is BackendResult.Failure -> researchError = result.message
            }
        } finally { researchLoading = false }
    }
    val matches: (String) -> Boolean = { text -> query.isBlank() || text.contains(query.trim(), true) }
    val assets = rows.filter { matchingPosition(it.position, query) || matches(it.account.name) }.let {
        sortedPortfolioRows(it, 3, snapshot?.totalValue?.currency ?: "RUB")
    }
    val accounts = snapshot?.accounts.orEmpty().filter { matches(it.name) || matches(it.id) }
    val payouts = request.json?.sectionData("payouts")?.records("items").orEmpty().filter {
        listOfNotNull(it.optionalText("title"), it.optionalText("instrument_uid"), it.optionalText("date"), it.optionalText("kind")).any(matches)
    }
    val archives = personal.research.filter { listOfNotNull(it.title, it.source, it.note, it.instrumentId).any(matches) }
    val cards = research?.records("cards").orEmpty().filter {
        listOfNotNull(it.optionalText("name"), it.optionalText("ticker"), it.optionalText("isin"), it.optionalText("explanation")).any(matches)
    }
    val pages = discoveryPages.filter { matches(it.title) || matches(it.terms) }
    val watches = personal.watches.filter { matches(it.title) || matches(it.reason) || matches(it.uid) }
    if (selectedArchive != null) {
        ResearchLibraryScreen(state, { selectedArchive = null }, initialId = selectedArchive)
        return
    }
    WorkspaceDetailPage("Найти и исследовать", "Активы, счета, выплаты и ваши рабочие материалы", onBack, SpectrumSymbol.Market) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)) {
            SpectrumTextField(query, { query = it.take(300) }, label = { Text("Поиск по приложению") }, singleLine = true,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 8.dp))
            SpectrumTabs(listOf("Всё", "Активы", "Счета", "Выплаты", "Исследования", "Страницы", "Наблюдение", "Календарь"),
                category, { category = it }, Modifier.padding(horizontal = 12.dp))
            if (chosenKeys.isNotEmpty()) Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp)) {
                TextButton(onClick = { compare = true }, enabled = chosen.size in 2..3) { Text("Сравнить (${chosen.size}/3)") }
                TextButton(onClick = { chosenKeys = arrayListOf() }) { Text("Снять выбор") }
            }
            LazyColumn(Modifier.weight(1f).fillMaxWidth(), contentPadding = PaddingValues(20.dp),
                verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
                item(key = "scope") {
                    Text("Поиск охватывает подключённый портфель, полученные события и материалы этого аккаунта.", style = MaterialTheme.typography.bodySmall)
                    if (snapshot == null) Text("Позиции и счета ещё не получены. Личные записи и страницы доступны.")
                    if (category in listOf(0, 3, 7)) WorkspaceRequestNotice(request)
                }
                if (category in listOf(0, 1)) {
                    item(key = "asset-title") { SectionHeading("Активы · ${assets.size}") }
                    items(assets.take(if (category == 0) 5 else shown), key = { "asset:${portfolioRowKey(it)}" }) { row -> SpectrumCard {
                        PositionLine(row.position, snapshot?.totalValue, row.account.name, sharedKey = portfolioRowKey(row)) { selectedKey = portfolioRowKey(row) }
                        val selectedForCompare = portfolioRowKey(row) in chosenKeys
                        TextButton(onClick = {
                            chosenKeys = ArrayList(if (selectedForCompare) chosenKeys.filter { it != portfolioRowKey(row) } else chosenKeys + portfolioRowKey(row))
                        }, enabled = selectedForCompare || chosenKeys.size < 3) { Text(if (selectedForCompare) "Убрать из сравнения" else "Добавить к сравнению") }
                    } }
                    if (assets.size > if (category == 0) 5 else shown) item(key = "more-assets") {
                        TextButton(onClick = { if (category == 0) category = 1 else shown += 30 }) { Text("Показать ещё активы") }
                    }
                    if (assets.isEmpty()) item(key = "no-assets") { Text("Подходящих позиций в полученном портфеле нет.") }
                }
                if (category in listOf(0, 2)) {
                    item(key = "account-title") { SectionHeading("Счета · ${accounts.size}") }
                    items(accounts, key = { "account:${it.id}" }) { account -> SpectrumCard(onClick = { destination(PortfolioDestination(accountId = account.id, section = 0)) }) {
                        Text(account.name, style = MaterialTheme.typography.titleMedium)
                        Text(account.totalValue.moneyText())
                        Text("${account.positions.size} позиций · открыть счёт", style = MaterialTheme.typography.bodySmall)
                    } }
                }
                if (category in listOf(0, 3)) {
                    item(key = "payout-title") { SectionHeading("Выплаты · ${payouts.size}"); WorkspaceSectionNotice(request.json?.section("payouts")) }
                    items(payouts.take(if (category == 0) 4 else shown), key = { "payout:${it.optString("id")}:${it.optString("account_id")}" }) { payout ->
                        DiscoveryPayout(payout) { uid -> standaloneUid = uid }
                    }
                    if (category == 3 && payouts.size > shown) item(key = "more-payouts") { TextButton(onClick = { shown += 30 }) { Text("Ещё выплаты") } }
                }
                if (category in listOf(0, 4)) {
                    item(key = "research-title") {
                        SectionHeading("Исследования · ${archives.size + cards.size}")
                        if (researchLoading) LinearProgressIndicator(Modifier.fillMaxWidth())
                        researchError?.let { Text("Последний анализ: $it", color = MaterialTheme.colorScheme.error) }
                    }
                    items(archives.take(if (category == 0) 3 else shown), key = { "archive:${it.id}" }) { archive -> SpectrumCard(onClick = { selectedArchive = archive.id }) {
                        Text(archive.title, style = MaterialTheme.typography.titleMedium)
                        Text("Сохранённый снимок · ${dateText(archive.observedAt)}", style = MaterialTheme.typography.bodySmall)
                        Text(archive.source, style = MaterialTheme.typography.bodySmall)
                        if (archive.note.isNotBlank()) Text(PrivateValue(archive.note))
                    } }
                    items(cards.take(if (category == 0) 3 else shown), key = { "research:${it.optString("instrument_uid")}" }) { card -> SpectrumCard(onClick = { selectedResearch = card }) {
                        Text(card.optionalText("name") ?: "Разбор инструмента", style = MaterialTheme.typography.titleMedium)
                        Text("Последний анализ · ${dateText(research?.optionalText("as_of"))}", style = MaterialTheme.typography.bodySmall)
                        Text(PrivateValue(card.optionalText("explanation") ?: "Откройте разбор"))
                    } }
                    if (category == 4 && maxOf(archives.size, cards.size) > shown) item(key = "more-research") { TextButton(onClick = { shown += 30 }) { Text("Ещё исследования") } }
                }
                if (category in listOf(0, 5)) {
                    item(key = "pages-title") { SectionHeading("Страницы и настройки · ${pages.size}") }
                    items(pages, key = { "page:${it.route.name}" }) { page -> SpectrumActionTile(page.title, page.terms, SpectrumSymbol.Sources, { navigate(page.route) }) }
                }
                if (category == 6) {
                    item(key = "watch-title") {
                        SectionHeading("Моё наблюдение · ${watches.size}")
                        Text("Причину добавления задаёте вы. Запись не является торговой рекомендацией.", style = MaterialTheme.typography.bodySmall)
                        if (watches.isEmpty()) Text("Добавьте бумагу в наблюдение из краткого просмотра или её деталей.")
                    }
                    items(watches, key = { "watch:${it.uid}" }) { watch -> SpectrumCard {
                        Text(watch.title, style = MaterialTheme.typography.titleMedium)
                        Text(PrivateValue(watch.reason))
                        val held = rows.filter { it.position.id == watch.uid }
                        if (held.isEmpty()) Text("Бумага отсутствует в текущем снимке портфеля. Запись наблюдения сохранена.")
                        else held.forEach { DataRow(it.account.name, it.position.currentValue.moneyText()) }
                        Row {
                            TextButton(onClick = { if (held.isEmpty()) standaloneUid = watch.uid else selectedKey = portfolioRowKey(held.first()) }) { Text("Открыть бумагу") }
                            TextButton(onClick = { personal.unwatch(watch.uid) }, enabled = !personal.busy) { Text("Убрать") }
                        }
                    } }
                    personal.error?.let { item(key = "watch-error") { Text(it, color = MaterialTheme.colorScheme.error) } }
                }
                if (category == 7) item(key = "calendar") {
                    DiscoveryCalendar(request.json, query) { uid -> standaloneUid = uid }
                }
            }
        }
    }
    selected?.let { row -> InstrumentDetailsScreen(row.position, { selectedKey = null }, row.account.name, sharedKey = portfolioRowKey(row), accountId = row.account.id) }
    if (selectedKey != null && selected == null) AlertDialog(onDismissRequest = { selectedKey = null }, title = { Text("Позиция изменилась") },
        text = { Text("В текущих данных этой позиции нет. Старая оценка не используется.") },
        confirmButton = { TextButton(onClick = { selectedKey = null }) { Text("Вернуться к поиску") } })
    if (compare) AssetComparisonDialog(chosen, snapshot?.asOf, { compare = false })
    standaloneUid?.let { uid -> DiscoveryDossier(uid) { standaloneUid = null } }
    selectedResearch?.let { card ->
        Dialog(onDismissRequest = { selectedResearch = null }, properties = DialogProperties(usePlatformDefaultWidth = false)) {
            SpectrumBackground(Modifier.fillMaxSize()) {
                LazyColumn(contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
                    item { TextButton(onClick = { selectedResearch = null }) { Text("Закрыть разбор") } }
                    item {
                        val payload = JSONObject(research?.toString() ?: "{}").put("cards", JSONArray(listOf(card)))
                        if (LocalWorkspacePreferences.current.value.hideHomeBalance) Text("Разбор скрыт режимом приватности.")
                        else {
                            Text("Показана одна выбранная карточка. Общие выводы относятся к исходному анализу.")
                            payload.remove("risk")
                            payload.remove("examined_positions"); payload.remove("total_positions"); payload.remove("issuer_coverage_count")
                            ResearchSnapshot(payload, session.token)
                            SaveResearchButton(payload, "Разбор ${card.optString("name")}", card.optionalText("instrument_uid"), observedAt = payload.optionalText("as_of"))
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun DiscoveryPayout(row: JSONObject, onInstrument: (String) -> Unit) {
    SpectrumCard {
        Text(row.optionalText("title") ?: "Выплата", style = MaterialTheme.typography.titleMedium)
        DataRow(row.optionalText("date") ?: "Дата не опубликована", workspaceMoney(row.optJSONObject("amount")))
        Text(when (row.optString("status")) { "received" -> "Получена"; "announced" -> "Объявлена"; "expected" -> "Ожидается"; else -> "Статус не подтверждён" })
        if (row.optBoolean("eligibility_unknown")) Notice("Право и количество на дату реестра не подтверждены.")
        row.optionalText("instrument_uid")?.let { uid -> TextButton(onClick = { onInstrument(uid) }) { Text("Компания и позиция") } }
    }
}

@Composable
private fun DiscoveryDossier(uid: String, close: () -> Unit) {
    val request = rememberWorkspaceRequest("/workspace/instruments/$uid/dossier")
    Dialog(onDismissRequest = close, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(Modifier.fillMaxSize()) { LazyColumn(contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
            item { TextButton(onClick = close) { Text("Закрыть досье") }; WorkspaceRequestNotice(request) }
            request.json?.takeIf { it.optString("instrument_uid") == uid }?.let { payload -> item {
                if (LocalWorkspacePreferences.current.value.hideHomeBalance) Text("Досье скрыто режимом приватности.") else InstrumentDossierContent(payload, onNavigate = close)
            } }
        } }
    }
}

@Composable
private fun DiscoveryCalendar(workspace: JSONObject?, query: String, onInstrument: (String) -> Unit) {
    var monthText by rememberSaveable { mutableStateOf(YearMonth.now().toString()) }
    val month = runCatching { YearMonth.parse(monthText) }.getOrDefault(YearMonth.now())
    val payouts = workspace?.sectionData("payouts")?.records("items").orEmpty()
    val events = workspace?.sectionData("events")?.records("items").orEmpty()
    SpectrumCard {
        Text("Календарь подтверждённых событий", style = MaterialTheme.typography.titleLarge)
        Row {
            TextButton(onClick = { monthText = month.minusMonths(1).toString() }) { Text("‹ Месяц") }
            TextButton(onClick = { monthText = YearMonth.now().toString() }) { Text(month.toString()) }
            TextButton(onClick = { monthText = month.plusMonths(1).toString() }) { Text("Месяц ›") }
        }
        val rows = (payouts.map { "payout" to it } + events.map { "event" to it }).filter { (_, value) ->
            (value.optionalText("date") ?: value.optionalText("occurred_at"))?.startsWith(month.toString()) == true &&
                (query.isBlank() || listOfNotNull(value.optionalText("title"), value.optionalText("summary")).any { it.contains(query, true) })
        }.sortedBy { (_, value) -> value.optionalText("date") ?: value.optionalText("occurred_at") }
        if (rows.isEmpty()) Text("В полученных данных за этот месяц событий нет. Неопубликованные события сюда не добавляются.")
        rows.forEach { (kind, row) ->
            if (kind == "payout") DiscoveryPayout(row, onInstrument)
            else WorkspaceEvents(listOf(row), workspace?.records("sources").orEmpty(), onInstrument)
        }
        WorkspaceSectionNotice(workspace?.section("payouts"))
        WorkspaceSectionNotice(workspace?.section("events"))
        Text("Объявленные даты отчётности доступны также в досье каждой компании. События без даты не помещаются в вымышленный день.", style = MaterialTheme.typography.bodySmall)
    }
}
