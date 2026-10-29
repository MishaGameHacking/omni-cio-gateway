package ru.omnicio.app.preview

import android.content.res.Configuration
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import ru.omnicio.app.ui.StrategyNavigationRail
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.android.tools.screenshot.PreviewTest
import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.data.backend.AnalystUser
import ru.omnicio.app.data.portfolio.PortfolioCurrency
import ru.omnicio.app.data.portfolio.PortfolioUiState
import ru.omnicio.app.data.workspace.VolumeReply
import ru.omnicio.app.data.workspace.WorkspaceTransport
import ru.omnicio.app.ui.LocalOpenNavigationMenu
import ru.omnicio.app.ui.AnalystBottomBar
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.auth.OwnerAccessScreen
import ru.omnicio.app.ui.auth.LocalOwnerAccessPreviewStatus
import ru.omnicio.app.ui.auth.LocalOwnerAccessPreviewCooldownSeconds
import ru.omnicio.app.data.backend.OwnerAccessStatus
import ru.omnicio.app.ui.home.SystemTelemetryCard
import ru.omnicio.app.ui.home.HomeScreen
import ru.omnicio.app.ui.profile.ProfileScreen
import ru.omnicio.app.ui.theme.AnalystTheme
import ru.omnicio.app.ui.workspace.*

/**
 * Real production Compose layouts rendered by Layoutlib on the owner laptop.
 * Explicit synthetic state, no authentication, networking, device runtime, or
 * interaction evidence. These images cannot satisfy an Android release gate.
 */
@PreviewTest
@Preview(name = "home-disconnected-dark", widthDp = 390, heightDp = 844, locale = "ru",
    uiMode = Configuration.UI_MODE_NIGHT_YES)
@Preview(name = "home-disconnected-light", widthDp = 390, heightDp = 844, locale = "ru",
    uiMode = Configuration.UI_MODE_NIGHT_NO)
@Composable
fun HomeDisconnectedAppearance() = HostAppearance("home", "not_connected")

@PreviewTest
@Preview(name = "home-results-dark", widthDp = 390, heightDp = 844, locale = "ru",
    uiMode = Configuration.UI_MODE_NIGHT_YES)
@Preview(name = "home-narrow-large-text", widthDp = 320, heightDp = 760, fontScale = 1.5f,
    locale = "ru", uiMode = Configuration.UI_MODE_NIGHT_YES)
@Composable
fun HomeReadyAppearance() = HostAppearance("home", "current")

@PreviewTest
@Preview(name = "home-connection-error-light", widthDp = 390, heightDp = 844, locale = "ru",
    uiMode = Configuration.UI_MODE_NIGHT_NO)
@Composable
fun HomeErrorAppearance() = HostAppearance("home", "error")

@PreviewTest
@Preview(name = "settings-dark", widthDp = 390, heightDp = 844, locale = "ru",
    uiMode = Configuration.UI_MODE_NIGHT_YES)
@Preview(name = "settings-light", widthDp = 390, heightDp = 844, locale = "ru",
    uiMode = Configuration.UI_MODE_NIGHT_NO)
@Preview(name = "settings-narrow-large-text", widthDp = 320, heightDp = 760, fontScale = 1.5f,
    locale = "ru", uiMode = Configuration.UI_MODE_NIGHT_NO)
@Preview(name = "settings-tall-content-sheet", widthDp = 390, heightDp = 2600, locale = "ru",
    uiMode = Configuration.UI_MODE_NIGHT_YES)
@Composable
fun SettingsAppearance() = HostAppearance("settings", "current")

@PreviewTest
@Preview(name = "decisions-dark", widthDp = 390, heightDp = 844, locale = "ru",
    uiMode = Configuration.UI_MODE_NIGHT_YES)
@Preview(name = "decisions-light", widthDp = 390, heightDp = 844, locale = "ru",
    uiMode = Configuration.UI_MODE_NIGHT_NO)
@Preview(name = "decisions-narrow-large-text", widthDp = 320, heightDp = 760, fontScale = 1.5f,
    locale = "ru", uiMode = Configuration.UI_MODE_NIGHT_YES)
@Composable
fun DecisionsAppearance() = HostAppearance("decisions", "current")

@PreviewTest
@Preview(name = "login-dark", widthDp = 390, heightDp = 844, locale = "ru",
    uiMode = Configuration.UI_MODE_NIGHT_YES)
@Preview(name = "login-narrow-large-text", widthDp = 320, heightDp = 900, fontScale = 1.5f,
    locale = "ru", uiMode = Configuration.UI_MODE_NIGHT_NO)
@Composable
fun LoginAppearance() = HostAppearance("login", "not_connected")

@PreviewTest
@Preview(name = "login-loading-light", widthDp = 390, heightDp = 844, locale = "ru",
    uiMode = Configuration.UI_MODE_NIGHT_NO)
@Composable
fun LoginLoadingAppearance() = HostAppearance("login", "loading")

@PreviewTest
@Preview(name = "login-error-dark", widthDp = 390, heightDp = 844, locale = "ru",
    uiMode = Configuration.UI_MODE_NIGHT_YES)
@Composable
fun LoginErrorAppearance() = HostAppearance("login", "error")

private val forbiddenTransport = object : WorkspaceTransport {
    override fun request(token: String, path: String, method: String, body: JSONObject?): VolumeReply =
        error("Host appearance previews have no network transport.")
}

@Composable
private fun HostAppearance(page: String, state: String) {
    check(LocalInspectionMode.current) { "This fixture is only for Layoutlib inspection." }
    val resource = remember(state) { appearanceResource(state) }
    val broker = when (state) {
        "not_connected" -> BrokerConnectionState.Missing
        "error" -> BrokerConnectionState.Unknown
        else -> BrokerConnectionState.Connected
    }
    CompositionLocalProvider(
        LocalOpenNavigationMenu provides {},
        LocalWorkspaceSession provides WorkspaceSession("", "synthetic-layout-only"),
        LocalOwnerAccessPreviewStatus provides OwnerAccessStatus(state != "setup", 10, 128),
        LocalWorkspaceSnapshot provides if (state == "current") system55Fixture() else null,
        LocalWorkspaceTransport provides forbiddenTransport,
        LocalWorkspacePreviewResources provides mapOf(
            "/automation/status" to resource, "/automation/decisions" to resource),
        LocalBrokerConnection provides broker,
        LocalWorkspacePreferences provides WorkspacePreferenceController(
            WorkspacePreferences(motion = MotionLevel.OFF, haptics = false)),
    ) {
        AnalystTheme {
            Column(Modifier.fillMaxSize()) {
                Surface(color = MaterialTheme.colorScheme.surfaceVariant) {
                    Text("ПРЕДПРОСМОТР · СИНТЕТИЧЕСКИЕ ДАННЫЕ\nНоутбук · Layoutlib · без Android runtime",
                        Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 4.dp),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Box(Modifier.weight(1f).fillMaxWidth()) {
                    val user = AnalystUser("synthetic-layout-only", "Тест интерфейса", null, null)
                    when (page) {
                        "login" -> OwnerAccessScreen(
                            loading = state == "loading",
                            errorMessage = if (state == "error") "Синтетический пример ошибки входа. Повторите попытку." else null,
                            onSessionReady = { _, _ -> }, onAccessStart = { null })

                        "home" -> HomeScreen(user, PortfolioUiState.NotConnected, PortfolioCurrency.RUB,
                            false, null, null, onCurrencyClick = {}, onOpenPortfolio = {},
                            onOpenRecommendations = {}, onOpenRisk = {}, onOpenMessages = {},
                            onOpenProfile = {}, onConnect = {})
                        "settings" -> ProfileScreen(user, tApiConfigured = broker == BrokerConnectionState.Connected,
                            screenshotsBlocked = false, onScreenshotsBlockedChange = {},
                            onPortfolioClick = {}, onOpenTApi = {}, onOpenEducation = {}, onLogout = {})
                        "decisions" -> Column(Modifier.fillMaxSize()) {
                            Box(Modifier.weight(1f)) { AutonomousDecisionsScreen {} }
                            AnalystBottomBar(AnalystTab.Actions, {}, {})
                        }
                        else -> error("Unknown host appearance route.")
                    }
                }
            }
        }
    }
}

private fun appearanceResource(state: String): WorkspaceResource {
    val connected = state != "not_connected"
    val candidate = JSONObject().put("instrument_uid", "synthetic-layout-instrument")
        .put("name", "СИНТЕТИЧЕСКИЙ ИНСТРУМЕНТ").put("ticker", "TEST")
        .put("evidence_current", true)
        .put("checks", JSONArray().put(JSONObject().put("state", "passed")
            .put("message", "Синтетический пример проверки идентификатора.")))
        .put("missing_evidence", JSONArray().put("investment_thesis_and_valuation"))
    val data = JSONObject().put("schema_version", 1).put("preference_version", 1)
        .put("enabled", true).put("scheduler_enabled", true).put("broker_connected", connected)
        .put("state", if (connected) "current" else "not_connected")
        .put("last_observation_at", if (connected) "2026-10-25T09:00:00Z" else JSONObject.NULL)
        .put("blockers", if (connected) JSONArray() else JSONArray().put(JSONObject()
            .put("code", "broker_not_connected")
            .put("message", "Синтетический пример: источник брокерских данных не подключён.")))
        .put("discovery", JSONObject().put("state", if (connected) "partial" else "waiting")
            .put("candidates", if (connected) JSONArray().put(candidate) else JSONArray())
            .put("coverage", JSONObject().put("scanned", 3).put("eligible", 2).put("reviewed", 1))
            .put("reasons", JSONArray()))
        .put("execution", JSONObject().put("mode", "read_only").put("real_orders_enabled", false))
        .put("ai", JSONObject().put("available", false))
        .put("events", JSONArray())
    val error = if (state == "error") "Синтетическая ошибка связи. Настоящая сеть не вызывалась." else null
    return WorkspaceResource(data, false, error) {}
}

@PreviewTest
@Preview(name = "profiles-compact", widthDp = 390, heightDp = 1100, locale = "ru")
@Preview(name = "profiles-large", widthDp = 320, heightDp = 1500, fontScale = 2f, locale = "ru")
@Composable
fun Profiles53() {
    val catalogue = JSONObject().put("items", JSONArray().apply {
        listOf("capital" to "Бережный старт", "coupon" to "Регулярный доход", "balanced" to "Сбалансированный портфель",
            "growth" to "Долгосрочный рост", "equity" to "Долевое участие").forEach { (id, title) ->
            put(JSONObject().put("id", id).put("title", title).put("description", "Синтетический пример профиля")
                .put("config", strategy53Fixture()))
        }
    })
    AnalystTheme {
        Surface(color = MaterialTheme.colorScheme.background) {
            Column(Modifier.fillMaxSize().padding(16.dp)) {
                Text("ПРЕДПРОСМОТР · СИНТЕТИЧЕСКИЕ ДАННЫЕ", style = MaterialTheme.typography.labelSmall)
                StrategyProfilesPanel(catalogue, JSONObject(), true, {}, {})
            }
        }
    }
}

private fun strategy53Fixture(): JSONObject = JSONObject()
    .put("horizon_months", 120)
    .put("mandate", JSONObject().put("account_id", "synthetic").put("loss_capacity_percent", "10"))
    .put("construction", JSONObject().put("version", 1).put("age", 35).put("reserve_percent", 20)
        .put("income_stability", "stable").put("loss_capacity_confirmed", true).put("reinvest", true)
        .put("key_rate_mode", "at_least_key_rate").put("enabled_classes", JSONArray(listOf("bond", "share", "etf"))))

@PreviewTest
@Preview(name = "settings53-light", widthDp = 390, heightDp = 1200, locale = "ru")
@Preview(name = "settings53-graphite", widthDp = 390, heightDp = 1800, locale = "ru", uiMode = Configuration.UI_MODE_NIGHT_YES)
@Preview(name = "settings53-large-text", widthDp = 320, heightDp = 1200, fontScale = 1.5f, locale = "ru")
@Composable
fun Settings53() {
    AnalystTheme {
        Surface(color = MaterialTheme.colorScheme.background) {
            Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)) {
                Text("ПРЕДПРОСМОТР · СИНТЕТИЧЕСКИЕ ДАННЫЕ", style = MaterialTheme.typography.labelSmall)
                StrategySimpleSettings(strategy53Fixture(), listOf(JSONObject().put("id", "synthetic").put("name", "Тестовый счёт")), true) {}
            }
        }
    }
}

@PreviewTest
@Preview(name = "plan53-light", widthDp = 390, heightDp = 1050, locale = "ru")
@Preview(name = "plan53-graphite", widthDp = 390, heightDp = 1050, locale = "ru", uiMode = Configuration.UI_MODE_NIGHT_YES)
@Composable
fun Plan53() {
    val data = JSONObject().put("actions", JSONArray().put(JSONObject().put("name", "Синтетический актив").put("ticker", "TEST")
        .put("action", "buy").put("suggested_lots", 2).put("quantity", "20")
        .put("total_cost", JSONObject().put("amount", "2000").put("currency", "RUB"))
        .put("as_of", "2026-10-29T10:00:00Z").put("expires_at", "2026-10-29T10:01:00Z")
        .put("explanation", "Синтетический пример. Просроченная цена отключает переход к покупке.")))
    CompositionLocalProvider(LocalWorkspacePreviewResources provides mapOf("/automation/strategy-plan" to WorkspaceResource(data, false, null) {})) {
        AnalystTheme { Surface(color = MaterialTheme.colorScheme.background) {
            Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)) { StrategyActionPlanPanel() }
        } }
    }
}

@PreviewTest
@Preview(name = "rail53-light", widthDp = 1000, heightDp = 900, locale = "ru")
@Preview(name = "rail53-graphite", widthDp = 1000, heightDp = 900, locale = "ru", uiMode = Configuration.UI_MODE_NIGHT_YES)
@Composable
fun Rail53() {
    AnalystTheme { Surface(color = MaterialTheme.colorScheme.background) {
        Row(Modifier.fillMaxSize()) {
            StrategyNavigationRail(AnalystTab.Actions, WorkspaceRoute.Strategies, {}, {}, initiallyExpanded = true)
            Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(24.dp)) {
                Text("Моя стратегия", style = MaterialTheme.typography.headlineMedium)
                StrategySimpleSettings(strategy53Fixture(), listOf(JSONObject().put("id", "synthetic").put("name", "Тестовый счёт")), true) {}
            }
        }
    } }
}

@PreviewTest
@Preview(name = "owner56-rail-collapsed", widthDp = 390, heightDp = 844, locale = "ru", uiMode = Configuration.UI_MODE_NIGHT_YES)
@Preview(name = "owner56-rail-collapsed-large-text", widthDp = 320, heightDp = 900, fontScale = 1.5f, locale = "ru", uiMode = Configuration.UI_MODE_NIGHT_YES)
@Composable
fun OwnerRail56() {
    AnalystTheme { Surface(color = MaterialTheme.colorScheme.background) {
        Row(Modifier.fillMaxSize()) {
            StrategyNavigationRail(AnalystTab.Actions, WorkspaceRoute.Strategies, {}, {})
            Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(16.dp)) {
                Text("ПРЕДПРОСМОТР · СИНТЕТИЧЕСКИЕ ДАННЫЕ", style = MaterialTheme.typography.labelSmall)
                Text("Моя стратегия", style = MaterialTheme.typography.headlineMedium)
                StrategySimpleSettings(strategy53Fixture(), listOf(JSONObject().put("id", "synthetic").put("name", "Тестовый счёт")), true) {}
            }
        }
    } }
}

@PreviewTest
@Preview(name = "owner56-research", widthDp = 390, heightDp = 844, locale = "ru", uiMode = Configuration.UI_MODE_NIGHT_YES)
@Preview(name = "owner56-research-large-text", widthDp = 320, heightDp = 1000, fontScale = 1.5f, locale = "ru", uiMode = Configuration.UI_MODE_NIGHT_YES)
@Composable
fun OwnerResearch56() {
    check(LocalInspectionMode.current)
    val status = JSONObject().put("documents", 2).put("due_targets", 1).put("in_progress", 0).put("sources", JSONArray())
    val documents = JSONObject().put("items", JSONArray().put(JSONObject().put("id", 1).put("kind", "report")
        .put("title", "Тестовая компания · финансовые результаты").put("publisher", "Синтетический источник")
        .put("published_at", 1793232000).put("last_seen", 1793318400)))
    CompositionLocalProvider(LocalWorkspaceSession provides WorkspaceSession("", "synthetic-layout-only"),
        LocalWorkspaceTransport provides forbiddenTransport,
        LocalWorkspacePreviewResources provides mapOf(
            "/workspace/osint/status" to WorkspaceResource(status, false, null) {},
            "/workspace/osint/documents?limit=25&q=" to WorkspaceResource(documents, false, null) {})) {
        AnalystTheme { Surface(color = MaterialTheme.colorScheme.background) {
            Column(Modifier.fillMaxSize()) {
                Text("ПРЕДПРОСМОТР · СИНТЕТИЧЕСКИЕ ДАННЫЕ", Modifier.padding(8.dp), style = MaterialTheme.typography.labelSmall)
                ServerResearchScreen({}, {})
            }
        } }
    }
}


@PreviewTest
@Preview(name = "analytics54-dark", widthDp = 390, heightDp = 1800, locale = "ru", uiMode = Configuration.UI_MODE_NIGHT_YES)
@Preview(name = "analytics54-light", widthDp = 390, heightDp = 1800, locale = "ru", uiMode = Configuration.UI_MODE_NIGHT_NO)
@Preview(name = "analytics54-large-text", widthDp = 320, heightDp = 1500, fontScale = 1.5f, locale = "ru", uiMode = Configuration.UI_MODE_NIGHT_YES)
@Composable
fun Analytics54Overview() = Analytics54Fixture("overview")

@PreviewTest
@Preview(name = "analytics54-value", widthDp = 390, heightDp = 1400, locale = "ru", uiMode = Configuration.UI_MODE_NIGHT_YES)
@Composable
fun Analytics54Value() = Analytics54Fixture("value")

@PreviewTest
@Preview(name = "analytics54-structure", widthDp = 390, heightDp = 1100, locale = "ru", uiMode = Configuration.UI_MODE_NIGHT_YES)
@Composable
fun Analytics54Structure() = Analytics54Fixture("structure")

/** Pure production rendering: no API requests, account access or trade execution. */
@Composable
private fun Analytics54Fixture(page: String) {
    check(LocalInspectionMode.current)
    fun money(amount: Long) = ru.omnicio.app.data.portfolio.MoneyAmount(ru.omnicio.app.data.portfolio.ApiDecimal(amount, 0), "RUB")
    val total = money(12000)
    val positions = listOf(
        ru.omnicio.app.data.portfolio.PortfolioPosition("synthetic-share", "Тестовая акция", "TEST", null, money(6000), null, instrumentType = "share", company = "Тестовая компания", sector = "Технологии"),
        ru.omnicio.app.data.portfolio.PortfolioPosition("synthetic-bond", "Тестовая облигация", "TESTB", null, money(4800), null, instrumentType = "bond", company = "Тестовый эмитент", sector = "Промышленность"),
        ru.omnicio.app.data.portfolio.PortfolioPosition("synthetic-cash", "Деньги", "RUB", null, money(1200), null, instrumentType = "cash"),
    )
    val account = ru.omnicio.app.data.portfolio.PortfolioAccount("synthetic-layout", "Тестовый счёт", total, null, positions,
        allocations = listOf("Акции" to 50L, "Облигации" to 40L, "Деньги" to 10L).map { (name, share) ->
            ru.omnicio.app.data.portfolio.PortfolioAllocation(name, ru.omnicio.app.data.portfolio.ApiDecimal(share, 0)) })
    val analytics = JSONObject().put("currency", "RUB").put("complete", true)
        .put("history", JSONArray().apply { listOf(8000, 10000, 9500, 12000).forEachIndexed { i, value ->
            put(JSONObject().put("date", "2026-10-${25+i}T12:00:00Z").put("value", value.toString())) } })
        .put("summary", JSONArray().put(JSONObject().put("category", "coupons")
            .put("amount", JSONObject().put("value", JSONObject().put("units", "120").put("nano", 0)).put("currency", "RUB"))))
    val payments = JSONObject().put("complete", true).put("items", JSONArray())
    val data = ru.omnicio.app.ui.portfolio.AnalyticsViewData(listOf(account),
        listOf(ru.omnicio.app.ui.portfolio.AccountData(analytics, null, false)),
        listOf(ru.omnicio.app.ui.portfolio.AccountData(payments, null, false)),
        total, "RUB", ru.omnicio.app.ui.portfolio.PortfolioPeriod(null, null), "2026-10-29T12:00:00Z")
    CompositionLocalProvider(LocalWorkspacePreferences provides WorkspacePreferenceController(WorkspacePreferences(motion = MotionLevel.OFF))) {
        AnalystTheme {
            Surface(color = MaterialTheme.colorScheme.background) {
                Column(Modifier.fillMaxSize()) {
                    Text("ПРЕДПРОСМОТР · СИНТЕТИЧЕСКИЕ ДАННЫЕ", Modifier.padding(8.dp), style = MaterialTheme.typography.labelSmall)
                    ru.omnicio.app.ui.portfolio.AnalyticsHeader(page, listOf(account), true, {}, {})
                    ru.omnicio.app.ui.portfolio.AnalyticsPages(page, data, false, null, null, {}, 0, {}, {}, {}, {}, null, null) { _, _ -> }
                }
            }
        }
    }
}



@PreviewTest
@Preview(name = "owner55-setup", widthDp = 390, heightDp = 1050, locale = "ru")
@Preview(name = "owner55-setup-large-text", widthDp = 320, heightDp = 1400, fontScale = 1.5f, locale = "ru")
@Composable
fun OwnerSetup55() = HostAppearance("login", "setup")

@PreviewTest
@Preview(name = "system55-home-tall", widthDp = 390, heightDp = 2300, locale = "ru")
@Composable
fun SystemHome55() = HostAppearance("home", "current")

@PreviewTest
@Preview(name = "system55-telemetry", widthDp = 390, heightDp = 1000, locale = "ru")
@Preview(name = "system55-telemetry-large-text", widthDp = 320, heightDp = 1500, fontScale = 1.5f, locale = "ru")
@Composable
fun SystemTelemetry55() {
    check(LocalInspectionMode.current)
    CompositionLocalProvider(LocalWorkspacePreferences provides WorkspacePreferenceController(
        WorkspacePreferences(motion = MotionLevel.OFF, haptics = false))) {
        AnalystTheme {
            Surface(color = MaterialTheme.colorScheme.background) {
                Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp)) {
                    Text("ПРЕДПРОСМОТР · СИНТЕТИЧЕСКИЕ ДАННЫЕ", style = MaterialTheme.typography.labelSmall)
                    SystemTelemetryCard(system55Fixture().getJSONObject("sections").getJSONObject("ai").getJSONObject("data"),
                        java.time.Instant.parse("2026-10-29T12:00:30Z")) { }
                }
            }
        }
    }
}

/** Synthetic, screenshot-only counters; this function never ships in the production source set. */
private fun system55Fixture(): JSONObject {
    val ai = JSONObject().put("jobs", JSONArray().put(JSONObject().put("job_id", "synthetic-job")
        .put("state", "running").put("stage", "collecting_metadata").put("updated_at", "2026-10-29T12:00:00Z")
        .put("progress", JSONObject().put("completed", 17).put("total", 40))))
        .put("check_history", JSONArray().apply {
            listOf(23, 18, 15, 22, 9, 12).forEachIndexed { index, count ->
                put(JSONObject().put("observation_count", count).put("checked_at", "2026-10-29T${(12-index).toString().padStart(2, '0')}:00:00Z"))
            }
        })
        .put("budget", JSONObject().put("estimated_and_reserved_rub", "12.50").put("daily_cap_rub", "80")
            .put("monthly_estimated_and_reserved_rub", "240.50").put("monthly_cap_rub", "2500")
            .put("budget_configuration_valid", true).put("paid_calls_paused", false))
    return JSONObject().put("sections", JSONObject().put("ai", JSONObject().put("data", ai)))
}

@PreviewTest
@Preview(name = "owner56-cooldown", widthDp = 390, heightDp = 1150, locale = "ru")
@Preview(name = "owner56-cooldown-large-text", widthDp = 320, heightDp = 1600, fontScale = 1.5f, locale = "ru")
@Composable
fun OwnerCooldown56() {
    CompositionLocalProvider(LocalOwnerAccessPreviewCooldownSeconds provides 125) {
        HostAppearance("login", "setup")
    }
}

