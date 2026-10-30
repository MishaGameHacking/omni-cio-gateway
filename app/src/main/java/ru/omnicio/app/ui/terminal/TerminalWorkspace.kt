package ru.omnicio.app.ui.terminal

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.paneTitle
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.LocalOpenNavigationMenu
import ru.omnicio.app.ui.LocalPanelExitScope
import ru.omnicio.app.ui.LocalRailVisible
import ru.omnicio.app.ui.PanelExitScope
import ru.omnicio.app.ui.PanelNavigationGuard
import ru.omnicio.app.ui.spatial.SpatialBackHandler
import ru.omnicio.app.ui.workspace.WorkspaceAutoSaveProvider
import ru.omnicio.app.ui.workspace.WorkspaceRoute

internal val LocalTerminalDetail = staticCompositionLocalOf { false }

/** The dashboard stays mounted under one detail pane. No navigation rail or page tabs. */
@Composable
internal fun TerminalWorkspace(visible: Boolean, route: WorkspaceRoute?, title: String, close: ()->Unit,
    dashboard: @Composable ()->Unit, detail: @Composable ()->Unit) {
    val guard=remember { PanelNavigationGuard() }
    val exit=route?.let { PanelExitScope(it,guard) }
    val guardedClose: ()->Unit={ guard.request(route,close) }
    WorkspaceAutoSaveProvider {
        CompositionLocalProvider(LocalRailVisible provides true,LocalOpenNavigationMenu provides null,
            LocalPanelExitScope provides exit) {
            Box(Modifier.fillMaxSize()) {
                Box(if(visible) Modifier.fillMaxSize().clearAndSetSemantics { } else Modifier.fillMaxSize()) { dashboard() }
                if(visible) {
                    SpatialBackHandler(true) { guardedClose() }
                    Surface(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.safeDrawing).padding(top=8.dp),
                        color=MaterialTheme.colorScheme.background,shape=TerminalShape,
                        border=BorderStroke(1.dp,MaterialTheme.colorScheme.outlineVariant)) {
                        Column(Modifier.fillMaxSize().semantics { paneTitle=title }) {
                            Row(Modifier.fillMaxWidth().padding(horizontal=12.dp),verticalAlignment=Alignment.CenterVertically) {
                                TerminalLabel(title.uppercase(),Modifier.weight(1f))
                                TerminalIconButton("close","Закрыть и вернуться к пульту",guardedClose)
                            }
                            HorizontalDivider(color=MaterialTheme.colorScheme.outlineVariant)
                            Box(Modifier.weight(1f).consumeWindowInsets(WindowInsets.safeDrawing)) {
                                CompositionLocalProvider(LocalTerminalDetail provides true,content=detail)
                            }
                        }
                    }
                }
            }
        }
    }
}
