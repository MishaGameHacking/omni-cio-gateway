package ru.omnicio.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.Layout
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.unit.Constraints
import java.math.BigDecimal
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.data.workspace.EncryptedWorkspaceStore
import ru.omnicio.app.data.workspace.JobCheckpointStore
import ru.omnicio.app.data.workspace.VolumeReply
import ru.omnicio.app.data.workspace.WorkspaceTransport
import ru.omnicio.app.ui.spectrum.SpectrumLoadingIndicator
import ru.omnicio.app.ui.AnalystNavigationPanels
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.workspace.*

private const val SYNTHETIC_CASH = "synthetic-cash"
private const val SYNTHETIC_ISSUER = "synthetic-issuer"
private const val SYNTHETIC_OPERATION = "synthetic-operation"
private const val SYNTHETIC_SNAPSHOT = "synthetic-snapshot"


/**
 * Debug-only contract fixture for production screens. Every value below is
 * synthetic. The transport has no HTTPS client, network fallback or auth bypass.
 * It validates mutations, records exact routes and returns deterministic states.
 */
@Composable
internal fun BusinessWorkspaceProbe(route: String, scenario: String, onBack: () -> Unit) {
    val initialRoute = route.removePrefix("business-")
    val supported = initialRoute in businessProbeRoutes && scenario in businessProbeScenarios &&
        (scenario != "job" || initialRoute in setOf("assistant", "plans"))
    if (!supported) {
        Text("ВИЗУАЛЬНЫЙ ТЕСТ · сценарий не реализован: $initialRoute/$scenario")
        return
    }
    val context = LocalContext.current
    val userId = rememberSaveable(initialRoute, scenario) { "synthetic-business-${UUID.randomUUID()}" }
    val transport = remember(userId, scenario) { BusinessProbeSessions.transport(userId, scenario) }
    val trace by transport.trace.collectAsState()
    var initialized by remember(userId) { mutableStateOf(false) }
    var page by rememberSaveable(initialRoute) { mutableStateOf(initialRoute) }
    val navigationFixture = initialRoute == "strategy" && scenario == "ready"
    val savedPages = rememberSaveableStateHolder()
    var revision by remember { mutableIntStateOf(0) }
    var navigation by rememberSaveable { mutableStateOf("none") }
    var chatContextJson by rememberSaveable { mutableStateOf(ChatContext("portfolio", title = "Синтетический тестовый портфель",
        accountId = PROBE_ACCOUNT, start = "2026-10-01", end = "2026-10-17").json()
        .put("title", "Синтетический тестовый портфель").toString()) }
    val chatContext = remember(chatContextJson) { JSONObject(chatContextJson).let { value -> ChatContext(
        mode = value.getString("mode"), instrumentUid = value.optString("instrument_uid").takeUnless { it.isBlank() || it == "null" },
        title = value.getString("title"), accountId = value.optString("account_id").takeUnless { it.isBlank() || it == "null" },
        start = value.optString("start").takeUnless { it.isBlank() || it == "null" },
        end = value.optString("end").takeUnless { it.isBlank() || it == "null" },
        eventId = value.optString("event_id").takeUnless { it.isBlank() || it == "null" }) } }
    LaunchedEffect(userId) {
        withContext(Dispatchers.IO) {
            val cache = EncryptedWorkspaceStore(context)
            cache.activateUser(userId)
            if (scenario == "job") check(JobCheckpointStore(context).save(userId, PROBE_REQUEST,
                if (initialRoute == "assistant") "/workspace/chat/threads/$PROBE_THREAD/messages"
                else "/workspace/plans/$PROBE_PLAN/reconcile", PROBE_JOB))
        }
        initialized = true
    }
    val marker = "business-probe:$initialRoute/$scenario;transport:synthetic;requests:${trace.requests};contract-errors:${trace.errors.size};navigation:$navigation" +
        ";message-posts:${trace.messagePosts};message-request-id:${trace.messageRequestId ?: "none"}" +
        ";by-request-gets:${trace.byRequestGets};recovered-request-id:${trace.recoveredRequestId ?: "none"}" +
        ";scenario-compares:${trace.scenarioComparisons};writes:${trace.mutations}"
    BusinessProbeFrame(disclosure = { compact ->
        BusinessProbeDisclosure(marker, "$initialRoute / $scenario", trace, navigation, compact)
    }) {
        if (!initialized) SpectrumLoadingIndicator(description = "Подготовка изолированного теста")
        else CompositionLocalProvider(
            LocalWorkspaceSession provides WorkspaceSession("debug-fixture-only", userId),
            LocalWorkspaceTransport provides transport,
            LocalWorkspaceRefreshKey provides revision,
            LocalWorkspaceInvalidate provides { revision++ },
            LocalWorkspaceRefresh provides { revision++ },
            LocalWorkspaceSnapshot provides transport.workspace(),
            LocalPortfolioSnapshot provides probePortfolio(),
            LocalPortfolioRefresh provides { revision++ },
            LocalReauthenticate provides { navigation = "sign-in" },
            LocalOpenAnalysisReport provides { navigation = "report:${it.orEmpty()}" },
            LocalChatContext provides chatContext,
            LocalAskAnalyst provides { chatContextJson = it.json().put("title", it.title).toString(); page = "assistant" },
            LocalEvidenceNavigator provides { navigation = "${it.section}:${it.id}:${it.accountId.orEmpty()}:${it.date.orEmpty()}" },
            LocalPortfolioDestination provides { navigation = "portfolio:${it.section}:${it.accountId.orEmpty()}:${it.query}" },
            LocalWorkspaceNavigator provides { destination ->
                when (destination) {
                    WorkspaceRoute.Assistant -> page = "assistant"
                    WorkspaceRoute.Strategies -> page = "strategy"
                    WorkspaceRoute.Messages -> page = "notifications"
                    WorkspaceRoute.AnalysisTimeline -> page = "analysis"
                    else -> navigation = "workspace:${destination.name}"
                }
            },
        ) {
            val workspace: @Composable () -> Unit = {
                when (page) {
                    "assistant" -> AssistantWorkspaceScreen(onBack, { navigation = "portfolio" }, { page = "plans" }, { page = "strategy" })
                    "risk" -> RiskWorkspaceScreen(onBack)
                    "plans" -> PlansWorkspaceScreen(onBack)
                    "strategy" -> LiveStrategyScreen(userId, onBack)
                    "notifications" -> NotificationEventsScreen(onBack)
                    "analysis" -> AnalysisTimelineScreen(onBack)
                    "catalogue" -> MarketCatalogueScreen(onBack)
                    "markets" -> MarketWorkspaceScreen(PortfolioUiState.Ready(probePortfolio()), onBack) { navigation = "portfolio" }
                    "appearance" -> AppearanceScreen(onBack)
                    "library" -> ResearchLibraryScreen(PortfolioUiState.Ready(probePortfolio()), onBack)
                }
            }
            if (navigationFixture) WorkspaceAutoSaveProvider {
                val preferences = LocalWorkspacePreferences.current.value
                val preferenceIdentity = listOf(preferences.accent.name, preferences.density.name, preferences.motion.name,
                    preferences.depth, preferences.hideHomeBalance, preferences.homeStructure,
                    preferences.haptics, preferences.brightLight).joinToString(",")
                val detailMarker = "navigation-detail:business-strategy/ready;transport:synthetic;page:$page;" +
                    "requests:${trace.requests};writes:${trace.mutations};contract-errors:${trace.errors.size};" +
                    "prefs:$preferenceIdentity;user:$userId"
                val selected = when (page) {
                    "strategy" -> WorkspaceRoute.Strategies; "markets" -> WorkspaceRoute.Market
                    "notifications" -> WorkspaceRoute.Messages; "assistant" -> WorkspaceRoute.Assistant
                    "appearance" -> WorkspaceRoute.Appearance; "library" -> WorkspaceRoute.Library
                    else -> null
                }
                BoxWithConstraints(Modifier.fillMaxSize().testTag("navigation-detail-page")
                    .semantics { contentDescription = detailMarker }) {
                    AnalystNavigationPanels(
                        selected = if (selected == WorkspaceRoute.Market) AnalystTab.Portfolio else AnalystTab.Profile,
                        selectedWorkspace = selected, wide = maxWidth >= 840.dp,
                        navigateTab = { navigation = "primary:${it.name}"; onBack() },
                        navigateWorkspace = { target ->
                            val next = when (target) {
                                WorkspaceRoute.Strategies -> "strategy"; WorkspaceRoute.Market -> "markets"
                                WorkspaceRoute.Messages -> "notifications"; WorkspaceRoute.Assistant -> "assistant"
                                WorkspaceRoute.Appearance -> "appearance"; WorkspaceRoute.Library -> "library"
                                else -> error("Unsupported synthetic detail destination")
                            }
                            navigation = "panel:${target.name}"
                            page = next
                        },
                    ) {
                        // Match the production per-destination state holder. A
                        // menu cancellation must keep the real editor instance.
                        savedPages.SaveableStateProvider(page) { workspace() }
                    }
                }
            } else WorkspaceAutoSaveProvider { Box(Modifier.fillMaxSize()) { workspace() } }
        }
    }
}

/** Two stable slots: changing their bounds must not recreate the focused workspace. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun BusinessProbeFrame(disclosure: @Composable (Boolean) -> Unit, content: @Composable () -> Unit) {
    BoxWithConstraints(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.safeDrawing)
        .semantics { testTagsAsResourceId = true }) {
        val compact = WindowInsets.isImeVisible && maxHeight < 240.dp
        Layout(content = {
            disclosure(compact)
            Box(Modifier.fillMaxSize()) { content() }
        }, modifier = Modifier.fillMaxSize()) { children, constraints ->
            // The disclosure must not narrow the production editor when a
            // taller IME appears. Keep both slots full width; the compact
            // disclosure scrolls within at most one third of the safe height.
            val markerConstraints = constraints.copy(
                minWidth = constraints.maxWidth, minHeight = 0,
                maxHeight = if (compact) minOf(64.dp.roundToPx(), constraints.maxHeight / 3)
                    else constraints.maxHeight,
            )
            val marker = children[0].measure(markerConstraints)
            val workspace = children[1].measure(Constraints.fixed(
                constraints.maxWidth, constraints.maxHeight - marker.height))
            layout(constraints.maxWidth, constraints.maxHeight) {
                marker.placeRelative(0, 0)
                workspace.placeRelative(0, marker.height)
            }
        }
    }
}

@Composable
private fun BusinessProbeDisclosure(marker: String, route: String, trace: ProbeTrace,
    navigation: String, compact: Boolean) {
    val detailStyle = MaterialTheme.typography.labelSmall.copy(fontSize = 10.sp, lineHeight = 13.sp)
    // The marker belongs to the visible viewport, so scrolling its details never
    // removes the transport/counter evidence from the native accessibility tree.
    Box(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.errorContainer)
        .testTag("business-probe-marker").semantics { contentDescription = marker },
        propagateMinConstraints = true) {
        Column(Modifier.verticalScroll(rememberScrollState()).padding(if (compact) 4.dp else 6.dp)) {
            if (compact) {
                Text("Синтетика · запр.${trace.requests} · ош.${trace.errors.size}", style = detailStyle)
            } else {
                Text("ВИЗУАЛЬНЫЙ ТЕСТ · НЕ РЕАЛЬНЫЕ ДАННЫЕ", style = MaterialTheme.typography.labelSmall)
                Text("$route · запросов ${trace.requests} · ошибок контракта ${trace.errors.size}", style = detailStyle)
                if (navigation != "none") Text("Тест перехода: $navigation", style = detailStyle)
                trace.errors.lastOrNull()?.let { Text(it, style = detailStyle) }
            }
        }
    }
}

internal val businessProbeRoutes = setOf("assistant", "risk", "plans", "strategy", "notifications", "analysis", "catalogue")
internal val businessProbeScenarios = setOf("ready", "empty", "partial", "error", "job")
private const val PROBE_AS_OF = "2026-10-17T10:00:00Z"
private const val PROBE_ACCOUNT = "synthetic-account"
private const val PROBE_STOCK = "synthetic-stock"
private const val PROBE_BOND = "synthetic-bond"
private const val PROBE_THREAD = "synthetic-thread"
private const val PROBE_PLAN = "synthetic-plan"
private const val PROBE_JOB = "synthetic-job"
private const val PROBE_REQUEST = "synthetic-request"
private const val PROBE_SOURCE = "synthetic-source"

private fun jObject(vararg pairs: Pair<String, Any?>) = JSONObject().apply { pairs.forEach { (key, value) -> put(key, value ?: JSONObject.NULL) } }
private fun jArray(vararg values: Any?) = JSONArray(values.toList())
private fun probeMoney(amount: String, currency: String = "RUB") = jObject("amount" to amount, "currency" to currency)
private fun probeSource() = jObject("id" to PROBE_SOURCE, "provider" to "СИНТЕТИЧЕСКИЙ источник визуального теста",
    "method" to "debug-only contract fixture", "observed_at" to PROBE_AS_OF, "published_at" to PROBE_AS_OF,
    "expires_at" to "2026-10-18T10:00:00Z", "subject_id" to PROBE_STOCK, "unit" to "money", "currency" to "RUB", "url" to null)

private fun probePortfolio(): PortfolioSnapshot {
    fun money(value: Long) = MoneyAmount(ApiDecimal(value, 0), "RUB")
    val positions = listOf(
        PortfolioPosition(PROBE_STOCK, "Синтетическая акция", "TEST1", ApiDecimal(70, 0), money(70_000), null,
            currentPrice = money(1_000), instrumentType = "share", sector = "Синтетический сектор"),
        PortfolioPosition(PROBE_BOND, "Синтетическая облигация", "TEST2", ApiDecimal(20, 0), money(20_000), null,
            currentPrice = money(1_000), instrumentType = "bond"),
        PortfolioPosition(SYNTHETIC_CASH, "Тестовый остаток", null, ApiDecimal(10_000, 0), money(10_000), null, instrumentType = "cash"),
    )
    return PortfolioSnapshot(money(100_000), null, null,
        listOf(PortfolioAccount(PROBE_ACCOUNT, "Синтетический счёт", money(100_000), null, positions)), emptyList(), PROBE_AS_OF)
}

private data class ProbeTrace(
    val requests: Int = 0,
    val mutations: Int = 0,
    val errors: List<String> = emptyList(),
    val messagePosts: Int = 0,
    val messageRequestId: String? = null,
    val byRequestGets: Int = 0,
    val recoveredRequestId: String? = null,
    val scenarioComparisons: Int = 0,
)

/** Keep the simulated server consistent across Activity recreation, like HTTPS would be. */
private object BusinessProbeSessions {
    private val sessions = linkedMapOf<String, BusinessProbeTransport>()
    @Synchronized fun transport(userId: String, scenario: String): BusinessProbeTransport {
        val key = "$userId:$scenario"
        return sessions.getOrPut(key) { BusinessProbeTransport(scenario) }.also {
            while (sessions.size > 8) sessions.remove(sessions.keys.first())
        }
    }
}

/** Every successful answer is a defensive copy, just like a decoded HTTP body. */
private class BusinessProbeTransport(private val scenario: String) : WorkspaceTransport {
    val trace = MutableStateFlow(ProbeTrace())
    private var version = if (scenario == "empty") 0 else 3
    private var config = strategyConfig()
    private var preview: JSONObject? = null
    private var sequence = 0
    private val chatContract = BusinessChatContract(PROBE_THREAD, PROBE_AS_OF)
    private val messages: MutableList<JSONObject> = if (scenario == "empty") mutableListOf() else mutableListOf(
        jObject("id" to "synthetic-question", "role" to "user", "text" to "Что подтверждено в этом тестовом портфеле?", "created_at" to PROBE_AS_OF),
        assistantMessage("synthetic-answer"),
    )
    private var hasThread = scenario != "empty"
    private val checks: MutableList<JSONObject> = if (scenario == "empty") mutableListOf() else mutableListOf(riskCheck("synthetic-check", "Синтетическая проверка концентрации"))
    private val plans: MutableList<JSONObject> = if (scenario == "empty") mutableListOf() else mutableListOf(plan())
    private val notifications: MutableList<JSONObject> = if (scenario == "empty") mutableListOf() else mutableListOf(
        jObject("id" to "synthetic-notification", "title" to "Синтетическое изменение лимита", "body" to "Тестовое событие: источник сообщил о превышении пользовательского лимита.",
            "state" to if (scenario == "partial") "pending" else "presented", "created_at" to PROBE_AS_OF, "source_card_id" to null),
        jObject("id" to "synthetic-read", "title" to "Синтетический просмотренный обзор", "body" to "В тесте прочтение не означает выполнение сделки.",
            "state" to "read", "created_at" to PROBE_AS_OF, "source_card_id" to "synthetic-analysis"),
    )
    private val jobs = mutableMapOf(PROBE_JOB to job(if (scenario == "job") "uncertain" else "running"))
    private val jobPolls = mutableMapOf<String, Int>()
    private val requestJobs = mutableMapOf(PROBE_REQUEST to PROBE_JOB)

    fun workspace(): JSONObject {
        val ai = timelineProbeAi(scenario)
        val sources = ai.optJSONObject("last_check")?.optJSONObject("trigger")?.records("sources").orEmpty()
        return jObject("schema_version" to 1, "snapshot_id" to SYNTHETIC_SNAPSHOT, "currency" to "RUB",
            "as_of" to PROBE_AS_OF, "sources" to JSONArray(listOf(probeSource()) + sources),
            "sections" to jObject("ai" to jObject("state" to if (scenario == "empty") "not_configured" else "available",
                "data" to ai, "as_of" to PROBE_AS_OF, "sources" to JSONArray(sources))))
    }

    @Synchronized
    override fun request(token: String, path: String, method: String, body: JSONObject?): VolumeReply {
        trace.value = trace.value.copy(requests = trace.value.requests + 1,
            mutations = trace.value.mutations + if (method == "GET") 0 else 1)
        if (token != "debug-fixture-only") return invalid("Unexpected fixture session")
        if (scenario == "error") return VolumeReply(error = "Синтетический отказ источника. Настоящая сеть не вызывалась.",
            code = "synthetic_source_failure", status = 503, retryable = true)
        val endpoint = path.substringBefore('?')
        return try {
            catalogueProbeReply(path, method, body, scenario)
                ?: routeCore(path, endpoint, method, body)
                ?: routeRisks(endpoint, method, body)
                ?: routeStrategy(endpoint, method, body)
                ?: routePlans(endpoint, method, body)
                ?: routeNotifications(endpoint, method, body)
                ?: routeChat(endpoint, method, body)
                ?: routeJobs(endpoint, method)
                ?: invalid("Unhandled fixture route: $method $endpoint")
        } catch (failure: Exception) { invalid("Fixture contract rejected $method $endpoint: ${failure.javaClass.simpleName}") }
    }

    private fun routeCore(
        path: String,
        endpoint: String,
        method: String,
        body: JSONObject?,
    ): VolumeReply? {
        return when {
            method == "GET" && endpoint == "/workspace" -> ok(workspace())
            method == "GET" && endpoint.startsWith("/workspace/analysis/checks/") ->
                observedAnalysisCheck(endpoint)
            method == "GET" && endpoint == "/workspace/analysis/diff" ->
                observedAnalysisDifference(path)
            method == "POST" && endpoint == "/workspace/analysis" -> startAnalysis(body)
            else -> null
        }
    }

    private fun routeRisks(endpoint: String, method: String, body: JSONObject?): VolumeReply? {
        return when {
            method == "GET" && endpoint == "/workspace/risks" -> ok(risks())
            method == "GET" && endpoint == "/workspace/risks/checks" ->
                ok(jObject("items" to JSONArray(checks)))
            method == "GET" && endpoint == "/workspace/risks/events" ->
                ok(jObject("items" to riskEvents()))
            method == "POST" && endpoint == "/workspace/risks/checks" -> createRiskCheck(body)
            method == "PATCH" && endpoint.startsWith("/workspace/risks/checks/") ->
                updateRiskCheck(endpoint, body)
            method == "POST" && endpoint == "/workspace/risks/scenario" ->
                ok(scenarioResult(body!!))
            method == "POST" && endpoint == "/workspace/risks/scenarios/compare" ->
                compareRiskScenarios(body)
            else -> null
        }
    }

    private fun routeStrategy(endpoint: String, method: String, body: JSONObject?): VolumeReply? {
        return when {
            method == "GET" && endpoint == "/workspace/strategy" -> ok(strategy())
            method == "POST" && endpoint == "/workspace/strategy/preview" -> previewStrategy(body)
            method == "POST" && endpoint == "/workspace/strategy/confirm" -> confirmStrategy(body)
            else -> null
        }
    }

    private fun routePlans(endpoint: String, method: String, body: JSONObject?): VolumeReply? {
        return when {
            method == "GET" && endpoint == "/workspace/plans" ->
                ok(jObject("items" to JSONArray(plans)))
            method == "POST" && endpoint == "/workspace/plans" -> createPlan(body)
            method == "POST" && endpoint.endsWith("/open-broker") ->
                VolumeReply(
                    status = 409,
                    code = "fixture_external_handoff_blocked",
                    error =
                        "В визуальном тесте внешний брокер не открывается. Переход не означает сделку.",
                )
            method == "POST" &&
                endpoint.startsWith("/workspace/plans/") &&
                endpoint.endsWith("/reconcile") -> reconcilePlan(endpoint, body)
            else -> null
        }
    }

    private fun routeNotifications(
        endpoint: String,
        method: String,
        body: JSONObject?,
    ): VolumeReply? {
        return when {
            method == "GET" && endpoint == "/workspace/notifications/events" ->
                ok(jObject("items" to JSONArray(notifications)))
            method == "POST" &&
                endpoint.startsWith("/workspace/notifications/") &&
                endpoint.endsWith("/ack") -> acknowledgeNotification(endpoint, body)
            else -> null
        }
    }

    private fun routeChat(endpoint: String, method: String, body: JSONObject?): VolumeReply? {
        return when {
            method == "GET" && endpoint == "/workspace/chat/threads" ->
                ok(
                    jObject(
                        "items" to
                            if (!hasThread) JSONArray()
                            else
                                jArray(
                                    jObject(
                                        "thread_id" to PROBE_THREAD,
                                        "title" to "Синтетический диалог",
                                        "updated_at" to PROBE_AS_OF,
                                    )
                                )
                    )
                )
            method == "POST" && endpoint == "/workspace/chat/threads" -> createChatThread()
            method == "GET" && endpoint == "/workspace/chat/threads/$PROBE_THREAD/messages" ->
                ok(jObject("items" to JSONArray(messages), "has_more" to false))
            method == "POST" && endpoint == "/workspace/chat/estimate" -> estimateChat(body)
            method == "POST" && endpoint == "/workspace/chat/threads/$PROBE_THREAD/messages" ->
                sendChat(body)
            else -> null
        }
    }

    private fun routeJobs(endpoint: String, method: String): VolumeReply? {
        return when {
            method == "GET" && endpoint.startsWith("/workspace/jobs/by-request/") ->
                recoverRequest(endpoint)
            method == "GET" && endpoint.startsWith("/workspace/jobs/") -> pollJob(endpoint)
            method == "POST" && endpoint.endsWith("/cancel") -> cancelJob(endpoint)
            else -> null
        }
    }

    private fun observedAnalysisCheck(endpoint: String): VolumeReply {
        val check =
            timelineProbeCheck(scenario, endpoint.substringAfterLast('/'))
                ?: return VolumeReply(
                    error = "Тестовая проверка не найдена.",
                    code = "not_found",
                    status = 404,
                )
        return ok(check)
    }

    private fun observedAnalysisDifference(path: String): VolumeReply {
        val parameters = fixtureQuery(path)
        require(parameters["current_card_id"] == "synthetic-analysis")
        require(parameters["previous_card_id"] in setOf(null, "synthetic-previous-analysis"))
        require(parameters["offset"]?.toIntOrNull() in setOf(null, 0))
        return ok(timelineProbeFacts())
    }

    private fun startAnalysis(body: JSONObject?): VolumeReply {
        require(body?.optString("reason") == "manual")
        if (scenario in setOf("empty", "partial"))
            return conflict("Синтетический анализ недоступен по состоянию источника.")
        return enqueue(body, "analysis")
    }

    private fun createRiskCheck(body: JSONObject?): VolumeReply {
        require(body?.optString("title")?.isNotBlank() == true)
        val created = riskCheck("synthetic-check-${++sequence}", body.getString("title"))
        checks.add(0, created)
        return ok(created)
    }

    private fun updateRiskCheck(endpoint: String, body: JSONObject?): VolumeReply {
        val check = checks.single { it.getString("id") == endpoint.substringAfterLast('/') }
        require(body?.optString("state") in setOf("pending", "reviewed"))
        val steps = check.getJSONArray("steps")
        val selected =
            (0 until steps.length())
                .map { steps.getJSONObject(it) }
                .single { it.getString("id") == body!!.getString("step_id") }
        selected.put("state", body!!.getString("state"))
        return ok(check)
    }

    private fun compareRiskScenarios(body: JSONObject?): VolumeReply {
        trace.value = trace.value.copy(scenarioComparisons = trace.value.scenarioComparisons + 1)
        val candidates = body!!.getJSONArray("scenarios")
        require(candidates.length() in 2..4 && body.optString("currency", "RUB") == "RUB")
        val seen = mutableSetOf<String>()
        val compared = JSONArray()
        repeat(candidates.length()) { index ->
            val candidate = candidates.getJSONObject(index)
            require(
                seen.add(candidate.getString("id")) && candidate.getString("title").isNotBlank()
            )
            compared.put(
                jObject(
                    "id" to candidate.getString("id"),
                    "title" to candidate.getString("title"),
                    "result" to scenarioResult(candidate),
                )
            )
        }
        return ok(
            jObject(
                "snapshot_id" to SYNTHETIC_SNAPSHOT,
                "as_of" to PROBE_AS_OF,
                "currency" to "RUB",
                "scenarios" to compared,
                "comparison_basis" to "same_observed_snapshot_same_currency",
                "assumptions_are_user_defined" to true,
            )
        )
    }

    private fun previewStrategy(body: JSONObject?): VolumeReply {
        if (body?.optInt("expected_version") != version)
            return conflict("Синтетический конфликт версии: пересчитайте предпросмотр.")
        require(body.has("config") xor body.has("rollback_to_version"))
        val candidate =
            if (body.has("config")) body.getJSONObject("config")
            else {
                require(body.getInt("rollback_to_version") == 2 && version > 0)
                strategyConfig("income")
            }
        require(validProbeStrategy(candidate))
        preview =
            jObject(
                "preview_id" to "synthetic-preview-${++sequence}",
                "expected_version" to version,
                "snapshot_id" to SYNTHETIC_SNAPSHOT,
                "config" to candidate,
                "can_confirm" to (scenario != "partial"),
                "expires_at" to "2026-10-18T10:10:00Z",
                "impact" to
                    jObject(
                        "coverage" to risks().optJSONArray("coverage"),
                        "breaches" to risks().optJSONArray("concentrations"),
                        "reserve_gap" to null,
                        "reserve_gap_basis" to
                            "observed_cash_balance_before_withdrawal_restrictions",
                        "withdrawable_cash" to null,
                        "execution_state" to "not_executed",
                        "warnings" to
                            if (scenario == "partial")
                                jArray(
                                    "Тест: источник части связей отсутствует; применение недоступно."
                                )
                            else JSONArray(),
                    ),
            )
        return ok(preview!!)
    }

    private fun confirmStrategy(body: JSONObject?): VolumeReply {
        val value = preview ?: return conflict("Сначала рассчитайте тестовый предпросмотр.")
        require(
            value.optBoolean("can_confirm") &&
                body?.optInt("expected_version") == version &&
                body.optString("preview_id") == value.getString("preview_id")
        )
        config = JSONObject(value.getJSONObject("config").toString())
        version++
        preview = null
        return ok(strategy())
    }

    private fun createPlan(body: JSONObject?): VolumeReply {
        require(
            body?.optString("account_id") == PROBE_ACCOUNT &&
                body.optString("instrument_uid") in setOf(PROBE_STOCK, PROBE_BOND)
        )
        require(
            body.getString("quantity").toBigDecimal().signum() > 0 &&
                body.getString("side") in setOf("buy", "sell")
        )
        require(body.optInt("strategy_version") == version)
        val created =
            plan()
                .put("id", "synthetic-plan-${++sequence}")
                .put("title", "СИНТЕТИЧЕСКИЙ РАСЧЁТ · " + body.optString("title"))
                .put("quantity", body.getString("quantity"))
                .put("instrument_uid", body.getString("instrument_uid"))
                .put("side", body.getString("side"))
                .put("state", "calculated")
                .put("executed_quantity", "0")
                .put("opened_at", JSONObject.NULL)
                .put("bound_operations", JSONArray())
                .put("candidate_operations", JSONArray())
                .put(
                    "calculation",
                    jObject(
                        "estimated_value" to
                            probeMoney(
                                body
                                    .getString("quantity")
                                    .toBigDecimal()
                                    .multiply(BigDecimal("1000"))
                                    .toPlainString()
                            )
                    ),
                )
        plans.add(0, created)
        return ok(created)
    }

    private fun reconcilePlan(endpoint: String, body: JSONObject?): VolumeReply {
        val plan = plans.single {
            it.getString("id") == endpoint.removeSuffix("/reconcile").substringAfterLast('/')
        }
        val identifiers = body?.optJSONArray("operation_ids")
        if (identifiers != null && identifiers.length() > 0) {
            require(
                (0 until identifiers.length()).all {
                    identifiers.getString(it) == SYNTHETIC_OPERATION
                }
            )
            val bound = plan.getJSONArray("bound_operations")
            if (
                (0 until bound.length()).none {
                    bound.getJSONObject(it).getString("id") == SYNTHETIC_OPERATION
                }
            ) {
                bound.put(syntheticOperation(SYNTHETIC_OPERATION, "3"))
                plan.put(
                    "executed_quantity",
                    plan
                        .getString("executed_quantity")
                        .toBigDecimal()
                        .add(BigDecimal("3"))
                        .toPlainString(),
                )
            }
            plan.put("state", "partial")
        }
        return enqueue(body)
    }

    private fun acknowledgeNotification(endpoint: String, body: JSONObject?): VolumeReply {
        require(body?.optString("state") == "read")
        val event = notifications.single {
            it.getString("id") == endpoint.removeSuffix("/ack").substringAfterLast('/')
        }
        event.put("state", "read")
        return ok(event)
    }

    private fun createChatThread(): VolumeReply {
        hasThread = true
        return ok(jObject("thread_id" to PROBE_THREAD))
    }

    private fun estimateChat(body: JSONObject?): VolumeReply {
        val request = requireNotNull(body)
        return ok(JSONObject(chatContract.estimate(chatRequest(request, request.get("thread_id") as String))))
    }

    private fun chatRequest(body: JSONObject, threadId: String): ProbeChatRequest {
        val context = body.getJSONObject("context")
        return ProbeChatRequest(threadId, body.get("text") as String, context.toString(),
            context.get("mode") as String, body.get("tier") as String)
    }

    private fun sendChat(body: JSONObject?): VolumeReply {
        val requestId = body?.optString("request_id").orEmpty()
        trace.value =
            trace.value.copy(
                messagePosts = trace.value.messagePosts + 1,
                messageRequestId = requestId,
            )
        val request = requireNotNull(body)
        chatContract.validateSend(requestId, chatRequest(request, PROBE_THREAD),
            request.opt("max_cost_micro_rub"), request.opt("expected_route_id"), request.opt("confirm_premium"))
        if (scenario == "ready" && trace.value.messagePosts != 1)
            return invalid("A lost chat response must not issue a second message POST")
        messages.add(
            jObject(
                "id" to "synthetic-user-${++sequence}",
                "role" to "user",
                "text" to request.getString("text"),
                "created_at" to PROBE_AS_OF,
            )
        )
        messages.add(assistantMessage("synthetic-answer-$sequence"))
        val accepted = enqueue(request, "chat")
        // The simulated server has accepted this exact request. Only
        // its response is lost; recovery must read the existing job.
        return if (scenario == "ready" && accepted.data != null)
            VolumeReply(
                error =
                    "СИНТЕТИЧЕСКАЯ потеря ответа после принятия запроса. Сверьте сохранённый идентификатор.",
                code = "synthetic_lost_response",
                ambiguous = true,
            )
        else accepted
    }

    private fun recoverRequest(endpoint: String): VolumeReply {
        val requestId = endpoint.substringAfterLast('/')
        trace.value = trace.value.copy(byRequestGets = trace.value.byRequestGets + 1)
        val id =
            requestJobs[requestId]
                ?: return VolumeReply(status = 404, error = "Тестовое задание не найдено.")
        trace.value = trace.value.copy(recoveredRequestId = requestId)
        return ok(jobs.getValue(id))
    }

    private fun pollJob(endpoint: String): VolumeReply {
        val id = endpoint.substringAfterLast('/')
        val value = jobs[id] ?: return invalid("Unknown fixture job")
        val polls = (jobPolls[id] ?: 0) + 1
        jobPolls[id] = polls
        if (value.optString("state") == "running" && polls >= 3)
            value.put("state", "completed").put("stage", "completed")
        return ok(value)
    }

    private fun cancelJob(endpoint: String): VolumeReply {
        val id = endpoint.removeSuffix("/cancel").substringAfterLast('/')
        val value = jobs.getValue(id)
        value.put("state", "cancelled").put("stage", "cancelled")
        return ok(value)
    }

private fun ok(data: JSONObject) = VolumeReply(data = JSONObject(data.toString()), status = 200)
    private fun fixtureQuery(path: String): Map<String, String> = path.substringAfter('?', "").split('&').mapNotNull { pair ->
        val parts = pair.split('=', limit = 2)
        if (parts.size != 2) null else java.net.URLDecoder.decode(parts[0], Charsets.UTF_8) to
            java.net.URLDecoder.decode(parts[1], Charsets.UTF_8)
    }.toMap()
    private fun conflict(message: String) = VolumeReply(error = message, code = "synthetic_conflict", status = 409)
    private fun invalid(message: String): VolumeReply {
        trace.value = trace.value.copy(errors = (trace.value.errors + message).takeLast(10))
        return VolumeReply(error = message, code = "fixture_contract_error", status = 422)
    }
    private fun enqueue(body: JSONObject?, kind: String = "reconcile"): VolumeReply {
        val request = body?.optString("request_id")?.takeIf(String::isNotBlank) ?: return invalid("Missing request_id")
        requestJobs[request]?.let { return ok(jobs.getValue(it)) }
        val id = "synthetic-job-${++sequence}"; requestJobs[request] = id; jobs[id] = job("running", id, request, kind)
        return ok(jobs.getValue(id))
    }
    private fun job(state: String, id: String = PROBE_JOB, requestId: String = PROBE_REQUEST, kind: String = "synthetic") =
        JSONObject(businessProbeJobPayload(id, requestId, kind, state, PROBE_AS_OF)).put("sources", jArray(probeSource()))
    private fun strategy() = jObject("active" to if (version == 0) null else jObject("version" to version, "confirmed_at" to PROBE_AS_OF, "config" to config),
        "history" to if (version == 0) JSONArray() else jArray(jObject("version" to 2, "confirmed_at" to "2026-10-16T10:00:00Z", "config" to strategyConfig("income"))))
    private fun strategyConfig(goal: String = "preservation") = jObject("goal" to goal, "horizon_months" to 36,
        "reserve" to probeMoney("10000"), "risk_level" to "moderate", "allowed_markets" to jArray("MOEX"),
        "limits" to jObject("position_percent" to "60", "issuer_percent" to "60", "group_percent" to "70", "sector_percent" to "80", "currency_percent" to "100"))
    private fun validProbeStrategy(candidate: JSONObject): Boolean {
        if (candidate.optString("goal") !in setOf("preservation", "income", "growth") || candidate.optInt("horizon_months") !in 1..600) return false
        if (candidate.optString("risk_level") !in setOf("conservative", "moderate", "aggressive")) return false
        val reserve = candidate.optJSONObject("reserve") ?: return false
        if (reserve.optString("currency") !in setOf("RUB", "USD", "EUR") || reserve.optString("amount").toBigDecimalOrNull()?.signum()?.let { it < 0 } != false) return false
        val limits = candidate.optJSONObject("limits") ?: return false
        return listOf("position_percent", "issuer_percent", "group_percent", "sector_percent", "currency_percent").all { field ->
            limits.optString(field).toBigDecimalOrNull()?.let { it.signum() > 0 && it <= BigDecimal("100") } == true
        }
    }
    private fun risks(): JSONObject {
        if (scenario == "empty") return jObject("as_of" to null, "snapshot_id" to null, "strategy_version" to 0, "coverage" to JSONArray(), "concentrations" to JSONArray())
        val partial = scenario == "partial"
        fun coverage(direction: String, known: Int, notApplicable: Int, missing: List<String> = emptyList()) = jObject(
            "direction" to direction, "state" to if (missing.isEmpty()) "available" else "partial", "known_positions" to known,
            "total_positions" to 3, "not_applicable_positions" to notApplicable, "missing_instrument_uids" to JSONArray(missing),
            "as_of" to PROBE_AS_OF, "age_seconds" to 0, "basis" to "СИНТЕТИЧЕСКИЙ тест подтверждённых наблюдений")
        return jObject("as_of" to PROBE_AS_OF, "snapshot_id" to SYNTHETIC_SNAPSHOT, "strategy_version" to version,
            "coverage" to jArray(coverage("issuer", if (partial) 1 else 2, 1, if (partial) listOf(PROBE_BOND) else emptyList()),
                coverage("ratings", if (partial) 0 else 1, 2, if (partial) listOf(PROBE_BOND) else emptyList()),
                coverage("trading", if (partial) 1 else 2, 1, if (partial) listOf(PROBE_BOND) else emptyList()),
                coverage("liquidity", if (partial) 1 else 2, 1, if (partial) listOf(PROBE_BOND) else emptyList()),
                coverage("position", 3, 0), coverage("currency", 3, 0)),
            "concentrations" to jArray(jObject("direction" to "issuer", "id" to SYNTHETIC_ISSUER, "label" to "Синтетическая компания",
                "value" to if (partial) null else probeMoney("70000"),
                "share_percent" to if (partial) null else "70", "limit_percent" to "60", "breached" to true.takeUnless { partial },
                "instrument_uids" to jArray(PROBE_STOCK), "source_ids" to jArray(PROBE_SOURCE))),
            "events" to riskEvents(), "sources" to jArray(probeSource()), "coverage_is_not_probability_of_loss" to true)
    }
    private fun riskEvents(): JSONArray {
        if (scenario == "empty") return JSONArray()
        fun rating(grade: String) = jObject("state" to "available", "warnings" to JSONArray(), "items" to jArray(jObject(
            "agency" to "СИНТЕТИЧЕСКОЕ агентство", "scale" to "Синтетическая национальная шкала", "subject_kind" to "issue",
            "subject_id" to PROBE_BOND, "grade" to grade, "status" to "active", "outlook" to "stable", "level_within_agency" to null)))
        return jArray(jObject("id" to "synthetic-risk-event", "kind" to "risk_limit_breached", "title" to "Синтетическое превышение лимита",
            "occurred_at" to PROBE_AS_OF, "instrument_uids" to jArray(PROBE_STOCK), "source_ids" to jArray(PROBE_SOURCE), "sources" to jArray(probeSource()),
            "details" to jObject("before" to jObject("share_percent" to "55"), "after" to jObject("share_percent" to "70"))),
            jObject("id" to "synthetic-rating-event", "kind" to if (scenario == "partial") "risk_rating_data_stale" else "risk_rating_changed",
                "title" to if (scenario == "partial") "Синтетический рейтинг: свежесть не подтверждена" else "Синтетическое изменение рейтинга выпуска",
                "occurred_at" to PROBE_AS_OF, "instrument_uids" to jArray(PROBE_BOND), "source_ids" to jArray(PROBE_SOURCE), "sources" to jArray(probeSource()),
                "details" to jObject("before" to rating("TEST-AA"), "after" to if (scenario == "partial") jObject("state" to "unavailable", "warnings" to jArray("Тестовый источник устарел"), "items" to JSONArray()) else rating("TEST-A"),
                    "critical" to false, "basis" to "reviewed_agency_records_not_a_default_probability", "missing_is_not_resolved" to (scenario == "partial"))))
    }
    private fun scenarioResult(candidate: JSONObject): JSONObject {
        val shocks = candidate.getJSONArray("shocks")
        require(shocks.length() == 1)
        val shock = shocks.getJSONObject(0)
        val percent = shock.getString("percent").toBigDecimal()
        require(percent >= BigDecimal(-100) && percent <= BigDecimal(1000))
        val axis = shock.getString("axis"); val id = shock.getString("id")
        val values = linkedMapOf(PROBE_STOCK to BigDecimal("70000"), PROBE_BOND to BigDecimal("20000"), SYNTHETIC_CASH to BigDecimal("10000"))
        val selected = when (axis) {
            "all" -> values
            "currency" -> { require(id == "RUB"); values }
            "instrument" -> { require(id in values); values.filterKeys { it == id } }
            "country" -> { require(id == "RU"); values.filterKeys { it != SYNTHETIC_CASH } }
            "sector" -> { require(id == "Синтетический сектор"); values.filterKeys { it == PROBE_STOCK } }
            else -> error("Unknown synthetic scenario axis")
        }
        val change = selected.values.fold(BigDecimal.ZERO, BigDecimal::add).multiply(percent).divide(BigDecimal(100))
        val unknown = if (scenario == "partial" && axis == "sector") listOf(PROBE_BOND) else emptyList()
        return jObject("snapshot_id" to SYNTHETIC_SNAPSHOT, "as_of" to PROBE_AS_OF, "baseline" to probeMoney("100000"),
            "estimated_change" to probeMoney(change.toPlainString()), "estimated_after" to if (unknown.isEmpty()) probeMoney(BigDecimal("100000").add(change).toPlainString()) else null,
            "covered_positions" to selected.size, "total_positions" to 3, "uncovered_instrument_uids" to JSONArray(unknown),
            "assumptions" to jArray(JSONObject(shock.toString())), "complete" to unknown.isEmpty(), "is_forecast" to false,
            "basis" to "user_shocks_linear_valuation_no_fx_or_derivative_model")
    }
    private fun riskCheck(id: String, title: String) = jObject("id" to id, "title" to title,
        "instrument_uids" to jArray(PROBE_STOCK), "steps" to jArray(
            jObject("id" to "source", "title" to "Открыть синтетический источник", "state" to "pending"),
            jObject("id" to "limit", "title" to "Сверить тестовый лимит", "state" to "reviewed")))
    private fun plan() = jObject("id" to PROBE_PLAN, "title" to "СИНТЕТИЧЕСКИЙ ПЛАН · акция", "instrument_uid" to PROBE_STOCK,
        "account_id" to PROBE_ACCOUNT, "quantity" to "10", "lot" to 1, "executed_quantity" to if (scenario == "partial") "2" else "0",
        "state" to if (scenario == "partial") "partial" else "calculated", "as_of" to PROBE_AS_OF,
        "opened_at" to if (scenario == "partial" || scenario == "job") PROBE_AS_OF else null, "broker_url" to null,
        "calculation" to jObject("estimated_value" to probeMoney("10000")), "reconciliation_complete" to (scenario != "partial"),
        "bound_operations" to if (scenario == "partial") jArray(syntheticOperation("synthetic-bound", "2")) else JSONArray(),
        "candidate_operations" to if (scenario == "partial") jArray(syntheticOperation("synthetic-bound", "2"), syntheticOperation(SYNTHETIC_OPERATION, "3")) else JSONArray(),
        "sources" to jArray(probeSource()))
    private fun syntheticOperation(id: String, quantity: String) = jObject("id" to id, "date" to PROBE_AS_OF, "quantity" to quantity,
        "payment" to probeMoney(BigDecimal(quantity).multiply(BigDecimal("-1000")).toPlainString()))
    private fun assistantMessage(id: String) = jObject("id" to id, "role" to "assistant", "created_at" to PROBE_AS_OF,
        "text" to if (scenario == "partial") "СИНТЕТИЧЕСКИЙ ОТВЕТ: часть исходных сведений отсутствует; точный вывод не подтверждён."
            else "СИНТЕТИЧЕСКИЙ ОТВЕТ: тестовая доля компании 70% сопоставлена с пользовательским лимитом 60%. Это проверка интерфейса, не инвестиционный совет.",
        "evidence" to jArray(jObject("source_id" to PROBE_SOURCE, "as_of" to PROBE_AS_OF)),
        "highlights" to jArray(jObject("section" to "instrument", "id" to PROBE_STOCK, "label" to "Показать синтетическую позицию"),
            jObject("section" to "history", "id" to "synthetic-history", "account_id" to PROBE_ACCOUNT, "date" to PROBE_AS_OF, "label" to "Показать синтетическую дату")),
        "claims" to jArray(jObject("text" to "Тестовая концентрация требует проверки", "fact_ids" to jArray("synthetic-fact"))),
        "facts" to jArray(jObject("id" to "synthetic-fact", "as_of" to PROBE_AS_OF, "source_ids" to jArray(PROBE_SOURCE),
            "value" to jObject("share_percent" to if (scenario == "partial") null else "70", "limit_percent" to "60"))),
        "sources" to jArray(probeSource()), "uncertainties" to if (scenario == "partial") jArray("СИНТЕТИЧЕСКИЙ тест отсутствующего рейтинга") else JSONArray(),
        "impact_hypothesis" to if (scenario == "ready" && id == "synthetic-answer") impactHypothesis() else null,
        "actions" to jArray(jObject("type" to "open_risks", "id" to SYNTHETIC_ISSUER, "label" to "Открыть тестовую концентрацию")))

    /** The UI receives server-owned facts separately from the explicitly hypothetical channel. */
    private fun impactHypothesis() = jObject("kind" to "hypothesis",
        "label" to "Гипотеза влияния ИИ — не подтверждённый факт",
        "event" to jObject("id" to "event:synthetic-impact-event", "title" to "СИНТЕТИЧЕСКОЕ событие влияния",
            "published_at" to PROBE_AS_OF, "fact_id" to "synthetic-event-fact", "event_identity_verified" to true, "source_ids" to jArray(PROBE_SOURCE)),
        "companies" to jArray(jObject("instrument_uid" to PROBE_STOCK, "issuer_id" to SYNTHETIC_ISSUER,
            "issuer_name" to "СИНТЕТИЧЕСКИЙ эмитент гипотезы", "identity_state" to "verified",
            "fact_id" to "synthetic-company-fact", "source_ids" to jArray(PROBE_SOURCE))),
        "positions" to jArray(jObject("instrument_uid" to PROBE_STOCK, "account_id" to PROBE_ACCOUNT,
            "account_name" to "Синтетический счёт", "quantity" to "70", "value" to probeMoney("70000"),
            "as_of" to PROBE_AS_OF, "fact_id" to "synthetic-position-fact", "source_ids" to jArray(PROBE_SOURCE))),
        "channels" to jArray(jObject("mechanism" to "СИНТЕТИЧЕСКИЙ канал: издержки компании могут измениться",
            "direction" to "unknown", "horizon" to "unclear", "uncertainty" to "СИНТЕТИЧЕСКАЯ неопределённость: величина изменения не подтверждена",
            "assumptions" to jArray("СИНТЕТИЧЕСКОЕ допущение: компания использует затронутый ресурс"),
            "fact_ids" to jArray("synthetic-event-fact", "synthetic-company-fact", "synthetic-position-fact"), "source_ids" to jArray(PROBE_SOURCE))),
        "limitations" to jArray("СИНТЕТИЧЕСКИЙ пример: численное влияние не рассчитано"),
        "sources" to jArray(probeSource()), "snapshot_id" to SYNTHETIC_SNAPSHOT, "as_of" to PROBE_AS_OF,
        "computed_financial_impact" to null)
}
