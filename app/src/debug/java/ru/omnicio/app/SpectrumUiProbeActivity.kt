package ru.omnicio.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.analysis.AnalysisEvidence
import ru.omnicio.app.data.analysis.AnalysisIdea
import ru.omnicio.app.data.analysis.InsightCard
import ru.omnicio.app.data.backend.AnalystUser
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.data.updates.ReleaseDecision
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.LocalAnalystTabNavigator
import ru.omnicio.app.ui.analysis.*
import ru.omnicio.app.ui.auth.TelegramLoginScreen
import ru.omnicio.app.ui.education.EducationScreen
import ru.omnicio.app.ui.home.HomeScreen
import ru.omnicio.app.ui.home.MarketScreen
import ru.omnicio.app.ui.home.RisksScreen
import ru.omnicio.app.ui.portfolio.HistoryChart
import ru.omnicio.app.ui.portfolio.HistoryPoint
import ru.omnicio.app.ui.portfolio.PortfolioScreen
import ru.omnicio.app.ui.profile.ProfileScreen
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.theme.AnalystTheme
import ru.omnicio.app.ui.theme.ThemeMode
import ru.omnicio.app.ui.updates.UpdateGateActions
import ru.omnicio.app.ui.updates.UpdateGateUi
import java.math.BigDecimal
import java.time.Instant

/** Offline, watermarked fixtures. This activity and ALL its data are excluded from preview/release. */
class SpectrumUiProbeActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        runSpectrumContrastChecks()
        runSpectrumLineChecks()
        val requested = intent.getStringExtra("screen") ?: "Home"
        val theme = intent.getStringExtra("theme") ?: ThemeMode.DARK.name
        check(ThemeMode.entries.any { it.name == theme })
        check(getSharedPreferences("analyst_ai_settings", 0).edit().putString("theme_mode", theme).commit())
        setContent {
            AnalystTheme {
                check(LocalContentColor.current == MaterialTheme.colorScheme.onBackground)
                var screen by rememberSaveable { mutableStateOf(requested) }
                val navigate: (AnalystTab) -> Unit = { screen = it.name }
                BackHandler(screen != "Home") { screen = "Home" }
                CompositionLocalProvider(LocalAnalystTabNavigator provides navigate) {
                    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).statusBarsPadding().semantics {
                        contentDescription = "spectrum-screen:$screen;spectrum-contrast:passed;spectrum-line-tests:passed;synthetic-data-only"
                    }) {
                        Text("Тестовые данные · проверка интерфейса", Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp),
                            style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.error)
                        Box(Modifier.weight(1f).fillMaxWidth()) { SpectrumFixtureScreen(screen, navigate) }
                    }
                }
            }
        }
    }
}

@Composable
private fun SpectrumFixtureScreen(screen: String, navigate: (AnalystTab) -> Unit) {
    val snapshot = remember { spectrumFixtureSnapshot() }
    val state = remember(snapshot) { PortfolioUiState.Ready(snapshot) }
    val profile = { navigate(AnalystTab.Profile) }
    val portfolio = { navigate(AnalystTab.Portfolio) }
    when (screen) {
        "Portfolio" -> PortfolioScreen(state, profile)
        "Market" -> MarketScreen(state, profile)
        "Risks" -> RisksScreen(state, "", profile, {})
        "Education" -> EducationScreen({ navigate(AnalystTab.Home) }, portfolio, profile)
        "Profile" -> ProfileScreen(AnalystUser("synthetic-spectrum", "Тест Analyst AI", null, null), false, false, {}, portfolio, {}, {}, { navigate(AnalystTab.Education) }, {})
        "Login" -> TelegramLoginScreen(false, null, {})
        "Update" -> RequiredUpdateScreen(UpdateGateUi(null, ReleaseDecision.UPDATE_REQUIRED, "0.6.0-preview", false, false, 0, null, null, false), UpdateGateActions({}, {}, {}))
        "Chart" -> SpectrumChartFixture()
        "Ideas" -> SpectrumIdeasFixture(portfolio, profile)
        "Pulse", "Chat" -> SpectrumInsightFixture(screen, portfolio, profile)
        else -> HomeScreen(state, "", PortfolioCurrency.RUB, {}, profile, {})
    }
}

@Composable
private fun SpectrumChartFixture() {
    SpectrumBackground(Modifier.fillMaxSize()) {
        LazyColumn(Modifier.fillMaxSize().navigationBarsPadding(), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            item { SpectrumHeader("Динамика стоимости", "Синтетическая серия для визуального теста", SpectrumSymbol.Market) }
            item { SpectrumCard { HistoryChart(spectrumFixtureHistory(), "RUB") } }
        }
    }
}

@Composable
private fun SpectrumIdeasFixture(portfolio: () -> Unit, profile: () -> Unit) {
    AnalysisScaffold(AnalystTab.Ideas, "Рекомендации", "Тест представления проверенных направлений", portfolio, profile) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            item { ActionCard("Новые идеи для вас", "Тест состояния интерфейса, а не совет по покупке.", "Обновить", true, {}) }
            item { IdeaCard(AnalysisIdea("Облигации", 19.78, 25.0, 5.22, 10.0, "Синтетическая карточка для проверки отступов, типографики и переноса текста.")) }
        }
    }
}

@Composable
private fun SpectrumInsightFixture(screen: String, portfolio: () -> Unit, profile: () -> Unit) {
    val card = InsightCard("ui-test", "review", "warning", "Проверка структуры портфеля", "Тестовое уведомление. Оно не относится к реальному счёту пользователя.",
        listOf("Проверить отображение длинного текста и источников."),
        listOf(AnalysisEvidence("Синтетические данные интерфейсного теста.", "UI fixture", "2026-10-15T07:00:00Z")),
        listOf("Не является результатом инвестиционного анализа."), "2026-10-15T12:00:00Z", false, "2026-10-15T07:00:00Z")
    val tab = if (screen == "Chat") AnalystTab.Chat else AnalystTab.Pulse
    AnalysisScaffold(tab, if (screen == "Chat") "Сообщения" else "События", "Проверка карточек уведомлений", portfolio, profile) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(20.dp)) {
            item { InsightCardView(card, Instant.parse("2026-10-15T08:00:00Z"), true, {}) }
        }
    }
}

private fun spectrumFixtureSnapshot(): PortfolioSnapshot {
    fun rub(value: Long) = MoneyAmount(ApiDecimal(value, 0), "RUB")
    val positions = listOf(
        PortfolioPosition("test-share", "Акции · тест интерфейса", "ABC", ApiDecimal(10, 0), rub(3150), null, instrumentType = "share"),
        PortfolioPosition("test-bond", "Облигации · тест интерфейса", "BND", ApiDecimal(2, 0), rub(2010), null, instrumentType = "bond"),
        PortfolioPosition("test-cash", "Российский рубль", "RUB", ApiDecimal(5000, 0), rub(5000), null, instrumentType = "cash"),
    )
    val allocations = listOf(PortfolioAllocation("Акции", ApiDecimal(31, 0)), PortfolioAllocation("Облигации", ApiDecimal(19, 780000000)),
        PortfolioAllocation("Денежные средства", ApiDecimal(49, 220000000)))
    val account = PortfolioAccount("test-account", "Тестовый счёт", rub(10160), null, positions, allocations = allocations)
    return PortfolioSnapshot(rub(10160), null, null, listOf(account), allocations, asOf = "2026-10-15T07:00:00Z")
}
internal fun spectrumFixtureHistory(): List<HistoryPoint> = listOf("10000", "9950", "10060", "10040", "10100", "10120", "10160").mapIndexed { index, value ->
    HistoryPoint("2026-10-${(9 + index).toString().padStart(2, '0')}T07:00:00Z", BigDecimal(value))
}
