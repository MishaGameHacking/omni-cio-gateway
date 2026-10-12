from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    content = read(path)
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor, found {count}: {old[:100]!r}")
    write(path, content.replace(old, new, 1))


def append_once(path: str, marker: str, block: str) -> None:
    content = read(path)
    if marker in content:
        return
    write(path, content.rstrip() + "\n\n" + block.strip() + "\n")


# Register the new read-only portfolio router without disturbing existing auth/token code.
append_once(
    "backend/app.py",
    "tinvest_portfolio_router",
    """
try:
    from .tinvest_portfolio import router as tinvest_portfolio_router
except ImportError:
    from tinvest_portfolio import router as tinvest_portfolio_router

app.include_router(tinvest_portfolio_router)
""",
)

# Bump the Android version for the feature release.
replace_once(
    "app/build.gradle.kts",
    '        versionCode = 16\n        versionName = "0.2.3"',
    '        versionCode = 17\n        versionName = "0.3.0"',
)

# Portfolio UI: shared models, server-selected currency, and tap-to-cycle.
portfolio_path = "app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioScreen.kt"
portfolio = read(portfolio_path)
portfolio = portfolio.replace(
    "import androidx.compose.foundation.background\n",
    "import androidx.compose.foundation.background\nimport androidx.compose.foundation.clickable\n",
    1,
)
model_start = portfolio.index("data class ApiDecimal(")
model_end = portfolio.index("private val ScreenBackground")
portfolio = portfolio[:model_start] + portfolio[model_end:]
portfolio = portfolio.replace(
    "import java.util.Locale\nimport ru.omnicio.app.ui.AnalystBottomBar",
    """import java.util.Locale
import ru.omnicio.app.data.portfolio.ApiDecimal
import ru.omnicio.app.data.portfolio.MoneyAmount
import ru.omnicio.app.data.portfolio.PortfolioAccount
import ru.omnicio.app.data.portfolio.PortfolioAllocation
import ru.omnicio.app.data.portfolio.PortfolioCurrency
import ru.omnicio.app.data.portfolio.PortfolioPosition
import ru.omnicio.app.data.portfolio.PortfolioSnapshot
import ru.omnicio.app.data.portfolio.PortfolioUiState
import ru.omnicio.app.ui.AnalystBottomBar""",
    1,
)
old_signature = """fun PortfolioScreen(
    state: PortfolioUiState,
    onProfileClick: () -> Unit,
    modifier: Modifier = Modifier,
) {"""
new_signature = """fun PortfolioScreen(
    state: PortfolioUiState,
    onProfileClick: () -> Unit,
    selectedCurrency: PortfolioCurrency = PortfolioCurrency.RUB,
    onCurrencyClick: () -> Unit = {},
    modifier: Modifier = Modifier,
) {"""
if portfolio.count(old_signature) != 1:
    raise RuntimeError("PortfolioScreen signature anchor changed")
portfolio = portfolio.replace(old_signature, new_signature, 1)
portfolio = portfolio.replace(
    "PortfolioSummaryCard(snapshot = state.snapshot)",
    """PortfolioSummaryCard(
                            snapshot = state.snapshot,
                            selectedCurrency = selectedCurrency,
                            onCurrencyClick = onCurrencyClick,
                        )""",
    1,
)
portfolio = portfolio.replace(
    "@Composable\nprivate fun PortfolioSummaryCard(snapshot: PortfolioSnapshot) {",
    """@Composable
private fun PortfolioSummaryCard(
    snapshot: PortfolioSnapshot,
    selectedCurrency: PortfolioCurrency,
    onCurrencyClick: () -> Unit,
) {""",
    1,
)
old_amount = """            Text(
                text = snapshot.totalValue.formatted(),
                fontSize = 36.sp,
                lineHeight = 42.sp,
                fontWeight = FontWeight.Bold,
            )

            YieldRow("""
new_amount = """            Text(
                text = snapshot.totalValue.formatted(),
                modifier = Modifier.clickable(onClick = onCurrencyClick),
                fontSize = 36.sp,
                lineHeight = 42.sp,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = "Нажмите на сумму: ${selectedCurrency.name} → ${selectedCurrency.next().name}",
                style = MaterialTheme.typography.bodySmall,
                color = MutedText,
            )

            YieldRow("""
if portfolio.count(old_amount) != 1:
    raise RuntimeError("Portfolio amount anchor changed")
portfolio = portfolio.replace(old_amount, new_amount, 1)
write(portfolio_path, portfolio)

# Android backend client: fetch and parse the real portfolio payload.
client_path = "app/src/main/java/ru/omnicio/app/data/backend/AnalystBackendClient.kt"
replace_once(
    client_path,
    "import org.json.JSONObject\n",
    """import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.data.portfolio.ApiDecimal
import ru.omnicio.app.data.portfolio.MoneyAmount
import ru.omnicio.app.data.portfolio.PortfolioAccount
import ru.omnicio.app.data.portfolio.PortfolioAllocation
import ru.omnicio.app.data.portfolio.PortfolioCurrency
import ru.omnicio.app.data.portfolio.PortfolioPosition
import ru.omnicio.app.data.portfolio.PortfolioSnapshot
""",
)
replace_once(
    client_path,
    """    fun saveTInvestToken(
        accessToken: String,
        token: String,
    ): BackendResult<Boolean> {""",
    """    fun fetchPortfolio(
        accessToken: String,
        currency: PortfolioCurrency,
    ): BackendResult<PortfolioSnapshot> {
        val response = request(
            method = "GET",
            path = "/tinvest/portfolio?currency=${currency.name}",
            bearer = accessToken,
        )
        return when (response) {
            is BackendResult.Success -> runCatching {
                parsePortfolio(JSONObject(response.value))
            }.fold(
                onSuccess = { BackendResult.Success(it) },
                onFailure = {
                    BackendResult.Failure(
                        "T-Invest вернул некорректные данные портфеля.",
                        retryable = true,
                    )
                },
            )
            is BackendResult.Failure -> response
        }
    }

    fun saveTInvestToken(
        accessToken: String,
        token: String,
    ): BackendResult<Boolean> {""",
)
replace_once(
    client_path,
    '                path == "/tinvest/token" -> tinvestFailure(detail, status)',
    '                path.startsWith("/tinvest/") -> tinvestFailure(detail, status)',
)
replace_once(
    client_path,
    """            "empty_tinvest_token" ->
                "Вставьте токен доступа T-Invest."
            else -> when (status) {""",
    """            "empty_tinvest_token" ->
                "Вставьте токен доступа T-Invest."
            "tinvest_not_connected" ->
                "Подключите T-API в профиле, чтобы загрузить портфель."
            "unsupported_portfolio_currency" ->
                "Эта валюта отображения не поддерживается."
            "tinvest_token_unreadable" ->
                "Сохранённый токен T-Invest повреждён. Подключите T-API заново."
            else -> when (status) {""",
)
replace_once(
    client_path,
    """    private fun parseSession(json: JSONObject): AnalystSession {""",
    """    private fun parsePortfolio(json: JSONObject): PortfolioSnapshot {
        val accountsJson = json.optJSONArray("accounts") ?: JSONArray()
        val accounts = buildList {
            for (index in 0 until accountsJson.length()) {
                val account = accountsJson.getJSONObject(index)
                val positionsJson = account.optJSONArray("positions") ?: JSONArray()
                val positions = buildList {
                    for (positionIndex in 0 until positionsJson.length()) {
                        val position = positionsJson.getJSONObject(positionIndex)
                        add(
                            PortfolioPosition(
                                id = position.getString("id"),
                                title = position.getString("title"),
                                ticker = position.optNullableString("ticker"),
                                quantity = position.optNullableObject("quantity")?.let(::parseDecimal),
                                currentValue = position.optNullableObject("currentValue")?.let(::parseMoney),
                                expectedYieldPercent = position
                                    .optNullableObject("expectedYieldPercent")
                                    ?.let(::parseDecimal),
                            ),
                        )
                    }
                }
                add(
                    PortfolioAccount(
                        id = account.getString("id"),
                        name = account.getString("name"),
                        totalValue = parseMoney(account.getJSONObject("totalValue")),
                        expectedYieldPercent = account
                            .optNullableObject("expectedYieldPercent")
                            ?.let(::parseDecimal),
                        positions = positions,
                    ),
                )
            }
        }

        val allocationsJson = json.optJSONArray("allocations") ?: JSONArray()
        val allocations = buildList {
            for (index in 0 until allocationsJson.length()) {
                val allocation = allocationsJson.getJSONObject(index)
                add(
                    PortfolioAllocation(
                        title = allocation.getString("title"),
                        sharePercent = parseDecimal(allocation.getJSONObject("sharePercent")),
                    ),
                )
            }
        }

        return PortfolioSnapshot(
            totalValue = parseMoney(json.getJSONObject("totalValue")),
            expectedYieldAmount = json.optNullableObject("expectedYieldAmount")?.let(::parseMoney),
            expectedYieldPercent = json
                .optNullableObject("expectedYieldPercent")
                ?.let(::parseDecimal),
            accounts = accounts,
            allocations = allocations,
        )
    }

    private fun parseMoney(json: JSONObject): MoneyAmount = MoneyAmount(
        value = parseDecimal(json.getJSONObject("value")),
        currency = json.getString("currency"),
    )

    private fun parseDecimal(json: JSONObject): ApiDecimal = ApiDecimal(
        units = json.get("units").toString().toLong(),
        nano = json.optInt("nano"),
    )

    private fun JSONObject.optNullableObject(key: String): JSONObject? {
        if (!has(key) || isNull(key)) {
            return null
        }
        return getJSONObject(key)
    }

    private fun parseSession(json: JSONObject): AnalystSession {""",
)

# Main application: load portfolio, persist currency selection and route five tabs.
main_path = "app/src/main/java/ru/omnicio/app/MainActivity.kt"
replace_once(
    main_path,
    "import androidx.compose.runtime.Composable\n",
    "import androidx.compose.runtime.Composable\nimport androidx.compose.runtime.CompositionLocalProvider\n",
)
replace_once(
    main_path,
    """import ru.omnicio.app.data.settings.AppSettingsStore
import ru.omnicio.app.data.tinvest.TInvestTokenStore
import ru.omnicio.app.ui.auth.TelegramLoginScreen
import ru.omnicio.app.ui.portfolio.PortfolioScreen
import ru.omnicio.app.ui.portfolio.PortfolioUiState
import ru.omnicio.app.ui.profile.ProfileScreen""",
    """import ru.omnicio.app.data.portfolio.PortfolioCurrency
import ru.omnicio.app.data.portfolio.PortfolioUiState
import ru.omnicio.app.data.settings.AppSettingsStore
import ru.omnicio.app.data.tinvest.TInvestTokenStore
import ru.omnicio.app.ui.AnalystTab
import ru.omnicio.app.ui.LocalAnalystTabNavigator
import ru.omnicio.app.ui.PlaceholderTabScreen
import ru.omnicio.app.ui.auth.TelegramLoginScreen
import ru.omnicio.app.ui.portfolio.PortfolioScreen
import ru.omnicio.app.ui.profile.ProfileScreen""",
)
replace_once(
    main_path,
    """private enum class AppScreen {
    Portfolio,
    Profile,
    TApi,
}""",
    """private enum class AppScreen {
    Portfolio,
    Ideas,
    Pulse,
    Chat,
    Profile,
    TApi,
}""",
)
replace_once(
    main_path,
    """    var tApiConfigured by remember { mutableStateOf(false) }
    var screenshotsBlocked by rememberSaveable {
        mutableStateOf(initialScreenshotsBlocked)
    }""",
    """    var tApiConfigured by remember { mutableStateOf(false) }
    var portfolioState by remember { mutableStateOf<PortfolioUiState>(PortfolioUiState.NotConnected) }
    var portfolioCurrencyName by rememberSaveable {
        mutableStateOf(PortfolioCurrency.RUB.name)
    }
    val portfolioCurrency = remember(portfolioCurrencyName) {
        runCatching { PortfolioCurrency.valueOf(portfolioCurrencyName) }
            .getOrDefault(PortfolioCurrency.RUB)
    }
    var screenshotsBlocked by rememberSaveable {
        mutableStateOf(initialScreenshotsBlocked)
    }""",
)
status_anchor = """        tApiConfigured = connected
    }

    MaterialTheme {"""
status_replacement = """        tApiConfigured = connected
    }

    LaunchedEffect(signedIn?.accessToken, tApiConfigured, portfolioCurrency) {
        val session = signedIn
        if (session == null || !tApiConfigured) {
            portfolioState = PortfolioUiState.NotConnected
            return@LaunchedEffect
        }

        portfolioState = PortfolioUiState.Loading
        portfolioState = when (val result = withContext(Dispatchers.IO) {
            backend.fetchPortfolio(
                accessToken = session.accessToken,
                currency = portfolioCurrency,
            )
        }) {
            is BackendResult.Success -> PortfolioUiState.Ready(result.value)
            is BackendResult.Failure -> PortfolioUiState.Error(result.message)
        }
    }

    MaterialTheme {"""
replace_once(main_path, status_anchor, status_replacement)
main = read(main_path)
start = main.index("            is AuthUiState.SignedIn -> {")
end = main.index("\n            }\n        }\n    }\n}\n\n@Preview", start) + len("\n            }")
new_signed_in = """            is AuthUiState.SignedIn -> {
                val navigateToTab: (AnalystTab) -> Unit = { tab ->
                    screenName = when (tab) {
                        AnalystTab.Portfolio -> AppScreen.Portfolio
                        AnalystTab.Ideas -> AppScreen.Ideas
                        AnalystTab.Pulse -> AppScreen.Pulse
                        AnalystTab.Chat -> AppScreen.Chat
                        AnalystTab.Profile -> AppScreen.Profile
                    }.name
                }

                CompositionLocalProvider(LocalAnalystTabNavigator provides navigateToTab) {
                    when (screen) {
                        AppScreen.Portfolio -> {
                            PortfolioScreen(
                                state = portfolioState,
                                selectedCurrency = portfolioCurrency,
                                onCurrencyClick = {
                                    portfolioCurrencyName = portfolioCurrency.next().name
                                },
                                onProfileClick = {
                                    screenName = AppScreen.Profile.name
                                },
                            )
                        }

                        AppScreen.Ideas -> {
                            PlaceholderTabScreen(
                                selected = AnalystTab.Ideas,
                                title = "Что купить",
                                description = "Здесь появятся персональные подборки активов после согласования правил риска, горизонта и допустимых рынков.",
                            )
                        }

                        AppScreen.Pulse -> {
                            PlaceholderTabScreen(
                                selected = AnalystTab.Pulse,
                                title = "Пульс",
                                description = "Раздел подготовлен для важных событий рынка и компаний из портфеля без лишнего информационного шума.",
                            )
                        }

                        AppScreen.Chat -> {
                            PlaceholderTabScreen(
                                selected = AnalystTab.Chat,
                                title = "Чат",
                                description = "Здесь будет лента важных сообщений Analyst AI. Пользователь не задаёт модели произвольные вопросы — система сообщает только полезные выводы.",
                            )
                        }

                        AppScreen.Profile -> {
                            ProfileScreen(
                                user = current.user,
                                tApiConfigured = tApiConfigured,
                                screenshotsBlocked = screenshotsBlocked,
                                onScreenshotsBlockedChange = { blocked ->
                                    screenshotsBlocked = blocked
                                    onScreenshotsBlockedChange(blocked)
                                },
                                onPortfolioClick = {
                                    screenName = AppScreen.Portfolio.name
                                },
                                onOpenTApi = {
                                    screenName = AppScreen.TApi.name
                                },
                                onLogout = {
                                    sessionStore.clear()
                                    screenName = AppScreen.Portfolio.name
                                    tApiConfigured = false
                                    portfolioState = PortfolioUiState.NotConnected
                                    authState = AuthUiState.SignedOut()
                                },
                            )
                        }

                        AppScreen.TApi -> {
                            TApiScreen(
                                accessToken = current.accessToken,
                                tApiConfigured = tApiConfigured,
                                onBack = {
                                    screenName = AppScreen.Profile.name
                                },
                                onConnectionChanged = { configured ->
                                    tApiConfigured = configured
                                    if (!configured) {
                                        portfolioState = PortfolioUiState.NotConnected
                                    }
                                },
                            )
                        }
                    }
                }
            }"""
main = main[:start] + new_signed_in + main[end:]
write(main_path, main)

# Persist the new product constraints for future development.
append_once(
    "AGENTS.md",
    "## AI orchestration",
    """
## AI orchestration

- Users do not directly prompt the investment AI. It emits proactive, structured insights.
- Routine data collection, calculations, caching and risk thresholds must run without LLMs.
- Use the balanced `fast` / `standard` / `premium` gate in `backend/ai_policy.py`; no material change means no model call.
- Timeweb AI Gateway model IDs and API keys are server configuration, never APK constants.
- The primary navigation has five tabs: Portfolio, Ideas, Pulse, Chat and Profile.
- Portfolio display currency cycles RUB -> USD -> EUR by tapping the total; request that currency from T-Invest rather than inventing local FX conversion.
""",
)
append_once(
    "README.md",
    "## Analyst AI 0.3.0",
    """
## Analyst AI 0.3.0

This iteration adds a five-tab Android shell, real read-only T-Invest portfolio loading, RUB/USD/EUR portfolio display selected by tapping the total, and a deterministic AI decision gate that prevents empty token-consuming analyses. The chosen autonomous-analysis architecture is documented in `docs/AI_ORCHESTRATION.md`.
""",
)

print("Analyst AI feature transformation applied successfully")
