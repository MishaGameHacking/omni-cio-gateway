package ru.omnicio.app.ui.workspace

import androidx.compose.runtime.staticCompositionLocalOf

enum class WorkspaceRoute { Appearance, Assistant, Strategies, Market, Messages, Education }
val LocalWorkspaceNavigator = staticCompositionLocalOf<(WorkspaceRoute) -> Unit> { {} }
