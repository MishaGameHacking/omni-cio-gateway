package ru.omnicio.app.ui.workspace

import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.mapSaver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.data.backend.BackendResult
import ru.omnicio.app.data.market.*
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.data.workspace.*
import ru.omnicio.app.ui.portfolio.*
import ru.omnicio.app.ui.research.ResearchSnapshot
import ru.omnicio.app.ui.spatial.SpatialWindow
import ru.omnicio.app.ui.spectrum.*
import java.time.YearMonth

private const val WORKSPACE_CONTENT_TAG = "workspace-content"


private data class SearchPage(val title: String, val terms: String, val route: WorkspaceRoute)
private val discoveryPages = listOf(
    SearchPage("ИИ-помощник", "чат вопрос анализ исследование", WorkspaceRoute.Assistant),
    SearchPage("Стратегия", "цель риск ограничения распределение", WorkspaceRoute.Strategies),
    SearchPage("Отрасли и география", "рынок страна валюта структура глобус торговая сессия календарь", WorkspaceRoute.Market),
    SearchPage("Сообщения", "уведомление событие внимание", WorkspaceRoute.Messages),
    SearchPage("Внешний вид", "настройки тема анимация 3d движение размер", WorkspaceRoute.Appearance),
    SearchPage("Правила уведомлений", "настройки порог расписание тишина", WorkspaceRoute.NotificationSettings),
    SearchPage("Устройства и сеансы", "настройки безопасность авторизация", WorkspaceRoute.Devices),
    SearchPage("История действий", "обновление задание журнал", WorkspaceRoute.ActivityHistory),
    SearchPage("Цели и резерв", "настройки капитал накопления", WorkspaceRoute.Goals),
    SearchPage("Сохранённые исследования", "архив заметка офлайн", WorkspaceRoute.Library),
    SearchPage("Разборы во времени", "анализ изменение решение", WorkspaceRoute.AnalysisTimeline),
    SearchPage("Последний анализ", "отчёт исследование компания источники", WorkspaceRoute.Reports),
    SearchPage("Что нового", "обновление новые возможности", WorkspaceRoute.NewFeatures),
    SearchPage("Обучение", "помощь термины жесты", WorkspaceRoute.Education),
)

@Stable
private class DiscoverySelection {
    var positionKey by mutableStateOf<String?>(null)
    var standaloneUid by mutableStateOf<String?>(null)
    var archiveId by mutableStateOf<String?>(null)
    var researchKey by mutableStateOf<String?>(null)
    var chosenKeys by mutableStateOf<List<String>>(emptyList())
    var comparing by mutableStateOf(false)

    fun toggleComparison(key: String) {
        chosenKeys = if (key in chosenKeys) chosenKeys - key else if (chosenKeys.size < 3) chosenKeys + key else chosenKeys
    }

    companion object {
        val saver = mapSaver(
            save = { value: DiscoverySelection -> mapOf("position" to value.positionKey, "standalone" to value.standaloneUid,
                "archive" to value.archiveId, "research" to value.researchKey,
                "chosen" to ArrayList(value.chosenKeys), "comparing" to value.comparing) },
            restore = { saved -> DiscoverySelection().apply {
                positionKey = saved["position"] as? String; standaloneUid = saved["standalone"] as? String
                archiveId = saved["archive"] as? String; researchKey = saved["research"] as? String
                chosenKeys = (saved["chosen"] as? List<*>)?.filterIsInstance<String>().orEmpty()
                comparing = saved["comparing"] as? Boolean ?: false
            } },
        )
    }
}

private data class DiscoveryResearch(val json: JSONObject?, val loading: Boolean, val error: String?, val refresh: () -> Unit)

@Composable
private fun rememberDiscoveryResearch(): DiscoveryResearch {
    val session = LocalWorkspaceSession.current
    val client = LocalPortfolioReadSource.current
    val foreground = workspaceForeground()
    var revision by remember(session.userId) { mutableIntStateOf(0) }
    var data by remember(session.userId) { mutableStateOf<JSONObject?>(null) }
    var error by remember(session.userId) { mutableStateOf<String?>(null) }
    var loading by remember(session.userId) { mutableStateOf(false) }
    LaunchedEffect(client, session.token, foreground, LocalWorkspaceRefreshKey.current, revision) {
        if (session.token.isBlank() || !foreground) return@LaunchedEffect
        loading = true
        try {
            when (val result = withContext(Dispatchers.IO) { client.research(session.token) }) {
                is BackendResult.Success -> { data = result.value; error = null }
                is BackendResult.Failure -> error = result.message
            }
        } finally { loading = false }
    }
    return DiscoveryResearch(data, loading, error) { revision++ }
}

private data class DiscoveryResults(
    val rows: List<PortfolioRow>,
    val assets: List<PortfolioRow>,
    val accounts: List<PortfolioAccount>,
    val payouts: List<JSONObject>,
    val archives: List<SavedResearch>,
    val cards: List<JSONObject>,
    val pages: List<SearchPage>,
    val watches: List<WatchEntry>,
)

private fun discoveryResults(snapshot: PortfolioSnapshot?, personal: PersonalWorkspaceController,
    workspace: JSONObject?, research: JSONObject?, query: String): DiscoveryResults {
    val text = query.trim()
    fun matches(value: String) = text.isBlank() || value.contains(text, true)
    val rows = snapshot?.accounts?.flatMap { account -> account.positions.map { PortfolioRow(account, it) } }.orEmpty()
    val assets = sortedPortfolioRows(rows.filter {
        matchingPosition(it.position, text) || matches(it.position.id) || matches(it.account.name)
    }, 3, snapshot?.totalValue?.currency ?: "RUB")
    return DiscoveryResults(rows, assets,
        snapshot?.accounts.orEmpty().filter { matches(it.name) || matches(it.id) },
        workspace?.sectionData("payouts")?.records("items").orEmpty().filter {
            listOfNotNull(it.optionalText("title"), it.optionalText("instrument_uid"), it.optionalText("date"), it.optionalText("kind")).any(::matches)
        },
        personal.research.filter { listOfNotNull(it.title, it.source, it.note, it.instrumentId).any(::matches) },
        research?.records("cards").orEmpty().filter {
            listOfNotNull(it.optionalText("name"), it.optionalText("ticker"), it.optionalText("isin"), it.optionalText("explanation")).any(::matches)
        },
        discoveryPages.filter { matches(it.title) || matches(it.terms) },
        personal.watches.filter { matches(it.title) || matches(it.reason) || matches(it.uid) },
    )
}

/** Searches authenticated holdings, source events and user notes; it does not invent market coverage. */
@Composable
fun DiscoveryWorkspaceScreen(state: PortfolioUiState, onBack: () -> Unit) {
    val snapshot = (state as? PortfolioUiState.Ready)?.snapshot
    val session = LocalWorkspaceSession.current
    val personal = rememberPersonalWorkspace()
    val selection = rememberSaveable(session.userId, saver = DiscoverySelection.saver) { DiscoverySelection() }
    var query by rememberSaveable(session.userId) { mutableStateOf("") }
    var category by rememberSaveable(session.userId) { mutableIntStateOf(0) }
    var catalogue by rememberSaveable(session.userId) { mutableStateOf(false) }
    var shown by rememberSaveable(query, category) { mutableIntStateOf(30) }
    if (catalogue) {
        MarketCatalogueScreen { catalogue = false }
        return
    }
    if (selection.archiveId != null) {
        ResearchLibraryScreen(state, { selection.archiveId = null }, initialId = selection.archiveId)
        return
    }
    val request = rememberWorkspaceRequest(parameters = mapOf("currency" to (snapshot?.totalValue?.currency ?: "RUB")),
        refreshKey = LocalWorkspaceRefreshKey.current)
    val research = rememberDiscoveryResearch()
    val results = discoveryResults(snapshot, personal, request.json, research.json, query)
    val chosen = results.rows.filter { portfolioRowKey(it) in selection.chosenKeys }
    WorkspaceDetailPage("Найти и исследовать", "Активы, счета, выплаты и ваши рабочие материалы", onBack, SpectrumSymbol.Market,
        adaptToIme = true) { padding ->
        val compact = LocalCompactWorkspaceInput.current
        Column(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)) {
            SpectrumTextField(query, { query = it.take(300) }, label = { Text("Поиск по приложению") }, singleLine = true,
                modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 8.dp).testTag("discovery-query"))
            SpectrumTabs(listOf("Всё", "Активы", "Счета", "Выплаты", "Исследования", "Страницы", "Наблюдение", "Календарь"),
                category, { category = it }, Modifier.padding(horizontal = 12.dp))
            DiscoveryResultList(results, snapshot, personal, request, research, selection, query, category, shown,
                { if (category == 0) category = 1 else shown += 30 }, { shown += 30 }, Modifier.weight(1f)) {
                if (compact) WorkspacePageHeading("Найти и исследовать", "Активы, счета, выплаты и ваши рабочие материалы")
                TextButton(onClick = { catalogue = true }) { Text("Каталог брокера · найти новые активы") }
                DiscoveryComparisonTray(selection, chosen.size)
            }
        }
    }
    DiscoveryOverlays(selection, results.rows, chosen, snapshot?.asOf, research)
}

@Composable
private fun DiscoveryComparisonTray(selection: DiscoverySelection, count: Int) {
    if (selection.chosenKeys.isEmpty()) return
    Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        TextButton(onClick = { selection.comparing = true }, enabled = count in 2..3) { Text("Сравнить ($count/3)") }
        TextButton(onClick = { selection.chosenKeys = emptyList() }) { Text("Снять выбор") }
        if (count != selection.chosenKeys.size) Text("Часть выбранных позиций отсутствует в текущем снимке.", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun DiscoveryResultList(results: DiscoveryResults, snapshot: PortfolioSnapshot?, personal: PersonalWorkspaceController,
    request: WorkspaceRequest, research: DiscoveryResearch, selection: DiscoverySelection,
    query: String, category: Int, shown: Int, moreAssets: () -> Unit, more: () -> Unit, modifier: Modifier,
    header: @Composable () -> Unit) {
    val navigate = LocalWorkspaceNavigator.current
    val destination = LocalPortfolioDestination.current
    LazyColumn(modifier.fillMaxWidth().semantics { testTagsAsResourceId = true }.testTag(WORKSPACE_CONTENT_TAG), contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
        item(key = "page-controls") {
            Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(workspaceGap)) { header() }
        }
        item(key = "scope") {
            Text("Поиск охватывает подключённый портфель, полученные события и материалы этого аккаунта.", style = MaterialTheme.typography.bodySmall)
            if (snapshot == null) Text("Позиции и счета ещё не получены. Личные записи и страницы доступны.")
            if (category in listOf(0, 3, 7)) WorkspaceRequestNotice(request)
        }
        if (category in listOf(0, 1)) discoveryAssets(results.assets, snapshot?.totalValue, selection, if (category == 0) 5 else shown, moreAssets)
        if (category in listOf(0, 2)) discoveryAccounts(results.accounts, destination)
        if (category in listOf(0, 3)) discoveryPayouts(results.payouts, request.json?.section("payouts"), selection,
            if (category == 0) 4 else shown, category == 3, more)
        if (category in listOf(0, 4)) discoveryResearch(results, research, selection, category == 0, shown, more)
        if (category in listOf(0, 5)) discoveryPages(results.pages, navigate)
        if (category == 6) discoveryWatches(results, personal, selection)
        if (category == 7) item(key = "calendar") { DiscoveryCalendar(request.json, query) { selection.standaloneUid = it } }
    }
}

private fun LazyListScope.discoveryAssets(assets: List<PortfolioRow>, total: MoneyAmount?, selection: DiscoverySelection,
    limit: Int, more: () -> Unit) {
    item(key = "asset-title") { SectionHeading("Активы · ${assets.size}") }
    items(assets.take(limit), key = { "asset:${portfolioRowKey(it)}" }) { row -> SpectrumCard(Modifier.testTag("discovery-asset-${portfolioRowKey(row)}")) {
        val rowKey = portfolioRowKey(row)
        PositionLine(row.position, total, row.account.name, sharedKey = rowKey) { selection.positionKey = rowKey }
        val selected = rowKey in selection.chosenKeys
        TextButton(onClick = { selection.toggleComparison(rowKey) }, enabled = selected || selection.chosenKeys.size < 3,
            modifier = Modifier.testTag("discovery-compare-$rowKey")) {
            Text(if (selected) "Убрать из сравнения" else "Добавить к сравнению")
        }
    } }
    if (assets.size > limit) item(key = "more-assets") { TextButton(onClick = more) { Text("Показать ещё активы") } }
    if (assets.isEmpty()) item(key = "no-assets") { Text("Подходящих позиций в полученном портфеле нет.") }
}

private fun LazyListScope.discoveryAccounts(accounts: List<PortfolioAccount>, destination: (PortfolioDestination) -> Unit) {
    item(key = "account-title") { SectionHeading("Счета · ${accounts.size}") }
    items(accounts, key = { "account:${it.id}" }) { account ->
        SpectrumCard(onClick = { destination(PortfolioDestination(accountId = account.id, section = 0)) }) {
            Text(account.name, style = MaterialTheme.typography.titleMedium)
            Text(account.totalValue.moneyText())
            Text("${account.positions.size} позиций · открыть счёт", style = MaterialTheme.typography.bodySmall)
        }
    }
}

private fun LazyListScope.discoveryPayouts(payouts: List<JSONObject>, section: JSONObject?, selection: DiscoverySelection,
    limit: Int, canShowMore: Boolean, more: () -> Unit) {
    item(key = "payout-title") { SectionHeading("Выплаты · ${payouts.size}"); WorkspaceSectionNotice(section) }
    items(payouts.take(limit), key = { "payout:${it.optString("id")}:${it.optString("account_id")}" }) { payout ->
        DiscoveryPayout(payout) { selection.standaloneUid = it }
    }
    if (canShowMore && payouts.size > limit) item(key = "more-payouts") { TextButton(onClick = more) { Text("Ещё выплаты") } }
}

private fun researchCardKey(card: JSONObject) = card.optionalText("instrument_uid") ?: dossierRecordKey("research", card)

private fun LazyListScope.discoveryResearch(results: DiscoveryResults, request: DiscoveryResearch, selection: DiscoverySelection,
    compact: Boolean, shown: Int, more: () -> Unit) {
    item(key = "research-title") {
        SectionHeading("Исследования · ${results.archives.size + results.cards.size}")
        DiscoveryResearchNotice(request)
    }
    items(results.archives.take(if (compact) 3 else shown), key = { "archive:${it.id}" }) { archive ->
        SpectrumCard(Modifier.testTag("discovery-archive-${archive.id}"), onClick = { selection.archiveId = archive.id }) {
            Text(archive.title, style = MaterialTheme.typography.titleMedium)
            Text("Сохранённый снимок · ${dateText(archive.observedAt)}", style = MaterialTheme.typography.bodySmall)
            Text(archive.source, style = MaterialTheme.typography.bodySmall)
            if (archive.note.isNotBlank()) Text(PrivateValue(archive.note))
        }
    }
    items(results.cards.take(if (compact) 3 else shown), key = { "research:${researchCardKey(it)}" }) { card ->
        SpectrumCard(Modifier.testTag("discovery-research-${researchCardKey(card)}"), onClick = { selection.researchKey = researchCardKey(card) }) {
            Text(card.optionalText("name") ?: "Разбор инструмента", style = MaterialTheme.typography.titleMedium)
            Text("Последний анализ · ${dateText(request.json?.optionalText("as_of"))}", style = MaterialTheme.typography.bodySmall)
            Text(PrivateValue(card.optionalText("explanation") ?: "Откройте разбор"))
        }
    }
    if (!compact && maxOf(results.archives.size, results.cards.size) > shown)
        item(key = "more-research") { TextButton(onClick = more) { Text("Ещё исследования") } }
}

@Composable
private fun DiscoveryResearchNotice(request: DiscoveryResearch) {
    if (request.loading) SpectrumLoadingIndicator(description = "Получаем последний анализ")
    request.error?.let {
        Text("Последний анализ: $it", color = MaterialTheme.colorScheme.error)
        TextButton(onClick = request.refresh) { Text("Повторить чтение анализа") }
    }
}

private fun LazyListScope.discoveryPages(pages: List<SearchPage>, navigate: (WorkspaceRoute) -> Unit) {
    item(key = "pages-title") { SectionHeading("Страницы и настройки · ${pages.size}") }
    items(pages, key = { "page:${it.route.name}" }) { page ->
        SpectrumActionTile(page.title, page.terms, SpectrumSymbol.Sources, { navigate(page.route) })
    }
}

private fun LazyListScope.discoveryWatches(results: DiscoveryResults, personal: PersonalWorkspaceController, selection: DiscoverySelection) {
    item(key = "watch-title") {
        SectionHeading("Моё наблюдение · ${results.watches.size}")
        Text("Причину добавления задаёте вы. Запись не является торговой рекомендацией.", style = MaterialTheme.typography.bodySmall)
        if (results.watches.isEmpty()) Text("Добавьте бумагу в наблюдение из краткого просмотра или её деталей.")
    }
    items(results.watches, key = { "watch:${it.uid}" }) { watch -> SpectrumCard {
        Text(watch.title, style = MaterialTheme.typography.titleMedium)
        Text(PrivateValue(watch.reason))
        val held = results.rows.filter { it.position.id == watch.uid }
        if (held.isEmpty()) Text("Бумага отсутствует в текущем снимке портфеля. Запись наблюдения сохранена.")
        else held.forEach { DataRow(it.account.name, it.position.currentValue.moneyText()) }
        // The dossier covers every account; a watch never silently picks the first holding.
        TextButton(onClick = { selection.standaloneUid = watch.uid }) { Text("Открыть бумагу на всех счетах") }
        TextButton(onClick = { personal.unwatch(watch.uid) }, enabled = !personal.busy) { Text("Убрать") }
    } }
    personal.error?.let { item(key = "watch-error") { Text(it, color = MaterialTheme.colorScheme.error) } }
}

@Composable
private fun DiscoveryOverlays(selection: DiscoverySelection, rows: List<PortfolioRow>, chosen: List<PortfolioRow>,
    observedAt: String?, research: DiscoveryResearch) {
    val row = rows.singleOrNull { portfolioRowKey(it) == selection.positionKey }
    if (row != null) InstrumentDetailsScreen(row.position, { selection.positionKey = null }, row.account.name,
        sharedKey = portfolioRowKey(row), accountId = row.account.id)
    else if (selection.positionKey != null) WorkspaceDialog("Позиция изменилась", { selection.positionKey = null }) {
        Text("В текущих данных этой позиции нет либо её идентификатор неоднозначен. Старая оценка не используется.")
        TextButton(onClick = { selection.positionKey = null }) { Text("Вернуться к поиску") }
    }
    if (selection.comparing) AssetComparisonDialog(chosen, observedAt, { selection.comparing = false })
    selection.standaloneUid?.let { uid -> DiscoveryDossier(uid) { selection.standaloneUid = null } }
    selection.researchKey?.let { key -> DiscoveryResearchDialog(key, research) { selection.researchKey = null } }
}

@Composable
private fun DiscoveryResearchDialog(selectedKey: String, request: DiscoveryResearch, close: () -> Unit) {
    val session = LocalWorkspaceSession.current
    val card = request.json?.records("cards")?.singleOrNull { researchCardKey(it) == selectedKey }
    Dialog(onDismissRequest = close, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        SpatialWindow(Modifier.fillMaxSize()) {
            SpectrumBackground(Modifier.fillMaxSize()) {
                LazyColumn(Modifier.fillMaxSize().semantics { testTagsAsResourceId = true }.testTag(WORKSPACE_CONTENT_TAG)
                    .windowInsetsPadding(WindowInsets.safeDrawing), contentPadding = PaddingValues(20.dp),
                    verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
                    item { TextButton(onClick = close) { Text("Закрыть разбор") }; DiscoveryResearchNotice(request) }
                    item {
                        when {
                            LocalWorkspacePreferences.current.value.hideHomeBalance -> Text("Разбор скрыт режимом приватности.")
                            card != null -> DiscoverySelectedResearch(checkNotNull(request.json), card, session.token)
                            request.loading -> Text("Получаем выбранную карточку по сохранённому идентификатору.")
                            else -> Text("Выбранная карточка не получена однозначно. Другой разбор вместо неё не показан.")
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun DiscoverySelectedResearch(research: JSONObject, card: JSONObject, token: String) {
    val payload = JSONObject(research.toString()).put("cards", JSONArray(listOf(card)))
    Text("Показана одна выбранная карточка. Общие выводы относятся к исходному анализу.")
    payload.remove("risk")
    payload.remove("examined_positions"); payload.remove("total_positions"); payload.remove("issuer_coverage_count")
    ResearchSnapshot(payload, token)
    SaveResearchButton(payload, "Разбор ${card.optString("name")}", card.optionalText("instrument_uid"), observedAt = payload.optionalText("as_of"))
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
internal fun DiscoveryDossier(uid: String, close: () -> Unit) {
    val request = rememberWorkspaceRequest("/workspace/instruments/$uid/dossier")
    Dialog(onDismissRequest = close, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        SpatialWindow(Modifier.fillMaxSize()) {
            SpectrumBackground(Modifier.fillMaxSize()) {
                LazyColumn(Modifier.fillMaxSize().semantics { testTagsAsResourceId = true }.testTag(WORKSPACE_CONTENT_TAG)
                    .windowInsetsPadding(WindowInsets.safeDrawing), contentPadding = PaddingValues(20.dp),
                    verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
                    item { TextButton(onClick = close) { Text("Закрыть досье") }; WorkspaceRequestNotice(request) }
                    request.json?.let { payload -> item {
                        when {
                            payload.optString("instrument_uid") != uid -> Text("Ответ относится к другому инструменту. Сведения не показаны.")
                            LocalWorkspacePreferences.current.value.hideHomeBalance -> Text("Досье скрыто режимом приватности.")
                            else -> InstrumentDossierContent(payload, onNavigate = close)
                        }
                    } }
                }
            }
        }
    }
}

@Composable
private fun DiscoveryCalendar(workspace: JSONObject?, query: String, onInstrument: (String) -> Unit) {
    var monthText by rememberSaveable { mutableStateOf(YearMonth.now(Moscow).toString()) }
    val month = runCatching { YearMonth.parse(monthText) }.getOrDefault(YearMonth.now(Moscow))
    val payouts = workspace?.sectionData("payouts")?.records("items").orEmpty()
    val events = workspace?.sectionData("events")?.records("items").orEmpty()
    SpectrumCard {
        Text("Календарь событий источников", style = MaterialTheme.typography.titleLarge)
        Column {
            TextButton(onClick = { monthText = month.minusMonths(1).toString() }) { Text("Предыдущий месяц") }
            TextButton(onClick = { monthText = YearMonth.now(Moscow).toString() }) { Text(month.toString()) }
            TextButton(onClick = { monthText = month.plusMonths(1).toString() }) { Text("Следующий месяц") }
        }
        val rows = (payouts.map { "payout" to it } + events.map { "event" to it }).filter { (_, value) ->
            val date = reportCalendarDate(value.optionalText("date") ?: value.optionalText("occurred_at"))
            date?.let { YearMonth.from(it) == month } == true &&
                (query.isBlank() || listOfNotNull(value.optionalText("title"), value.optionalText("summary")).any { it.contains(query, true) })
        }.sortedBy { (_, value) -> value.optionalText("date") ?: value.optionalText("occurred_at") }
        if (rows.isEmpty()) Text("В полученных данных за этот месяц событий нет. Неопубликованные события сюда не добавляются.")
        rows.forEach { (kind, row) ->
            if (kind == "payout") DiscoveryPayout(row, onInstrument)
            else WorkspaceEvents(listOf(row), workspace?.records("sources").orEmpty(), onInstrument)
        }
        WorkspaceSectionNotice(workspace?.section("payouts"))
        WorkspaceSectionNotice(workspace?.section("events"))
        Text("Объявленные даты отчётности доступны в досье каждой компании. События без даты не помещаются в вымышленный день.", style = MaterialTheme.typography.bodySmall)
    }
}
