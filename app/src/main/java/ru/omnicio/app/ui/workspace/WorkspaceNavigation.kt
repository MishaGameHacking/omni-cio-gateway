package ru.omnicio.app.ui.workspace

import androidx.compose.runtime.staticCompositionLocalOf

enum class WorkspaceRoute { AnalysisSettings, Appearance, Assistant, Strategies, Market, Messages, Education, NotificationSettings,
    Discovery, Library, Devices, ActivityHistory, Goals, NewFeatures, AnalysisTimeline, Reports }
val LocalWorkspaceNavigator = staticCompositionLocalOf<(WorkspaceRoute) -> Unit> { {} }

val LocalWorkspaceBack = staticCompositionLocalOf<() -> Unit> { {} }
val LocalWorkspaceBackProgress = staticCompositionLocalOf { 0f }
data class RecentDestination(val name: String, val title: String)
data class WorkspaceHistory(val items: List<RecentDestination> = emptyList(), val open: (String) -> Unit = {})
val LocalWorkspaceHistory = staticCompositionLocalOf { WorkspaceHistory() }
