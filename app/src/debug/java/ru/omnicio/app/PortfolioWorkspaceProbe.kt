package ru.omnicio.app

import androidx.activity.compose.LocalActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.UriHandler
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import java.net.URI
import java.util.UUID
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.data.portfolio.PortfolioUiState
import ru.omnicio.app.data.workspace.EncryptedWorkspaceStore
import ru.omnicio.app.data.workspace.LocalPortfolioReadSource
import ru.omnicio.app.data.workspace.PersonalWorkspaceStore
import ru.omnicio.app.ui.portfolio.PortfolioScreen
import ru.omnicio.app.ui.spatial.SpatialBackHandler
import ru.omnicio.app.ui.spectrum.SpectrumLoadingIndicator
import ru.omnicio.app.ui.workspace.*

internal val portfolioProbeRoutes = setOf("discovery", "dossier", "history", "quotes", "markets", "appearance")
internal val portfolioProbeCases = setOf("discovery" to "ready", "dossier" to "ready", "history" to "ready",
    "history" to "partial", "quotes" to "ready", "markets" to "ready", "appearance" to "ready")

/** Production screens with synthetic read transports; source-set isolation is the only fixture switch. */
@Composable
internal fun PortfolioWorkspaceProbe(route: String, scenario: String, onBack: () -> Unit) {
    val initialRoute = route.removePrefix("portfolio-")
    if ((initialRoute to scenario) !in portfolioProbeCases) {
        Text("ВИЗУАЛЬНЫЙ ТЕСТ · сценарий не реализован: $initialRoute/$scenario")
        return
    }
    val activity = LocalActivity.current
    val context = LocalContext.current
    val suppliedRun = activity?.intent?.getStringExtra("spectrum_probe_run")?.takeIf { it.matches(Regex("[a-f0-9]{32}")) }
    val runId = rememberSaveable(initialRoute, scenario) { suppliedRun ?: UUID.randomUUID().toString().replace("-", "") }
    val userId = "synthetic-portfolio-$runId"
    val transport = remember(userId, scenario) { PortfolioProbeSessions.transport(userId, scenario) }
    val data = transport.data
    val trace by transport.trace.collectAsState()
    val snapshot = remember(transport) { data.snapshot() }
    val state = remember(snapshot) { PortfolioUiState.Ready(snapshot) }
    val initialPage = when (initialRoute) { "dossier", "history", "quotes" -> "portfolio"; else -> initialRoute }
    var page by rememberSaveable(initialRoute, scenario) { mutableStateOf(initialPage) }
    var initialized by remember(userId) { mutableStateOf(false) }
    var preparationError by remember(userId) { mutableStateOf<String?>(null) }
    var revision by remember { mutableIntStateOf(0) }
    var pendingDestination by rememberSaveable(initialRoute, scenario) { mutableStateOf(initialProbeDestination(initialRoute)?.toString()) }
    var destinationJson by rememberSaveable(initialRoute, scenario) { mutableStateOf(pendingDestination ?: "{}") }
    var navigationErrors by rememberSaveable { mutableStateOf(emptyList<String>()) }
    var openedSources by rememberSaveable { mutableStateOf(emptyList<String>()) }
    var chatContextJson by rememberSaveable { mutableStateOf(ChatContext().json().put("title", "СИНТЕТИЧЕСКИЙ портфель").toString()) }
    val chatContext = remember(chatContextJson) { probeChatContext(JSONObject(chatContextJson)) }
    val savedPages = rememberSaveableStateHolder()
    val back: () -> Unit = { if (page == initialPage) onBack() else page = initialPage }
    val openPortfolio: (PortfolioDestination) -> Unit = { target ->
        pendingDestination = target.probeJson().toString()
        destinationJson = pendingDestination!!
        page = "portfolio"
    }
    SpatialBackHandler(page != initialPage, onBack = back)
    LaunchedEffect(userId) {
        try {
            withContext(Dispatchers.IO) { EncryptedWorkspaceStore(context).activateUser(userId) }
            seedPersonalWorkspace(PersonalWorkspaceStore(context, userId), data)
            initialized = true
        } catch (cancelled: CancellationException) { throw cancelled }
        catch (_: Exception) { preparationError = "Не удалось подготовить изолированное зашифрованное хранилище" }
    }
    val preferences = LocalWorkspacePreferences.current.value
    val transcript = data.obj("route" to initialRoute, "scenario" to scenario, "run_id" to runId,
        "initialized" to initialized, "current_page" to page, "request_count" to trace.count,
        "calls" to JSONArray(trace.calls.map { it.json() }), "contract_errors" to (trace.errors.size + navigationErrors.size),
        "destination" to JSONObject(destinationJson), "opened_sources" to JSONArray(openedSources),
        "chat_context" to JSONObject(chatContextJson), "day" to data.day.toString(),
        "history_start" to data.historyStart, "history_end" to data.historyEnd, "history_instant" to data.historyInstant,
        "prefs" to data.obj("motion" to preferences.motion.name, "bright_light" to preferences.brightLight,
            "accent" to preferences.accent.name, "depth" to preferences.depth, "density" to preferences.density.name))
    val marker = "portfolio-probe:$initialRoute/$scenario;transport:synthetic;initialized:$initialized;requests:${trace.count};" +
        "contract-errors:${trace.errors.size + navigationErrors.size};page:$page;run:$runId"
    val uriHandler = remember {
        object : UriHandler {
            override fun openUri(uri: String) {
                val permitted = runCatching { URI(uri).let { it.scheme == "https" && it.host == "example.invalid" &&
                    it.userInfo == null && it.path.startsWith("/synthetic/") } }.getOrDefault(false)
                if (permitted) openedSources = (openedSources + uri).takeLast(16)
                else navigationErrors = (navigationErrors + "Открыт неожиданный внешний источник").takeLast(16)
            }
        }
    }
    // Use the same stable disclosure/content slots as the business fixture.
    // A large-font IME can leave too little height for a fixed banner above input.
    BusinessProbeFrame(disclosure = { compact ->
        val detailStyle = MaterialTheme.typography.labelSmall.copy(fontSize = 10.sp, lineHeight = 13.sp)
        Box(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.errorContainer)
            .testTag("portfolio-probe").semantics { contentDescription = marker }, propagateMinConstraints = true) {
            Column(Modifier.verticalScroll(rememberScrollState()).padding(if (compact) 4.dp else 6.dp)) {
                Text(if (compact) "Синтетика" else "ВИЗУАЛЬНЫЙ ТЕСТ · НЕ РЕАЛЬНЫЕ ДАННЫЕ",
                    style = MaterialTheme.typography.labelSmall)
                Text(if (compact) "Запр.${trace.count} · ош.${trace.errors.size + navigationErrors.size}"
                    else "$initialRoute / $scenario · запросов ${trace.count} · ошибок ${trace.errors.size + navigationErrors.size}",
                    style = detailStyle)
                preparationError?.let { Text(it, style = detailStyle) }
                (trace.errors + navigationErrors).lastOrNull()?.let { Text(it, style = detailStyle) }
            }
            Box(Modifier.align(Alignment.TopEnd).size(2.dp).testTag("portfolio-probe-transcript")
                .clearAndSetSemantics { contentDescription = transcript.toString() })
        }
    }) {
        if (!initialized) SpectrumLoadingIndicator(description = "Подготовка изолированного портфельного теста")
        else CompositionLocalProvider(
            LocalWorkspaceSession provides WorkspaceSession(PORTFOLIO_PROBE_TOKEN, userId),
            LocalWorkspaceTransport provides transport,
            LocalPortfolioReadSource provides transport,
            LocalWorkspaceRefreshKey provides revision,
            LocalWorkspaceRefresh provides { revision++ },
            LocalWorkspaceInvalidate provides { revision++ },
            LocalPortfolioRefresh provides { revision++ },
            LocalWorkspaceSnapshot provides data.workspace(),
            LocalPortfolioSnapshot provides snapshot,
            LocalPortfolioDestination provides openPortfolio,
            LocalChatContext provides chatContext,
            LocalAskAnalyst provides { chatContextJson = it.json().put("title", it.title).toString(); page = "assistant" },
            LocalUriHandler provides uriHandler,
            LocalReauthenticate provides { navigationErrors = navigationErrors + "Неожиданный возврат на вход" },
            LocalWorkspaceNavigator provides { target ->
                val next = when (target) {
                    WorkspaceRoute.Discovery -> "discovery"
                    WorkspaceRoute.Library -> "library"
                    WorkspaceRoute.Market -> "markets"
                    WorkspaceRoute.Appearance -> "appearance"
                    WorkspaceRoute.Assistant -> "assistant"
                    else -> null
                }
                if (next != null) page = next
                else navigationErrors = navigationErrors + "Маршрут ${target.name} не входит в этот портфельный сценарий"
            },
        ) {
            Box(Modifier.fillMaxSize()) {
                savedPages.SaveableStateProvider(page) {
                    when (page) {
                        "discovery" -> DiscoveryWorkspaceScreen(state, back)
                        "library" -> ResearchLibraryScreen(state, back)
                        "markets" -> MarketWorkspaceScreen(state, back) { openPortfolio(PortfolioDestination()) }
                        "appearance" -> AppearanceScreen(back)
                        "assistant" -> AssistantWorkspaceScreen(back, { openPortfolio(PortfolioDestination()) },
                            { navigationErrors = navigationErrors + "Переход к действиям вне сценария" },
                            { navigationErrors = navigationErrors + "Переход к стратегии вне сценария" })
                        "portfolio" -> PortfolioScreen(state, onProfileClick = back, accessToken = PORTFOLIO_PROBE_TOKEN,
                            destination = pendingDestination?.let { probeDestination(JSONObject(it)) },
                            onDestinationConsumed = { pendingDestination = null },
                            initialHistoryDate = data.historyInstant.takeIf { initialRoute == "history" },
                            initialHistoryStart = data.historyStart.takeIf { initialRoute == "history" },
                            initialHistoryEnd = data.historyEnd.takeIf { initialRoute == "history" },
                            initialHistoryResolution = "hour".takeIf { initialRoute == "history" })
                    }
                }
            }
        }
    }
}

private fun initialProbeDestination(route: String): JSONObject? = when (route) {
    "dossier" -> PortfolioDestination(accountId = PORTFOLIO_PROBE_ACCOUNT_A, query = PORTFOLIO_PROBE_SHARE_A).probeJson()
    "quotes" -> PortfolioDestination(accountId = PORTFOLIO_PROBE_ACCOUNT_A, query = PORTFOLIO_PROBE_BOND).probeJson()
    "history" -> PortfolioDestination(section = 3, accountId = PORTFOLIO_PROBE_ACCOUNT_A).probeJson()
    else -> null
}

private fun PortfolioDestination.probeJson() = JSONObject().put("section", section)
    .put("account_id", accountId ?: JSONObject.NULL).put("query", query)
    .put("sector", sector ?: JSONObject.NULL).put("kind", kind ?: JSONObject.NULL)
    .put("operation_id", operationId ?: JSONObject.NULL).put("operation_date", operationDate ?: JSONObject.NULL)

private fun JSONObject.optional(key: String): String? = (opt(key) as? String)?.takeIf(String::isNotBlank)
private fun probeDestination(value: JSONObject) = PortfolioDestination(value.optInt("section", 1), value.optional("account_id"),
    value.optString("query"), value.optional("sector"), value.optional("kind"), value.optional("operation_id"), value.optional("operation_date"))
private fun probeChatContext(value: JSONObject) = ChatContext(value.optString("mode", "portfolio"), value.optional("instrument_uid"),
    value.optString("title", "СИНТЕТИЧЕСКИЙ портфель"), value.optional("account_id"), value.optional("start"), value.optional("end"),
    eventId = value.optional("event_id"))

/** Seed once per explicit run ID. Never overwrite records during rotation or a persistence restart. */
private suspend fun seedPersonalWorkspace(store: PersonalWorkspaceStore, data: PortfolioProbeData) {
    if (store.read().optBoolean("portfolio_probe_seeded")) return
    val archiveId = "synthetic-saved-research"
    check(store.saveArchive(archiveId, data.research()))
    store.change { json ->
        json.put("research", JSONArray(listOf(data.obj("id" to archiveId, "title" to "СИНТЕТИЧЕСКИЙ архив ARCHIVE",
            "instrument_id" to PORTFOLIO_PROBE_SHARE_A, "start" to data.historyStart, "end" to data.historyEnd,
            "source" to "СИНТЕТИЧЕСКИЙ сохранённый источник", "observed_at" to data.asOf,
            "captured_at" to data.asOf, "note" to "СИНТЕТИЧЕСКАЯ заметка: проверить исходный период"))))
        json.put("watchlist", JSONArray(listOf(data.obj("uid" to PORTFOLIO_PROBE_SHARE_A,
            "title" to "СИНТЕТИЧЕСКАЯ компания", "reason" to "СИНТЕТИЧЕСКАЯ причина: изучить отчётность", "created_at" to data.asOf))))
        json.put("portfolio_probe_seeded", true)
    }
}
