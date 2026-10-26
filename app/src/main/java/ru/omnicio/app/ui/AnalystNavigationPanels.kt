package ru.omnicio.app.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.path
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import ru.omnicio.app.ui.spectrum.SpectrumIconButton
import ru.omnicio.app.ui.spectrum.SpectrumSymbol
import ru.omnicio.app.ui.workspace.WorkspaceRoute

internal val LocalOpenNavigationMenu = staticCompositionLocalOf<(() -> Unit)?> { null }

/** A pending editor exit belongs to one mounted page and can continue only once. */
internal class PanelNavigationGuard {
    internal class Binding(val route: WorkspaceRoute, val request: (() -> Unit) -> Unit)
    private var current: Binding? = null

    fun register(route: WorkspaceRoute, request: (() -> Unit) -> Unit): Binding =
        Binding(route, request).also { current = it }

    fun unregister(binding: Binding) {
        if (current === binding) current = null
    }

    fun request(route: WorkspaceRoute?, navigate: () -> Unit) {
        val owner = current?.takeIf { it.route == route }
        var continued = false
        val proceed: () -> Unit = {
            if (!continued && (owner == null || current === owner)) {
                continued = true
                navigate()
            }
        }
        if (owner == null) proceed() else owner.request(proceed)
    }

    /** The drawer and wide rail share this actual route-bound exit path. */
    fun requestDestination(
        source: Pair<AnalystTab, WorkspaceRoute?>,
        current: () -> Pair<AnalystTab, WorkspaceRoute?>,
        sameDestination: Boolean,
        navigate: () -> Unit,
    ) {
        if (!sameDestination && current() == source) {
            request(source.second) { if (current() == source) navigate() }
        }
    }
}

internal data class PanelExitScope(val route: WorkspaceRoute, val guard: PanelNavigationGuard)
internal val LocalPanelExitScope = staticCompositionLocalOf<PanelExitScope?> { null }

internal data class DetailNavigationMenu(
    val route: WorkspaceRoute,
    val open: () -> Unit,
)

internal val LocalDetailNavigationMenu = staticCompositionLocalOf<DetailNavigationMenu?> { null }

/** Outgoing AnimatedContent must never register as the incoming destination. */
@Composable
internal fun RegisterPanelExit(route: WorkspaceRoute, request: (() -> Unit) -> Unit) {
    val owner = LocalPanelExitScope.current?.takeIf { it.route == route }
    val currentRequest by rememberUpdatedState(request)
    DisposableEffect(owner?.guard, route) {
        val binding = owner?.guard?.register(route) { proceed -> currentRequest(proceed) }
        onDispose { if (binding != null) owner?.guard?.unregister(binding) }
    }
}

private val detailDestinations = listOf(
    WorkspaceRoute.Strategies to "Стратегия",
    WorkspaceRoute.Market to "Рынок",
    WorkspaceRoute.Messages to "События",
    WorkspaceRoute.Assistant to "Ассистент",
    WorkspaceRoute.Appearance to "Оформление",
    WorkspaceRoute.Library to "Исследования",
)

private val menuIcon = ImageVector.Builder("Navigation menu", 24.dp, 24.dp, 24f, 24f).apply {
    path(fill = SolidColor(Color.Black)) {
        moveTo(3f, 5f); lineTo(21f, 5f); lineTo(21f, 7f); lineTo(3f, 7f); close()
        moveTo(3f, 11f); lineTo(21f, 11f); lineTo(21f, 13f); lineTo(3f, 13f); close()
        moveTo(3f, 17f); lineTo(21f, 17f); lineTo(21f, 19f); lineTo(3f, 19f); close()
    }
}.build()

@Composable
internal fun AnalystMenuButton(open: () -> Unit) {
    IconButton(open, Modifier.size(48.dp).testTag("navigation-menu-open")) {
        Icon(menuIcon, "Открыть меню", tint = MaterialTheme.colorScheme.onSurface)
    }
}

/** Shared navigation only; all settings and commands remain on their real screens. */
@Composable
fun AnalystNavigationPanels(
    selected: AnalystTab,
    selectedWorkspace: WorkspaceRoute? = null,
    wide: Boolean,
    navigateTab: (AnalystTab) -> Unit,
    navigateWorkspace: (WorkspaceRoute) -> Unit,
    content: @Composable () -> Unit,
) {
    val drawer = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    val guard = remember { PanelNavigationGuard() }
    val currentDestination by rememberUpdatedState(selected to selectedWorkspace)
    val openMenu: () -> Unit = { scope.launch { drawer.open() } }
    val closeThen: (Boolean, () -> Unit) -> Unit = { sameDestination, navigate ->
        val source = currentDestination
        scope.launch {
            drawer.close()
            if (drawer.isClosed) {
                guard.requestDestination(source, { currentDestination }, sameDestination, navigate)
            }
        }
    }
    val detailRoute = selectedWorkspace?.takeIf { route -> detailDestinations.any { it.first == route } }
    val exitScope = detailRoute?.let { PanelExitScope(it, guard) }
    val detailMenu = detailRoute?.takeIf { !wide }?.let { DetailNavigationMenu(it, openMenu) }
    val selectWideTab: (AnalystTab) -> Unit = { tab ->
        val source = currentDestination
        guard.requestDestination(source, { currentDestination },
            source.second == null && tab == source.first.primaryDestination()) { navigateTab(tab) }
    }
    LaunchedEffect(wide) {
        if (wide) drawer.snapTo(DrawerValue.Closed)
    }
    CompositionLocalProvider(
        LocalWideNavigation provides wide,
        LocalOpenNavigationMenu provides if (wide) null else openMenu,
        LocalDetailNavigationMenu provides detailMenu,
        LocalPanelExitScope provides exitScope,
    ) {
        // Keep content in the same composition slot when the window changes size.
        ModalNavigationDrawer(
            drawerState = drawer,
            // Only the menu button opens the sheet; edge gestures belong to Android Back.
            gesturesEnabled = false,
            modifier = Modifier.fillMaxSize().semantics { testTagsAsResourceId = true },
            drawerContent = {
                // The DrawerState overload handles native predictive Back and cancellation.
                ModalDrawerSheet(
                    drawerState = drawer,
                    modifier = Modifier.fillMaxHeight().widthIn(max = 360.dp).testTag("navigation-panel"),
                    windowInsets = WindowInsets.safeDrawing,
                ) {
                    Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Разделы", Modifier.weight(1f).semantics { heading() },
                            style = MaterialTheme.typography.titleLarge)
                        SpectrumIconButton(SpectrumSymbol.Close, "Закрыть меню",
                            { scope.launch { drawer.close() } }, Modifier.testTag("navigation-menu-close"))
                    }
                    Column(Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState())
                        .testTag("navigation-panel-content").padding(horizontal = 12.dp, vertical = 8.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        listOf(AnalystTab.Home to "Система", AnalystTab.Actions to "Решения",
                            AnalystTab.Profile to "Настройки").forEach { (tab, title) ->
                            NavigationDrawerItem(
                                label = { Text(title, softWrap = true) },
                                selected = selectedWorkspace == null && tab == selected.primaryDestination(),
                                onClick = { closeThen(selectedWorkspace == null && tab == selected.primaryDestination()) { navigateTab(tab) } },
                                modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)
                                    .testTag("navigation-primary-" + tab.name.lowercase()),
                            )
                        }
                        HorizontalDivider(Modifier.padding(vertical = 8.dp))
                        detailDestinations.forEach { (route, title) ->
                            NavigationDrawerItem(
                                label = { Text(title, softWrap = true) },
                                selected = route == selectedWorkspace,
                                onClick = { closeThen(route == selectedWorkspace) { navigateWorkspace(route) } },
                                modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)
                                    .testTag("navigation-workspace-" + route.name.lowercase()),
                            )
                        }
                    }
                }
            },
        ) {
            Row(Modifier.fillMaxSize()) {
                if (wide) AnalystSideRail(selected, selectWideTab)
                Box(Modifier.weight(1f).fillMaxHeight()) { content() }
            }
        }
    }
}
