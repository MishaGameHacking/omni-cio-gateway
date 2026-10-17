package ru.omnicio.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
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
import ru.omnicio.app.ui.workspace.*

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
    var revision by remember { mutableIntStateOf(0) }
    var navigation by rememberSaveable { mutableStateOf("none") }
    var chatContextJson by rememberSaveable { mutableStateOf(ChatContext("portfolio", title = "Синтетический тестовый портфель",
        accountId = PROBE_ACCOUNT, start = "2026-10-01", end = "2026-10-17").json()
        .put("title", "Синтетический тестовый портфель").toString()) }
    val chatContext = remember(chatContextJson) { JSONObject(chatContextJson).let { value -> ChatContext(
        mode = value.getString("mode"), instrumentUid = value.optString("instrument_uid").takeUnless { it.isBlank() || it == "null" },
        title = value.getString("title"), accountId = value.optString("account_id").takeUnless { it.isBlank() || it == "null" },
        start = value.optString("start").takeUnless { it.isBlank() || it == "null" },
        end = value.optString("end").takeUnless { it.isBlank() || it == "null" }) } }
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
    val marker = "business-probe:$initialRoute/$scenario;transport:synthetic;requests:${trace.requests};contract-errors:${trace.errors.size};navigation:$navigation"
    Column(Modifier.fillMaxSize().semantics { testTagsAsResourceId = true }) {
        Column(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.errorContainer).statusBarsPadding().padding(6.dp)
            .testTag("business-probe-marker").semantics { contentDescription = marker }) {
            Text("ВИЗУАЛЬНЫЙ ТЕСТ · НЕ РЕАЛЬНЫЕ ДАННЫЕ", style = MaterialTheme.typography.labelSmall)
            Text("$initialRoute / $scenario · запросов ${trace.requests} · ошибок контракта ${trace.errors.size}", fontSize = 10.sp)
            if (navigation != "none") Text("Тест перехода: $navigation", fontSize = 10.sp)
            trace.errors.lastOrNull()?.let { Text(it, fontSize = 10.sp) }
        }
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
                    else -> navigation = "workspace:${destination.name}"
                }
            },
        ) {
            Box(Modifier.weight(1f).fillMaxWidth()) {
                when (page) {
                    "assistant" -> AssistantWorkspaceScreen(onBack, { navigation = "portfolio" }, { page = "plans" }, { page = "strategy" })
                    "risk" -> RiskWorkspaceScreen(onBack)
                    "plans" -> PlansWorkspaceScreen(onBack)
                    "strategy" -> LiveStrategyScreen(userId, onBack)
                    "notifications" -> NotificationEventsScreen(onBack)
                }
            }
        }
    }
}

internal val businessProbeRoutes = setOf("assistant", "risk", "plans", "strategy", "notifications")
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
        PortfolioPosition("synthetic-cash", "Тестовый остаток", null, ApiDecimal(10_000, 0), money(10_000), null, instrumentType = "cash"),
    )
    return PortfolioSnapshot(money(100_000), null, null,
        listOf(PortfolioAccount(PROBE_ACCOUNT, "Синтетический счёт", money(100_000), null, positions)), emptyList(), PROBE_AS_OF)
}

private data class ProbeTrace(val requests: Int = 0, val errors: List<String> = emptyList())

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

    fun workspace(): JSONObject = jObject("schema_version" to 1, "snapshot_id" to "synthetic-snapshot", "currency" to "RUB",
        "as_of" to PROBE_AS_OF, "sources" to jArray(probeSource()), "sections" to JSONObject())

    @Synchronized
    override fun request(token: String, path: String, method: String, body: JSONObject?): VolumeReply {
        trace.value = trace.value.copy(requests = trace.value.requests + 1)
        if (token != "debug-fixture-only") return invalid("Unexpected fixture session")
        if (scenario == "error") return VolumeReply(error = "Синтетический отказ источника. Настоящая сеть не вызывалась.",
            code = "synthetic_source_failure", status = 503, retryable = true)
        val endpoint = path.substringBefore('?')
        return try {
            when {
                method == "GET" && endpoint == "/workspace" -> ok(workspace())
                method == "GET" && endpoint == "/workspace/risks" -> ok(risks())
                method == "GET" && endpoint == "/workspace/risks/checks" -> ok(jObject("items" to JSONArray(checks)))
                method == "GET" && endpoint == "/workspace/risks/events" -> ok(jObject("items" to riskEvents()))
                method == "POST" && endpoint == "/workspace/risks/checks" -> {
                    require(body?.optString("title")?.isNotBlank() == true)
                    val created = riskCheck("synthetic-check-${++sequence}", body.getString("title"))
                    checks.add(0, created); ok(created)
                }
                method == "PATCH" && endpoint.startsWith("/workspace/risks/checks/") -> {
                    val check = checks.single { it.getString("id") == endpoint.substringAfterLast('/') }
                    require(body?.optString("state") in setOf("pending", "reviewed"))
                    val steps = check.getJSONArray("steps")
                    val selected = (0 until steps.length()).map { steps.getJSONObject(it) }.single { it.getString("id") == body!!.getString("step_id") }
                    selected.put("state", body!!.getString("state")); ok(check)
                }
                method == "POST" && endpoint == "/workspace/risks/scenario" -> ok(scenarioResult(body!!))
                method == "POST" && endpoint == "/workspace/risks/scenarios/compare" -> {
                    val candidates = body!!.getJSONArray("scenarios")
                    require(candidates.length() in 2..4 && body.optString("currency", "RUB") == "RUB")
                    val seen = mutableSetOf<String>()
                    val compared = JSONArray()
                    repeat(candidates.length()) { index ->
                        val candidate = candidates.getJSONObject(index)
                        require(seen.add(candidate.getString("id")) && candidate.getString("title").isNotBlank())
                        compared.put(jObject("id" to candidate.getString("id"), "title" to candidate.getString("title"), "result" to scenarioResult(candidate)))
                    }
                    ok(jObject("snapshot_id" to "synthetic-snapshot", "as_of" to PROBE_AS_OF, "currency" to "RUB", "scenarios" to compared,
                        "comparison_basis" to "same_observed_snapshot_same_currency", "assumptions_are_user_defined" to true))
                }
                method == "GET" && endpoint == "/workspace/strategy" -> ok(strategy())
                method == "POST" && endpoint == "/workspace/strategy/preview" -> {
                    if (body?.optInt("expected_version") != version) return conflict("Синтетический конфликт версии: пересчитайте предпросмотр.")
                    require(body.has("config") xor body.has("rollback_to_version"))
                    val candidate = if (body.has("config")) body.getJSONObject("config") else {
                        require(body.getInt("rollback_to_version") == 2 && version > 0)
                        strategyConfig("income")
                    }
                    require(validProbeStrategy(candidate))
                    preview = jObject("preview_id" to "synthetic-preview-${++sequence}", "expected_version" to version,
                        "snapshot_id" to "synthetic-snapshot", "config" to candidate,
                        "can_confirm" to (scenario != "partial"), "expires_at" to "2026-10-18T10:10:00Z",
                        "impact" to jObject("coverage" to risks().optJSONArray("coverage"), "breaches" to risks().optJSONArray("concentrations"),
                            "reserve_gap" to null, "reserve_gap_basis" to "observed_cash_balance_before_withdrawal_restrictions",
                            "withdrawable_cash" to null, "execution_state" to "not_executed",
                            "warnings" to if (scenario == "partial") jArray("Тест: источник части связей отсутствует; применение недоступно.") else JSONArray()))
                    ok(preview!!)
                }
                method == "POST" && endpoint == "/workspace/strategy/confirm" -> {
                    val value = preview ?: return conflict("Сначала рассчитайте тестовый предпросмотр.")
                    require(value.optBoolean("can_confirm") && body?.optInt("expected_version") == version && body.optString("preview_id") == value.getString("preview_id"))
                    config = JSONObject(value.getJSONObject("config").toString()); version++; preview = null; ok(strategy())
                }
                method == "GET" && endpoint == "/workspace/plans" -> ok(jObject("items" to JSONArray(plans)))
                method == "POST" && endpoint == "/workspace/plans" -> {
                    require(body?.optString("account_id") == PROBE_ACCOUNT && body.optString("instrument_uid") in setOf(PROBE_STOCK, PROBE_BOND))
                    require(body.getString("quantity").toBigDecimal().signum() > 0 && body.getString("side") in setOf("buy", "sell"))
                    require(body.optInt("strategy_version") == version)
                    val created = plan().put("id", "synthetic-plan-${++sequence}").put("title", "СИНТЕТИЧЕСКИЙ РАСЧЁТ · " + body.optString("title"))
                        .put("quantity", body.getString("quantity")).put("instrument_uid", body.getString("instrument_uid"))
                        .put("side", body.getString("side")).put("state", "calculated").put("executed_quantity", "0")
                        .put("opened_at", JSONObject.NULL).put("bound_operations", JSONArray()).put("candidate_operations", JSONArray())
                        .put("calculation", jObject("estimated_value" to probeMoney(body.getString("quantity").toBigDecimal().multiply(BigDecimal("1000")).toPlainString())))
                    plans.add(0, created); ok(created)
                }
                method == "POST" && endpoint.endsWith("/open-broker") -> VolumeReply(status = 409, code = "fixture_external_handoff_blocked",
                    error = "В визуальном тесте внешний брокер не открывается. Переход не означает сделку.")
                method == "POST" && endpoint.startsWith("/workspace/plans/") && endpoint.endsWith("/reconcile") -> {
                    val plan = plans.single { it.getString("id") == endpoint.removeSuffix("/reconcile").substringAfterLast('/') }
                    val identifiers = body?.optJSONArray("operation_ids")
                    if (identifiers != null && identifiers.length() > 0) {
                        require((0 until identifiers.length()).all { identifiers.getString(it) == "synthetic-operation" })
                        val bound = plan.getJSONArray("bound_operations")
                        if ((0 until bound.length()).none { bound.getJSONObject(it).getString("id") == "synthetic-operation" }) {
                            bound.put(syntheticOperation("synthetic-operation", "3"))
                            plan.put("executed_quantity", plan.getString("executed_quantity").toBigDecimal().add(BigDecimal("3")).toPlainString())
                        }
                        plan.put("state", "partial")
                    }
                    enqueue(body)
                }
                method == "GET" && endpoint == "/workspace/notifications/events" -> ok(jObject("items" to JSONArray(notifications)))
                method == "POST" && endpoint.startsWith("/workspace/notifications/") && endpoint.endsWith("/ack") -> {
                    require(body?.optString("state") == "read")
                    val event = notifications.single { it.getString("id") == endpoint.removeSuffix("/ack").substringAfterLast('/') }
                    event.put("state", "read"); ok(event)
                }
                method == "GET" && endpoint == "/workspace/chat/threads" -> ok(jObject("items" to if (!hasThread) JSONArray() else jArray(
                    jObject("thread_id" to PROBE_THREAD, "title" to "Синтетический диалог", "updated_at" to PROBE_AS_OF))))
                method == "POST" && endpoint == "/workspace/chat/threads" -> { hasThread = true; ok(jObject("thread_id" to PROBE_THREAD)) }
                method == "GET" && endpoint == "/workspace/chat/threads/$PROBE_THREAD/messages" -> ok(jObject("items" to JSONArray(messages), "has_more" to false))
                method == "POST" && endpoint == "/workspace/chat/estimate" -> {
                    require(body?.getString("text")?.isNotBlank() == true)
                    ok(jObject("available" to true, "estimated_upper_bound" to probeMoney("0.01"), "synthetic" to true))
                }
                method == "POST" && endpoint == "/workspace/chat/threads/$PROBE_THREAD/messages" -> {
                    require(body?.getString("text")?.isNotBlank() == true && body.getJSONObject("context").getString("mode") in setOf("general", "portfolio", "instrument"))
                    messages.add(jObject("id" to "synthetic-user-${++sequence}", "role" to "user", "text" to body.getString("text"), "created_at" to PROBE_AS_OF))
                    messages.add(assistantMessage("synthetic-answer-$sequence")); enqueue(body)
                }
                method == "GET" && endpoint.startsWith("/workspace/jobs/by-request/") -> {
                    val id = requestJobs[endpoint.substringAfterLast('/')] ?: return VolumeReply(status = 404, error = "Тестовое задание не найдено.")
                    ok(jObject("job_id" to id))
                }
                method == "GET" && endpoint.startsWith("/workspace/jobs/") -> {
                    val id = endpoint.substringAfterLast('/'); val value = jobs[id] ?: return invalid("Unknown fixture job")
                    val polls = (jobPolls[id] ?: 0) + 1; jobPolls[id] = polls
                    if (value.optString("state") == "running" && polls >= 3) value.put("state", "completed").put("stage", "completed")
                    ok(value)
                }
                method == "POST" && endpoint.endsWith("/cancel") -> {
                    val id = endpoint.removeSuffix("/cancel").substringAfterLast('/'); val value = jobs.getValue(id)
                    value.put("state", "cancelled").put("stage", "cancelled"); ok(value)
                }
                else -> invalid("Unhandled fixture route: $method $endpoint")
            }
        } catch (failure: Exception) { invalid("Fixture contract rejected $method $endpoint: ${failure.javaClass.simpleName}") }
    }

    private fun ok(data: JSONObject) = VolumeReply(data = JSONObject(data.toString()), status = 200)
    private fun conflict(message: String) = VolumeReply(error = message, code = "synthetic_conflict", status = 409)
    private fun invalid(message: String): VolumeReply {
        trace.value = trace.value.copy(errors = (trace.value.errors + message).takeLast(10))
        return VolumeReply(error = message, code = "fixture_contract_error", status = 422)
    }
    private fun enqueue(body: JSONObject?): VolumeReply {
        val request = body?.optString("request_id")?.takeIf(String::isNotBlank) ?: return invalid("Missing request_id")
        requestJobs[request]?.let { return ok(jObject("job_id" to it)) }
        val id = "synthetic-job-${++sequence}"; requestJobs[request] = id; jobs[id] = job("running", id)
        return ok(jObject("job_id" to id))
    }
    private fun job(state: String, id: String = PROBE_JOB) = jObject("id" to id, "state" to state, "stage" to if (state == "uncertain") "provider_request" else "collecting",
        "updated_at" to PROBE_AS_OF, "can_retry" to false, "sources" to jArray(probeSource()))
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
        return jObject("as_of" to PROBE_AS_OF, "snapshot_id" to "synthetic-snapshot", "strategy_version" to version,
            "coverage" to jArray(coverage("issuer", if (partial) 1 else 2, 1, if (partial) listOf(PROBE_BOND) else emptyList()),
                coverage("ratings", if (partial) 0 else 1, 2, if (partial) listOf(PROBE_BOND) else emptyList()),
                coverage("trading", if (partial) 1 else 2, 1, if (partial) listOf(PROBE_BOND) else emptyList()),
                coverage("liquidity", if (partial) 1 else 2, 1, if (partial) listOf(PROBE_BOND) else emptyList()),
                coverage("position", 3, 0), coverage("currency", 3, 0)),
            "concentrations" to jArray(jObject("direction" to "issuer", "id" to "synthetic-issuer", "label" to "Синтетическая компания",
                "value" to if (partial) null else probeMoney("70000"),
                "share_percent" to if (partial) null else "70", "limit_percent" to "60", "breached" to if (partial) null else true,
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
        val values = linkedMapOf(PROBE_STOCK to BigDecimal("70000"), PROBE_BOND to BigDecimal("20000"), "synthetic-cash" to BigDecimal("10000"))
        val selected = when (axis) {
            "all" -> values
            "currency" -> { require(id == "RUB"); values }
            "instrument" -> { require(id in values); values.filterKeys { it == id } }
            "country" -> { require(id == "RU"); values.filterKeys { it != "synthetic-cash" } }
            "sector" -> { require(id == "Синтетический сектор"); values.filterKeys { it == PROBE_STOCK } }
            else -> error("Unknown synthetic scenario axis")
        }
        val change = selected.values.fold(BigDecimal.ZERO, BigDecimal::add).multiply(percent).divide(BigDecimal(100))
        val unknown = if (scenario == "partial" && axis == "sector") listOf(PROBE_BOND) else emptyList()
        return jObject("snapshot_id" to "synthetic-snapshot", "as_of" to PROBE_AS_OF, "baseline" to probeMoney("100000"),
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
        "candidate_operations" to if (scenario == "partial") jArray(syntheticOperation("synthetic-bound", "2"), syntheticOperation("synthetic-operation", "3")) else JSONArray(),
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
        "actions" to jArray(jObject("type" to "open_risks", "id" to "synthetic-issuer", "label" to "Открыть тестовую концентрацию")))
}
