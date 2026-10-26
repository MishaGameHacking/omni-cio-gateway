"""Administrative text delta for the owner's brain-triggered navigation.

The resulting source is applied/compiled/tested only by the Windows transport.
"""

def apply(files, base):
    ui = 'app/src/main/java/ru/omnicio/app/ui/'
    def get(path):
        return files[path] if path in files else base(path)
    def put(path, value):
        files[path] = value
    def replace(path, old, new, count=1):
        value = get(path)
        assert value.count(old) == count, (path, old[:100], value.count(old), count)
        put(path, value.replace(old, new))

    # Original host failures: update fixture labels, preserving every rejection.
    for path in ('.github/scripts/navigation_detail_probe.py',
                 '.github/scripts/tests/test_navigation_detail_probe.py',
                 '.github/scripts/tests/test_navigation_return_scroll.py',
                 '.github/scripts/tests/test_portfolio_preferences_traversal.py'):
        value = get(path).replace('"Система"', '"Главная"')
        value = value.replace('Предпросмотр цвета, контраста и движения', 'Единый стиль · движение и удобство')
        put(path, value)

    path='.github/scripts/tests/test_portfolio_preferences_traversal.py'
    replace(path, '''                (500, "Тема"), (1400, "Цвет акцента"), (2300, "Плотность карточек"),
                (3200, "Движение"), (4100, "Яркое освещение"), (5000, "Приватность"),
                (5700, "Вернуть оформление по умолчанию")''',
        '''                (500, "Движение"), (1400, "Яркое освещение"), (2300, "Приватность"),
                (3000, "Вернуть оформление по умолчанию")''')
    replace(path,'min(5800 * self.scale - self.height','min(3100 * self.scale - self.height')

    path = ui+'AnalystNavigationPanels.kt'
    value = get(path)
    start = value.index('internal val LocalOpenNavigationMenu')
    end = value.index('private val detailDestinations')
    preserved = value[start:end]
    put(path, '''package ru.omnicio.app.ui

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

'''+preserved+'''
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
''')

    put(ui+'DockPredictiveBack.kt', '''package ru.omnicio.app.ui

import android.view.View
import android.window.BackEvent
import android.window.OnBackAnimationCallback
import android.window.OnBackInvokedDispatcher
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.snap
import androidx.compose.animation.core.tween
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalView

/** A Popup owns a different window from its Activity, including its Back dispatcher. */
@Composable
internal fun rememberDockBackProgress(motionEnabled: Boolean, onCommit: () -> Unit): State<Float> {
    val view = LocalView.current
    val currentCommit by rememberUpdatedState(onCommit)
    var progress by remember { mutableFloatStateOf(0f) }
    var tracking by remember { mutableStateOf(false) }
    DisposableEffect(view) {
        var dispatcher: OnBackInvokedDispatcher? = null
        val callback = object : OnBackAnimationCallback {
            override fun onBackStarted(event: BackEvent) { tracking = true; progress = 0f }
            override fun onBackProgressed(event: BackEvent) { progress = event.progress.coerceIn(0f, 1f) }
            override fun onBackCancelled() { tracking = false; progress = 0f }
            override fun onBackInvoked() { tracking = false; currentCommit() }
        }
        fun detach() {
            dispatcher?.unregisterOnBackInvokedCallback(callback)
            dispatcher = null
        }
        fun attach() {
            val actual = view.findOnBackInvokedDispatcher()
            if (actual !== dispatcher) {
                detach()
                actual?.registerOnBackInvokedCallback(OnBackInvokedDispatcher.PRIORITY_OVERLAY, callback)
                dispatcher = actual
            }
        }
        val listener = object : View.OnAttachStateChangeListener {
            override fun onViewAttachedToWindow(v: View) = attach()
            override fun onViewDetachedFromWindow(v: View) = detach()
        }
        view.addOnAttachStateChangeListener(listener)
        if (view.isAttachedToWindow) attach()
        onDispose { view.removeOnAttachStateChangeListener(listener); detach() }
    }
    return animateFloatAsState(if (motionEnabled) progress else 0f,
        animationSpec = if (tracking || !motionEnabled) snap() else tween(160), label = "dock-back")
}
''')

    # All four destinations keep their full native hit area and accessible name.
    path=ui+'AnalystBottomBar.kt'
    value=get(path)
    a=value.index('/** Four direct destinations;')
    b=value.index('internal fun AnalystTab.primaryDestination()')
    value=value[:a]+'''/** A compact icon dock; labels remain available to accessibility and tooltips. */
@Suppress("UNUSED_PARAMETER")
@Composable
fun AnalystBottomBar(selected: AnalystTab, onPortfolioClick: () -> Unit,
    onProfileClick: () -> Unit, modifier: Modifier = Modifier) {
    if (LocalWideNavigation.current) return
    val navigate = LocalAnalystTabNavigator.current
    Surface(modifier.fillMaxWidth().zIndex(1f).clipToBounds().testTag("analyst-bottom-bar"),
        color = MaterialTheme.colorScheme.surface) {
        Column {
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            Row(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 16.dp, vertical = 6.dp)
                .selectableGroup(), horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically) {
                primaryTabs.forEach { tab ->
                    SpectrumGlyphButton(tab.symbol(), tab.label(), { navigate(tab) },
                        Modifier.size(56.dp).testTag("bottom-destination-" + tab.name.lowercase()),
                        active = tab == selected.primaryDestination(), role = Role.Tab)
                }
            }
        }
    }
}

'''+value[b:]
    a=value.index('@Composable\nfun AnalystSideRail')
    value=value[:a]+'''@Suppress("UNUSED_PARAMETER")
@Composable
fun AnalystSideRail(selected: AnalystTab, selectedWorkspace: ru.omnicio.app.ui.workspace.WorkspaceRoute?,
    navigate: (AnalystTab) -> Unit, navigateWorkspace: (ru.omnicio.app.ui.workspace.WorkspaceRoute) -> Unit) {
    Surface(Modifier.fillMaxHeight().width(80.dp).zIndex(1f).clipToBounds().testTag("analyst-side-rail"),
        color = MaterialTheme.colorScheme.surface) {
        Column(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Vertical))
            .verticalScroll(rememberScrollState()).padding(8.dp).selectableGroup(),
            verticalArrangement = Arrangement.spacedBy(12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            LocalOpenNavigationMenu.current?.let { AnalystMenuButton(it) }
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            primaryTabs.forEach { tab ->
                SpectrumGlyphButton(tab.symbol(), tab.label(), { navigate(tab) },
                    Modifier.size(56.dp).testTag("rail-destination-" + tab.name.lowercase()),
                    active = tab == selected.primaryDestination(), role = Role.Tab)
            }
        }
    }
}
'''
    put(path,value)

    # A single native control owns semantics; the vector child is decorative.
    put(ui+'spectrum/SpectrumGlyphButton.kt','''package ru.omnicio.app.ui.spectrum

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.interaction.collectIsHoveredAsState
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.semantics.*
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spatial.*

/** Icon-only UI retains native names, long-press hints, focus and 48dp+ targets. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SpectrumGlyphButton(symbol: SpectrumSymbol, label: String, onClick: () -> Unit,
    modifier: Modifier = Modifier, active: Boolean = false, enabled: Boolean = true,
    role: Role = Role.Button) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val focused by interaction.collectIsFocusedAsState()
    val hovered by interaction.collectIsHoveredAsState()
    val colors = MaterialTheme.colorScheme
    val animated = LocalFlatMotion.current != SpatialMotion.Off
    val scale by animateFloatAsState(if (pressed) .93f else if (focused || hovered) 1.07f else 1f,
        tween(if (animated) 140 else 0), label = "icon-focus")
    val click = rememberSpatialHapticClick(SpatialHaptic.Selection, onClick)
    TooltipBox(positionProvider = TooltipDefaults.rememberPlainTooltipPositionProvider(),
        tooltip = { PlainTooltip { Text(label) } }, state = rememberTooltipState()) {
        Box(modifier.sizeIn(minWidth = 48.dp, minHeight = 48.dp)
            .semantics { contentDescription = label; selected = active }
            .clip(RoundedCornerShape(18.dp))
            .background(Brush.verticalGradient(listOf(
                if (active) colors.primaryContainer else colors.surfaceContainerHigh,
                if (active) colors.secondaryContainer else colors.surfaceContainerLow)))
            .border(if (focused) 2.dp else 1.dp,
                if (focused) colors.secondary else if (active) colors.primary else colors.outlineVariant,
                RoundedCornerShape(18.dp))
            .clickable(interactionSource = interaction, indication = null, enabled = enabled, role = role, onClick = click),
            contentAlignment = Alignment.Center) {
            SpatialIcon(symbol.asset, Modifier.size(36.dp).graphicsLayer { scaleX = scale; scaleY = scale },
                tint = if (enabled) colors.onSurface else colors.onSurfaceVariant,
                state = if (pressed) SpatialState.Pressed else if (active || focused) SpatialState.Selected else SpatialState.Idle,
                motionAllowed = enabled, colorMode = SpatialColorMode.Decorative)
        }
    }
}
''')

    # Brain is first in each existing header, without another chrome row.
    path=ui+'home/HomeScreen.kt'
    replace(path,'                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {',
        '                        ru.omnicio.app.ui.AnalystHeaderMenu()\n                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {')
    path=ui+'profile/ProfileScreen.kt'
    old='''                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text("Настройки", style = MaterialTheme.typography.headlineLarge,
                            modifier = Modifier.semantics { heading() })
                        Text("Правила работы вашей системы", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }'''
    new='''                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        ru.omnicio.app.ui.AnalystHeaderMenu()
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text("Настройки", style = MaterialTheme.typography.headlineLarge,
                                modifier = Modifier.semantics { heading() })
                            Text("Правила работы вашей системы", color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }'''
    replace(path,old,new)
    path=ui+'spectrum/SpectrumDesignSystem.kt'
    value=get(path);a=value.index('fun SpectrumPageHeader(');b=value.index('fun SpectrumPrimaryButton',a)
    part=value[a:b].replace('        Column(Modifier.weight(1f)',
        '        ru.omnicio.app.ui.AnalystHeaderMenu()\n        Column(Modifier.weight(1f)')
    part=part.replace('        SpectrumIcon(symbol, Modifier.size(32.dp), selected = true, tile = false, motionAllowed = false)',
        '        if (ru.omnicio.app.ui.LocalOpenNavigationMenu.current == null)\n            SpectrumIcon(symbol, Modifier.size(32.dp), selected = true, tile = false, motionAllowed = false)')
    put(path,value[:a]+part+value[b:])
    path=ui+'workspace/WorkspaceUi.kt'
    value=get(path)
    value=value.replace('            SpectrumIconButton(SpectrumSymbol.Back, "Назад", onBack)',
                        '            onOpenMenu?.let { AnalystMenuButton(it) }')
    value=value.replace('            onOpenMenu?.let { AnalystMenuButton(it) }\n        }',
                        '            SpectrumIconButton(SpectrumSymbol.Back, "Назад", onBack)\n        }')
    put(path,value)
    path=ui+'workspace/AppearanceScreen.kt'
    replace(path,'                        SpectrumIconButton(SpectrumSymbol.Back, "Назад", onBack)\n                        menu?.let { AnalystMenuButton(it.open) }',
        '                        menu?.let { AnalystMenuButton(it.open) }\n                        SpectrumIconButton(SpectrumSymbol.Back, "Назад", onBack)')

    # Unique, original vector artwork for each menu destination.
    path=ui+'spectrum/SpectrumIcon.kt'
    replace(path,'    Expand("plus"), Collapse("minus"), Currency("currency"),',
        '    Expand("plus"), Collapse("minus"), Currency("currency"),\n'
        '    Brain("brain"), Decisions("decisions"), Strategy("strategy"), Reports("reports"),\n'
        '    Timeline("timeline"), Events("events"), Rules("rules"), Appearance("appearance"),\n'
        '    Devices("devices"), Recent("recent"), NewFeatures("new_features"),')
    path=ui+'NavigationCatalogue.kt'
    value=get(path)
    mapping={'Recommendations':'Decisions','Strategies':'Strategy','Reports':'Reports',
        'AnalysisTimeline':'Timeline','Messages':'Events','AnalysisSettings':'Rules',
        'Appearance':'Appearance','Devices':'Devices','ActivityHistory':'Recent','NewFeatures':'NewFeatures'}
    import re
    for destination,symbol in mapping.items():
        value,n=re.subn(r'(AnalystDestination\("'+destination+r'", "[^"]+", SpectrumSymbol\.)\w+',r'\g<1>'+symbol,value)
        assert n==1,destination
    put(path,value)
    path=ui+'spatial/FlatArtwork.kt'
    value=get(path)
    anchor='    when (name) {\n'
    assert value.count(anchor)==1
    artwork='''        "brain" -> {
            val left = Path().apply {
                moveTo(46f, 18f); cubicTo(31f, 9f, 20f, 20f, 23f, 31f)
                cubicTo(8f, 33f, 8f, 50f, 18f, 57f)
                cubicTo(11f, 71f, 27f, 85f, 39f, 78f)
                cubicTo(43f, 87f, 49f, 83f, 49f, 73f); lineTo(49f, 27f)
                cubicTo(49f, 22f, 49f, 19f, 46f, 18f); close()
            }
            drawPath(left, teal.copy(alpha=.18f)); drawPath(left, teal, style=Stroke(5f,cap=StrokeCap.Round))
            withTransform({ translate(100f,0f); scale(-1f,1f,Offset.Zero) }) {
                drawPath(left, violet.copy(alpha=.18f)); drawPath(left, violet, style=Stroke(5f,cap=StrokeCap.Round))
            }
            path(listOf(23f to 31f,35f to 37f,35f to 47f),teal)
            path(listOf(18f to 57f,29f to 54f,37f to 62f),teal)
            path(listOf(77f to 31f,65f to 37f,65f to 47f),violet)
            path(listOf(82f to 57f,71f to 54f,63f to 62f),violet)
            circle(50f,49f,5f,amber,true)
        }
        "decisions" -> {
            box(24f,17f,53f,67f,ink.copy(alpha=.12f),true);box(24f,17f,53f,67f,violet)
            box(38f,11f,25f,13f,teal,true,4f)
            path(listOf(34f to 50f,45f to 61f,68f to 37f),teal)
            line(37f,73f,62f,73f,ink,4f)
        }
        "strategy" -> {
            line(50f,78f,50f,49f,teal);line(50f,49f,25f,30f,violet);line(50f,49f,76f,29f,amber)
            circle(50f,79f,9f,teal,true);box(15f,13f,21f,21f,violet,false,5f)
            path(listOf(66f to 16f,83f to 16f,83f to 33f),amber)
        }
        "reports" -> {
            path(listOf(23f to 13f,60f to 13f,78f to 31f,78f to 85f,23f to 85f),ink,false,true)
            path(listOf(60f to 14f,60f to 32f,77f to 32f),violet)
            line(34f,70f,34f,57f,teal,7f);line(49f,70f,49f,45f,violet,7f);line(64f,70f,64f,53f,amber,7f)
        }
        "timeline" -> {
            line(24f,20f,24f,82f,violet,4f)
            for (y in listOf(24f,50f,77f)) { circle(24f,y,6f,teal,true);line(39f,y,76f,y,ink,5f) }
            line(39f,34f,59f,34f,violet,3f);line(39f,60f,68f,60f,violet,3f)
        }
        "events" -> {
            box(17f,23f,66f,59f,ink.copy(alpha=.12f),true);box(17f,23f,66f,59f,violet)
            line(32f,15f,32f,31f,teal);line(68f,15f,68f,31f,teal);line(19f,39f,81f,39f,violet,4f)
            path(listOf(52f to 45f,40f to 62f,53f to 62f,45f to 76f,67f to 56f,54f to 56f),amber,true,true)
        }
        "rules" -> {
            line(23f,15f,23f,84f,violet,4f);line(50f,15f,50f,84f,teal,4f);line(77f,15f,77f,84f,violet,4f)
            box(15f,30f,16f,14f,teal,true,5f);box(42f,57f,16f,14f,amber,true,5f);box(69f,23f,16f,14f,ink,true,5f)
        }
        "appearance" -> {
            val palette = Path().apply { moveTo(51f,14f);cubicTo(7f,11f,5f,74f,40f,84f)
                cubicTo(64f,91f,48f,66f,64f,62f);cubicTo(93f,68f,92f,17f,51f,14f);close() }
            drawPath(palette, violet.copy(alpha=.18f));drawPath(palette,ink,style=stroke)
            circle(31f,34f,6f,teal,true);circle(51f,27f,6f,violet,true)
            circle(71f,36f,6f,amber,true);circle(26f,56f,6f,rose,true)
        }
        "devices" -> {
            box(13f,21f,54f,40f,violet,false,5f);line(39f,61f,39f,75f,violet);line(25f,77f,51f,77f,violet)
            box(59f,36f,26f,49f,teal,true,5f);box(63f,41f,18f,32f,ink.copy(alpha=.25f),true,2f)
            circle(72f,79f,2f,ink,true)
        }
        "recent" -> {
            drawArc(violet,215f,295f,false,Offset(18f,18f),Size(65f,65f),style=stroke)
            path(listOf(14f to 22f,15f to 43f,35f to 40f),teal)
            path(listOf(51f to 31f,51f to 52f,66f to 61f),teal)
        }
        "new_features" -> {
            path(listOf(50f to 12f,60f to 38f,87f to 49f,60f to 59f,50f to 86f,40f to 59f,13f to 49f,40f to 38f),violet,true,true)
            path(listOf(79f to 12f,82f to 20f,91f to 23f,82f to 26f,79f to 34f,76f to 26f,68f to 23f,76f to 20f),teal,true,true)
            circle(21f,78f,5f,amber,true)
        }
'''
    put(path,value.replace(anchor,anchor+artwork))

    # Modal content gets a bounded viewport, finite entry/exit and native dismissal.
    put(ui+'spectrum/SpectrumModal.kt','''package ru.omnicio.app.ui.spectrum

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import kotlinx.coroutines.launch
import ru.omnicio.app.ui.spatial.LocalFlatMotion
import ru.omnicio.app.ui.spatial.SpatialMotion

/** Outside/Back delegates to the caller, so an editor can retain its draft. */
@Composable
internal fun SpectrumModal(onDismissRequest: () -> Unit,
    properties: DialogProperties = DialogProperties(), content: @Composable () -> Unit) {
    val imeHost = rememberDialogImeHostHandoff()
    val animated = LocalFlatMotion.current != SpatialMotion.Off
    val progress = remember { Animatable(if (animated) 0f else 1f) }
    val scope = rememberCoroutineScope()
    val dismiss by rememberUpdatedState(onDismissRequest)
    var closing by remember { mutableStateOf(false) }
    val requestDismiss: () -> Unit = {
        if (!closing) {
            closing = true
            scope.launch {
                progress.animateTo(0f, tween(if (animated) 130 else 0))
                dismiss()
                // A guarded dismissal may deliberately leave this dialog mounted.
                closing = false
                progress.animateTo(1f, tween(if (animated) 130 else 0))
            }
        }
    }
    LaunchedEffect(animated) { progress.animateTo(1f, tween(if (animated) 200 else 0)) }
    CompositionLocalProvider(LocalDialogImeHostHandoff provides imeHost) {
      Dialog(onDismissRequest = requestDismiss, properties = properties) {
        DialogImeHostFocus(imeHost)
        BoxWithConstraints(Modifier.safeDrawingPadding().padding(vertical = 12.dp)) {
            Box(Modifier.widthIn(max = 600.dp).fillMaxWidth().heightIn(max = maxHeight * .82f)
                .graphicsLayer {
                    alpha = progress.value
                    scaleX = .96f + progress.value * .04f; scaleY = scaleX
                    translationY = (1f - progress.value) * 16.dp.toPx()
                }) { content() }
        }
      }
    }
}
''')
    path=ui+'spectrum/SpectrumAlertDialog.kt'
    replace(path,'    Dialog(onDismissRequest = onDismissRequest, properties = properties) {',
        '    SpectrumModal(onDismissRequest = onDismissRequest, properties = properties) {')
    path=ui+'workspace/WorkspaceDialog.kt'
    value=get(path)
    a=value.index('    val imeHost = rememberDialogImeHostHandoff()')
    value=value[:a]+'''    ru.omnicio.app.ui.spectrum.SpectrumModal(onDismissRequest = onDismiss,
        properties = DialogProperties(decorFitsSystemWindows = false)) {
        SpatialWindow(Modifier.widthIn(max = 600.dp).fillMaxWidth()) {
            SpectrumCard(Modifier.verticalScroll(rememberScrollState()).semantics { testTagsAsResourceId = true }
                .testTag("workspace-content"), emphasized = true) {
                Text(title, style = MaterialTheme.typography.titleLarge)
                content()
            }
        }
    }
}
'''
    for stale in ('import androidx.compose.runtime.CompositionLocalProvider\\n', 'import androidx.compose.ui.window.Dialog\\n',
                  'import ru.omnicio.app.ui.spectrum.DialogImeHostFocus\\n',
                  'import ru.omnicio.app.ui.spectrum.LocalDialogImeHostHandoff\\n',
                  'import ru.omnicio.app.ui.spectrum.rememberDialogImeHostHandoff\\n'):
        value=value.replace(stale.replace('\\n','\n'),'')
    # Every modal (including nested suggestion pickers) owns one handoff and inset boundary.
    put(path,value)

    # Existing source-contract tests follow the new owner requirement, not stale UI.
    path='.github/scripts/tests/test_unified_update_contract.py'
    value=get(path).replace("self.assertIn('analystMenuDestinations.groupBy',bar)",
        "self.assertIn('SpectrumGlyphButton',bar)\n        self.assertNotIn('AnalystMenuButton(openMenu)',bar)")
    put(path,value)

    path='.github/scripts/tests/test_android17_live_spectrum.py'
    value=get(path).replace("self.assertIn('primaryTabs.chunked(2)',bar)",
        "self.assertIn('SpectrumGlyphButton(tab.symbol(), tab.label()',bar)\n        self.assertIn('Modifier.size(56.dp)',bar)")
    put(path,value)

    # Exercise menu mapping and ensure icon-only entries really are distinguishable.
    path='app/src/test/java/ru/omnicio/app/ui/NavigationCatalogueTest.kt'
    value=get(path)
    last=value.rfind('}')
    value=value[:last]+'''    @org.junit.Test fun everyMenuDestinationHasItsOwnIcon() {
        val icons = analystMenuDestinations.map { it.symbol.asset }
        org.junit.Assert.assertEquals(icons.size, icons.toSet().size)
        org.junit.Assert.assertTrue(analystMenuDestinations.all { it.title.isNotBlank() })
    }
'''+value[last:]
    put(path,value)
