package ru.omnicio.app.ui

private const val DEFAULT_RESERVE_MINOR = 25_000_000L
private const val DEFAULT_GOAL_HORIZON_YEARS = 3

internal data class LocalSettingsState(
    val portfolioPresent: Boolean = true,
    val brokerConnected: Boolean = false,
    val brokerCredentialPresent: Boolean = false,
    val brokerRevoked: Boolean = false,
    val dependentJobsRunning: Boolean = false,
    val reserveMinor: Long = DEFAULT_RESERVE_MINOR,
    val goalHorizonYears: Int = DEFAULT_GOAL_HORIZON_YEARS,
    val notificationsEnabled: Boolean = true,
    val fastAlertsEnabled: Boolean = false,
    val darkTheme: Boolean = false,
)

internal data class CommonSourceCategory(
    val name: String,
    val detail: String,
)

internal data class SubscriptionTierUi(
    val name: String,
    val status: String,
    val available: Boolean,
    val purchasable: Boolean,
)

internal fun connectBrokerFixtureState(state: LocalSettingsState): LocalSettingsState = state.copy(
    portfolioPresent = true,
    brokerConnected = true,
    brokerCredentialPresent = true,
    brokerRevoked = false,
    dependentJobsRunning = true,
)

internal fun disconnectBrokerState(state: LocalSettingsState): LocalSettingsState = state.copy(
    brokerConnected = false,
    brokerCredentialPresent = false,
    brokerRevoked = false,
    dependentJobsRunning = false,
)

internal fun revokeBrokerFixtureState(state: LocalSettingsState): LocalSettingsState = state.copy(
    brokerConnected = false,
    brokerCredentialPresent = true,
    brokerRevoked = true,
    dependentJobsRunning = false,
)

internal fun deleteLocalPortfolioState(state: LocalSettingsState): LocalSettingsState =
    disconnectBrokerState(state).copy(portfolioPresent = false)

internal fun restoreDemoPortfolioState(state: LocalSettingsState): LocalSettingsState =
    state.copy(portfolioPresent = true)

internal fun notificationsState(
    state: LocalSettingsState,
    enabled: Boolean,
): LocalSettingsState = state.copy(
    notificationsEnabled = enabled,
    fastAlertsEnabled = enabled && state.fastAlertsEnabled,
)

internal fun fastAlertsState(
    state: LocalSettingsState,
    enabled: Boolean,
): LocalSettingsState = state.copy(
    fastAlertsEnabled = enabled && state.notificationsEnabled,
)

internal fun reservePresetsMinor(): List<Long> = listOf(
    10_000_000L,
    DEFAULT_RESERVE_MINOR,
    50_000_000L,
)

internal fun goalHorizonPresets(): List<Int> = listOf(1, DEFAULT_GOAL_HORIZON_YEARS, 5)

internal fun commonSourceCategories(): List<CommonSourceCategory> = listOf(
    CommonSourceCategory(
        name = "Рыночные данные",
        detail = "Общие котировки и справочники · серверный общий слой, без локального портфеля.",
    ),
    CommonSourceCategory(
        name = "События эмитентов",
        detail = "Общие подтверждённые факты и новости по инструментам.",
    ),
    CommonSourceCategory(
        name = "Банк России",
        detail = "Официальные общие макроэкономические и регуляторные данные.",
    ),
    CommonSourceCategory(
        name = "T-Invest · только чтение",
        detail = "Персональный доступ подключается отдельно; в этой версии используется только демо-состояние.",
    ),
)

internal fun subscriptionTiers(): List<SubscriptionTierUi> = listOf(
    SubscriptionTierUi(
        name = "Наблюдение",
        status = "Доступно в текущем аналитическом режиме.",
        available = true,
        purchasable = false,
    ),
    SubscriptionTierUi(
        name = "Аналитика",
        status = "Может стать доступна после подключения соответствующей системной функции.",
        available = false,
        purchasable = false,
    ),
    SubscriptionTierUi(
        name = "Персональный план",
        status = "Недоступен до отдельного регуляторного допуска.",
        available = false,
        purchasable = false,
    ),
    SubscriptionTierUi(
        name = "Цели и доход",
        status = "Только фактически реализованные аналитические функции.",
        available = false,
        purchasable = false,
    ),
    SubscriptionTierUi(
        name = "Капитал",
        status = "Только фактически реализованные аналитические функции.",
        available = false,
        purchasable = false,
    ),
)

internal fun buildLocalExportSummary(state: LocalSettingsState): String = listOf(
    "OMNICIO · локальный экспорт демо-данных",
    "portfolio_present=" + state.portfolioPresent,
    "broker_connected=" + state.brokerConnected,
    "broker_revoked=" + state.brokerRevoked,
    "reserve_minor=" + state.reserveMinor,
    "goal_horizon_years=" + state.goalHorizonYears,
    "notifications_enabled=" + state.notificationsEnabled,
    "fast_alerts_enabled=" + state.fastAlertsEnabled,
    "dark_theme=" + state.darkTheme,
    "broker_credential=not_exported",
).joinToString(separator = "\n")
