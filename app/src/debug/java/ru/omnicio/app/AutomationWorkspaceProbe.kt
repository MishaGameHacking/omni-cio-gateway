package ru.omnicio.app

import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.compose.ui.zIndex
import kotlinx.coroutines.flow.MutableStateFlow
import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.data.backend.AnalystUser
import ru.omnicio.app.data.portfolio.PortfolioCurrency
import ru.omnicio.app.data.portfolio.PortfolioUiState
import ru.omnicio.app.data.workspace.VolumeReply
import ru.omnicio.app.data.workspace.WorkspaceTransport
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.LocalAnalystTabNavigator
import ru.omnicio.app.ui.home.HomeScreen
import ru.omnicio.app.ui.profile.ProfileScreen
import ru.omnicio.app.ui.workspace.*

internal val automationProbeRoutes = setOf("home", "settings", "decisions")
internal val automationProbeScenarios = setOf("ready", "not_connected", "paused", "error", "conflict")
internal const val AUTOMATION_PROBE_ERROR = "Синтетический отказ сервера. Настоящая сеть не вызывалась."
internal const val AUTOMATION_PROBE_CONFLICT = "Синтетический конфликт версии. Настройка не изменена."

internal data class AutomationProbeTrace(val requests: Int = 0, val writes: Int = 0,
    val applied: Int = 0, val rejected: Int = 0, val contractErrors: Int = 0, val version: Int = 1, val enabled: Boolean = true)

/** No network client exists in this debug-only transport. */
internal class AutomationProbeTransport(private val scenario: String) : WorkspaceTransport {
    private var enabled = scenario != "paused"
    private var version = 1
    val trace = MutableStateFlow(AutomationProbeTrace(enabled = enabled))
    fun brokerConnected(): Boolean = scenario != "not_connected"

    @Synchronized
    override fun request(token: String, path: String, method: String, body: JSONObject?): VolumeReply {
        trace.value = trace.value.copy(requests = trace.value.requests + 1)
        if (token != "debug-automation-only") return invalid()
        if (scenario == "error") return VolumeReply(error = AUTOMATION_PROBE_ERROR, code = "synthetic_unavailable", status = 503, retryable = true)
        if (method == "GET" && path in setOf("/automation/status", "/automation/decisions"))
            return VolumeReply(data = status(), status = 200)
        if (method == "PUT" && path == "/automation/preferences") {
            trace.value = trace.value.copy(writes = trace.value.writes + 1)
            if (body == null || body.keys().asSequence().toSet() != setOf("enabled", "expected_version") ||
                body.opt("enabled") !is Boolean || body.opt("expected_version") !is Number) return invalid()
            if (scenario == "conflict" || body.optInt("expected_version") != version) {
                version++
                trace.value = trace.value.copy(rejected = trace.value.rejected + 1, version = version)
                return VolumeReply(error = AUTOMATION_PROBE_CONFLICT, code = "version_conflict", status = 409)
            }
            enabled = body.getBoolean("enabled")
            version++
            trace.value = trace.value.copy(applied = trace.value.applied + 1, version = version, enabled = enabled)
            return VolumeReply(data = JSONObject().put("enabled", enabled).put("version", version), status = 200)
        }
        return invalid()
    }

    private fun invalid(): VolumeReply {
        trace.value = trace.value.copy(contractErrors = trace.value.contractErrors + 1)
        return VolumeReply(error = "Синтетический контракт запроса нарушен.", code = "fixture_contract_error", status = 400)
    }

    private fun status(): JSONObject {
        val connected = brokerConnected()
        val observed = connected && scenario != "paused"
        val blockers = JSONArray()
        if (!connected) blockers.put(JSONObject().put("code", "broker_not_connected")
            .put("message", "Синтетическое отсутствие подключения брокера."))
        if (!enabled) blockers.put(JSONObject().put("code", "paused")
            .put("message", "Синтетическая пауза автоматического анализа."))
        val candidates = JSONArray()
        if (observed) candidates.put(JSONObject()
            .put("instrument_uid", "synthetic-automation-fund").put("ticker", "TEST")
            .put("name", "СИНТЕТИЧЕСКИЙ ФОНД").put("instrument_type", "etf")
            .put("currency", "RUB").put("lot", 1).put("evidence_current", true)
            .put("checks", JSONArray().put(JSONObject().put("code", "identity").put("state", "passed")
                .put("message", "Синтетический идентификатор проверен."))
                .put(JSONObject().put("code", "risk").put("state", "unknown")
                    .put("message", "Синтетическая проверка риска ещё не завершена.")))
            .put("missing_evidence", JSONArray().put("Синтетическое недостающее основание.")))
        val at = "2026-10-25T09:00:00Z"
        return JSONObject().put("schema_version", 1).put("enabled", enabled).put("preference_version", version)
            .put("broker_connected", connected).put("scheduler_enabled", true)
            .put("state", when { !enabled -> "paused"; !connected -> "not_connected"; else -> "current" })
            .put("blockers", blockers).put("last_observation_at", if (observed) at else JSONObject.NULL)
            .put("last_full_collection_at", if (observed) at else JSONObject.NULL).put("current_job", JSONObject.NULL)
            .put("initial_observation", if (observed) JSONObject().put("at", at)
                .put("snapshot_id", "synthetic-observation").put("summary", "Синтетическая проверка завершена.") else JSONObject.NULL)
            .put("discovery", JSONObject().put("state", if (observed) "partial" else "waiting")
                .put("as_of", if (observed) at else JSONObject.NULL).put("coverage", JSONObject()
                    .put("scanned", if (observed) 3 else 0).put("eligible", if (observed) 2 else 0).put("reviewed", candidates.length()))
                .put("candidates", candidates).put("reasons", JSONArray()))
            .put("execution", JSONObject().put("mode", "read_only").put("real_orders_enabled", false))
            .put("ai", JSONObject().put("available", false).put("reason", "fixture_has_no_model"))
            .put("events", if (observed) JSONArray().put(JSONObject().put("id", "synthetic-event")
                .put("kind", "observation").put("at", at).put("title", "СИНТЕТИЧЕСКАЯ ПРОВЕРКА")
                .put("summary", "Визуальная проверка сохранённого события, без реальной сети.")) else JSONArray())
    }
}

@Composable
internal fun AutomationProbeProvider(transport: AutomationProbeTransport, content: @Composable () -> Unit) {
    CompositionLocalProvider(
        LocalWorkspaceSession provides WorkspaceSession("debug-automation-only", "synthetic-ui-test"),
        LocalWorkspaceTransport provides transport,
        LocalBrokerConnection provides if (transport.brokerConnected()) BrokerConnectionState.Connected else BrokerConnectionState.Missing,
        content = content,
    )
}

/** Production composables with visibly synthetic, isolated transport data. */
@Composable
internal fun AutomationWorkspaceProbe(route: String, scenario: String) {
    val initial = route.removePrefix("automation-")
    require(initial in automationProbeRoutes && scenario in automationProbeScenarios)
    require(scenario != "conflict" || initial == "settings")
    val transport = remember(initial, scenario) { AutomationProbeTransport(scenario) }
    val observed by transport.trace.collectAsState()
    var page by remember(initial) { mutableStateOf(initial) }
    var navigation by remember { mutableStateOf("none") }
    var screenshotsBlocked by remember { mutableStateOf(false) }
    val marker = "automation-probe:" + initial + "/" + scenario + ";transport:synthetic;page:" + page +
        ";requests:" + observed.requests + ";writes:" + observed.writes + ";applied:" + observed.applied +
        ";rejected:" + observed.rejected + ";contract-errors:" + observed.contractErrors +
        ";version:" + observed.version + ";enabled:" + observed.enabled + ";navigation:" + navigation
    Column(Modifier.fillMaxSize().statusBarsPadding()) {
        Surface(color = MaterialTheme.colorScheme.surface) {
            Text("ВИЗУАЛЬНЫЙ ТЕСТ · НЕ РЕАЛЬНЫЕ ДАННЫЕ", Modifier.fillMaxWidth().padding(4.dp),
                style = MaterialTheme.typography.labelSmall)
        }
        Box(Modifier.weight(1f).semantics { contentDescription = marker }) {
            AutomationProbeProvider(transport) {
                CompositionLocalProvider(
                    LocalAnalystTabNavigator provides { page = when (it) {
                        AnalystTab.Home -> "home"; AnalystTab.Actions -> "decisions"; else -> "settings"
                    } },
                    LocalWorkspaceNavigator provides { navigation = it.name },
                ) {
                    when (page) {
                        "home" -> HomeScreen(AnalystUser("synthetic-ui-test", "Тест интерфейса", null, null),
                            PortfolioUiState.NotConnected, PortfolioCurrency.RUB, false, null, null,
                            onCurrencyClick = {}, onOpenPortfolio = { navigation = "portfolio" },
                            onOpenRecommendations = { page = "decisions" }, onOpenRisk = { navigation = "risk" },
                            onOpenMessages = { navigation = "messages" }, onOpenProfile = { page = "settings" },
                            onConnect = { navigation = "connection" })
                        "decisions" -> Column(Modifier.fillMaxSize()) {
                            Box(Modifier.weight(1f)) { AutonomousDecisionsScreen { page = "home" } }
                            ru.omnicio.app.ui.AnalystBottomBar(AnalystTab.Actions, {}, { page = "settings" })
                        }
                        else -> ProfileScreen(AnalystUser("synthetic-ui-test", "Тест интерфейса", null, null),
                            tApiConfigured = transport.brokerConnected(), screenshotsBlocked = screenshotsBlocked,
                            onScreenshotsBlockedChange = { screenshotsBlocked = it },
                            onPortfolioClick = { navigation = "portfolio" }, onOpenTApi = { navigation = "connection" },
                            onOpenEducation = { navigation = "education" }, onLogout = { navigation = "logout" })
                    }
                }
            }
            Box(Modifier.align(Alignment.TopStart).size(2.dp).zIndex(100f)
                .clearAndSetSemantics { contentDescription = marker })
        }
    }
}
