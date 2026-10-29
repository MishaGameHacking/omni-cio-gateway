package ru.omnicio.app.ui

import androidx.compose.runtime.staticCompositionLocalOf
import ru.omnicio.app.ui.spectrum.SpectrumSymbol
import ru.omnicio.app.ui.workspace.WorkspaceRoute

enum class NavigationGroup(val title: String) { Main("Основное"), Portfolio("Портфель и рынок"),
    Research("Анализ и исследования"), Personal("Личное") }

data class AnalystDestination(val id: String, val title: String, val symbol: SpectrumSymbol,
    val group: NavigationGroup, val parent: AnalystTab, val tab: AnalystTab? = null,
    val workspace: WorkspaceRoute? = null)

/** IDs remain compatible with restored navigation, notifications and saved drafts. */
val analystDestinations: List<AnalystDestination> = listOf(
    AnalystDestination("Home", "Система", SpectrumSymbol.Home, NavigationGroup.Main, AnalystTab.Home, tab = AnalystTab.Home),
    AnalystDestination("Portfolio", "Аналитика", SpectrumSymbol.Portfolio, NavigationGroup.Main, AnalystTab.Portfolio, tab = AnalystTab.Portfolio),
    AnalystDestination("Recommendations", "Решения", SpectrumSymbol.Decisions, NavigationGroup.Main, AnalystTab.Actions, tab = AnalystTab.Actions),
    AnalystDestination("Profile", "Настройки", SpectrumSymbol.Settings, NavigationGroup.Main, AnalystTab.Profile, tab = AnalystTab.Profile),
    AnalystDestination("Risk", "Риски", SpectrumSymbol.Risk, NavigationGroup.Portfolio, AnalystTab.Portfolio, tab = AnalystTab.Risk),
    AnalystDestination("Strategies", "Стратегия", SpectrumSymbol.Strategy, NavigationGroup.Portfolio, AnalystTab.Portfolio, workspace = WorkspaceRoute.Strategies),
    AnalystDestination("Market", "Рынок", SpectrumSymbol.Market, NavigationGroup.Portfolio, AnalystTab.Portfolio, workspace = WorkspaceRoute.Market),
    AnalystDestination("Discovery", "Поиск инструментов", SpectrumSymbol.Search, NavigationGroup.Portfolio, AnalystTab.Portfolio, workspace = WorkspaceRoute.Discovery),
    AnalystDestination("Goals", "Цель и резерв", SpectrumSymbol.Goal, NavigationGroup.Portfolio, AnalystTab.Portfolio, workspace = WorkspaceRoute.Goals),
    AnalystDestination("Assistant", "Аналитик", SpectrumSymbol.Analyst, NavigationGroup.Research, AnalystTab.Actions, workspace = WorkspaceRoute.Assistant),
    AnalystDestination("Reports", "Выводы аналитика", SpectrumSymbol.Reports, NavigationGroup.Research, AnalystTab.Actions, workspace = WorkspaceRoute.Reports),
    AnalystDestination("Library", "Исследования", SpectrumSymbol.Sources, NavigationGroup.Research, AnalystTab.Actions, workspace = WorkspaceRoute.Library),
    AnalystDestination("AnalysisTimeline", "Работа аналитика", SpectrumSymbol.Timeline, NavigationGroup.Research, AnalystTab.Actions, workspace = WorkspaceRoute.AnalysisTimeline),
    AnalystDestination("Messages", "События", SpectrumSymbol.Events, NavigationGroup.Research, AnalystTab.Home, workspace = WorkspaceRoute.Messages),
    AnalystDestination("AnalysisSettings", "Правила анализа", SpectrumSymbol.Rules, NavigationGroup.Personal, AnalystTab.Profile, workspace = WorkspaceRoute.AnalysisSettings),
    AnalystDestination("NotificationSettings", "Уведомления", SpectrumSymbol.Notifications, NavigationGroup.Personal, AnalystTab.Profile, workspace = WorkspaceRoute.NotificationSettings),
    AnalystDestination("Appearance", "Оформление", SpectrumSymbol.Appearance, NavigationGroup.Personal, AnalystTab.Profile, workspace = WorkspaceRoute.Appearance),
    AnalystDestination("Devices", "Устройства", SpectrumSymbol.Devices, NavigationGroup.Personal, AnalystTab.Profile, workspace = WorkspaceRoute.Devices),
    AnalystDestination("ActivityHistory", "Недавно открыто", SpectrumSymbol.Recent, NavigationGroup.Personal, AnalystTab.Home, workspace = WorkspaceRoute.ActivityHistory),
    AnalystDestination("Education", "Обучение", SpectrumSymbol.Education, NavigationGroup.Personal, AnalystTab.Profile, tab = AnalystTab.Education, workspace = WorkspaceRoute.Education),
    AnalystDestination("NewFeatures", "Что нового", SpectrumSymbol.NewFeatures, NavigationGroup.Personal, AnalystTab.Profile, workspace = WorkspaceRoute.NewFeatures),
    AnalystDestination("TApi", "Подключение Т-Инвестиций", SpectrumSymbol.Sources, NavigationGroup.Personal, AnalystTab.Profile),
)

val analystPrimaryDestinations = analystDestinations.filter { it.group == NavigationGroup.Main }
val analystMenuDestinations = analystDestinations.filter { it.tab != null || it.workspace != null }
fun analystDestination(id: String): AnalystDestination? = analystDestinations.firstOrNull { it.id == id }
internal fun AnalystTab.destination(): AnalystDestination = analystDestinations.first { it.tab == this }
internal fun WorkspaceRoute.destination(): AnalystDestination = analystDestinations.first { it.workspace == this }

/** Section switches return to their root; contextual drill-down uses the ordinary Back stack. */
fun sectionBackStack(destinationId: String): List<String>? {
    val destination = analystDestination(destinationId) ?: return null
    return if (destination.group == NavigationGroup.Main) emptyList() else listOf(destination.parent.destination().id)
}

val LocalAnalystSectionNavigator = staticCompositionLocalOf<(String) -> Unit> { {} }

