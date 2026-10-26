package ru.omnicio.app.ui

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.*
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Popup
import androidx.compose.ui.window.PopupProperties
import kotlinx.coroutines.launch
import ru.omnicio.app.ui.spatial.LocalFlatMotion
import ru.omnicio.app.ui.spatial.SpatialMotion
import ru.omnicio.app.ui.spectrum.*
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


/** A semantic brain button; the bottom bar contains only destinations. */
@Composable
internal fun AnalystMenuButton(open: () -> Unit) {
    SpectrumGlyphButton(SpectrumSymbol.Brain, "Открыть меню", open,
        Modifier.size(48.dp).testTag("navigation-menu-open"), active = true)
}

@Composable
internal fun AnalystHeaderMenu() {
    if (!LocalWideNavigation.current) LocalOpenNavigationMenu.current?.let { AnalystMenuButton(it) }
}

/** Menu dismissal finishes before a route-bound draft guard can continue. */
@Composable
fun AnalystNavigationPanels(
    selected: AnalystTab,
    selectedWorkspace: WorkspaceRoute? = null,
    wide: Boolean,
    navigateTab: (AnalystTab) -> Unit,
    navigateWorkspace: (WorkspaceRoute) -> Unit,
    content: @Composable () -> Unit,
) {
    if (ru.omnicio.app.ui.workspace.LocalWorkspaceAutoSave.current == null) {
        ru.omnicio.app.ui.workspace.WorkspaceAutoSaveProvider {
            AnalystNavigationPanels(selected, selectedWorkspace, wide, navigateTab, navigateWorkspace, content)
        }
        return
    }
    var menuOpen by remember { mutableStateOf(false) }
    val guard = remember { PanelNavigationGuard() }
    val currentDestination by rememberUpdatedState(selected to selectedWorkspace)
    val openMenu: () -> Unit = { menuOpen = true }
    val detailRoute = selectedWorkspace
    val exitScope = detailRoute?.let { PanelExitScope(it, guard) }
    val detailMenu = detailRoute?.takeIf { !wide }?.let { DetailNavigationMenu(it, openMenu) }
    val selectTab: (AnalystTab) -> Unit = { tab ->
        val source = currentDestination
        guard.requestDestination(source, { currentDestination },
            source.second == null && tab == source.first.primaryDestination()) { navigateTab(tab) }
    }
    val selectWorkspace: (WorkspaceRoute) -> Unit = { route ->
        val source = currentDestination
        guard.requestDestination(source, { currentDestination }, source.second == route) { navigateWorkspace(route) }
    }
    CompositionLocalProvider(
        LocalWideNavigation provides wide,
        LocalOpenNavigationMenu provides openMenu,
        LocalDetailNavigationMenu provides detailMenu,
        LocalPanelExitScope provides exitScope,
    ) {
        // Content stays in one slot when a window changes size or a popup opens.
        BoxWithConstraints(Modifier.fillMaxSize().clipToBounds().semantics { testTagsAsResourceId = true }) {
            Row(Modifier.fillMaxSize()) {
                if (wide) AnalystSideRail(selected, selectedWorkspace, selectTab, selectWorkspace)
                Box(Modifier.weight(1f).fillMaxHeight()) { content() }
            }
            if (menuOpen) {
                val width = (maxWidth - 24.dp).coerceAtMost(600.dp)
                val height = maxHeight * .65f
                AnalystIconDock(selected, selectedWorkspace, width, height,
                    onDismiss = { menuOpen = false },
                    onSelect = { destination ->
                        menuOpen = false
                        destination.workspace?.let(selectWorkspace) ?: destination.tab?.let(selectTab)
                    })
            }
        }
    }
}

/** Short, scrollable icon rows. A native focusable popup consumes outside/Back. */
@Composable
private fun AnalystIconDock(selected: AnalystTab, selectedWorkspace: WorkspaceRoute?,
    width: androidx.compose.ui.unit.Dp, height: androidx.compose.ui.unit.Dp,
    onDismiss: () -> Unit, onSelect: (AnalystDestination) -> Unit) {
    val motion = LocalFlatMotion.current
    val enabled = motion != SpatialMotion.Off
    val opacity = remember { Animatable(if (enabled) 0f else 1f) }
    val scope = rememberCoroutineScope()
    var closing by remember { mutableStateOf(false) }
    val currentDismiss by rememberUpdatedState(onDismiss)
    val currentSelect by rememberUpdatedState(onSelect)
    val close: (AnalystDestination?) -> Unit = { destination ->
        if (!closing) {
            closing = true
            scope.launch {
                opacity.animateTo(0f, tween(if (enabled) 140 else 0))
                if (destination == null) currentDismiss() else currentSelect(destination)
            }
        }
    }
    LaunchedEffect(enabled) { if (!closing) opacity.animateTo(1f, tween(if (enabled) 180 else 0)) }
    val density = LocalDensity.current
    val top = WindowInsets.safeDrawing.getTop(density)
    val offset = with(density) { IntOffset(12.dp.roundToPx(), top + 60.dp.roundToPx()) }
    Popup(alignment = Alignment.TopStart, offset = offset, onDismissRequest = { close(null) },
        properties = PopupProperties(focusable = true, dismissOnBackPress = false,
            dismissOnClickOutside = true, clippingEnabled = true)) {
        val backProgress by rememberDockBackProgress(enabled) { close(null) }
        val colors = MaterialTheme.colorScheme
        Column(Modifier.width(width).heightIn(max = height)
            .graphicsLayer {
                alpha = opacity.value
                scaleX = (.96f + .04f * opacity.value) * (1f - .06f * backProgress)
                scaleY = scaleX
                translationY = -12.dp.toPx() * backProgress
            }
            .clip(RoundedCornerShape(28.dp))
            .background(Brush.verticalGradient(listOf(colors.surfaceContainerHigh, colors.surface)))
            .border(1.dp, colors.outlineVariant, RoundedCornerShape(28.dp))
            .semantics { testTagsAsResourceId = true; paneTitle = "Разделы" }
            .testTag("navigation-panel")) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.End) {
                SpectrumGlyphButton(SpectrumSymbol.Close, "Закрыть меню", { close(null) },
                    Modifier.size(48.dp).testTag("navigation-menu-close"))
            }
            Column(Modifier.fillMaxWidth().weight(1f, fill = false)
                .verticalScroll(rememberScrollState()).testTag("navigation-panel-content")
                .padding(start = 8.dp, end = 8.dp, bottom = 12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)) {
                analystMenuDestinations.groupBy { it.group }.entries.forEachIndexed { row, (group, destinations) ->
                    if (row > 0) HorizontalDivider(Modifier.padding(horizontal = 12.dp), color = colors.outlineVariant)
                    LazyRow(Modifier.fillMaxWidth().semantics { contentDescription = group.title }
                        .testTag("navigation-row-" + group.name.lowercase()),
                        contentPadding = PaddingValues(horizontal = 4.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        itemsIndexed(destinations, key = { _, item -> item.id }) { index, destination ->
                            val route = destination.workspace
                            val active = if (route != null) route == selectedWorkspace
                                else selectedWorkspace == null && destination.tab == selected
                            val enter = remember { Animatable(if (enabled) 0f else 1f) }
                            LaunchedEffect(enabled) {
                                enter.animateTo(1f, tween(if (enabled) 220 else 0,
                                    delayMillis = if (enabled) (row * 36 + index * 32).coerceAtMost(260) else 0))
                            }
                            SpectrumGlyphButton(destination.symbol, destination.title, { close(destination) },
                                Modifier.size(56.dp).graphicsLayer {
                                    alpha = enter.value
                                    translationY = (1f - enter.value) * 14.dp.toPx()
                                    scaleX = .8f + .2f * enter.value; scaleY = scaleX
                                }.testTag(if (route != null) "navigation-workspace-" + route.name.lowercase()
                                    else "navigation-primary-" + destination.tab!!.name.lowercase()),
                                active = active, enabled = !closing)
                        }
                    }
                }
            }
        }
    }
}
