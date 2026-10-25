package ru.omnicio.app.ui.spatial

import android.animation.ValueAnimator
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.PowerManager
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.boundsInWindow
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import kotlinx.coroutines.delay
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette

internal class FlatDrawStats { var operations: Long = 0 }
internal val LocalFlatDrawStats = staticCompositionLocalOf<FlatDrawStats?> { null }
internal val LocalFlatMotion = staticCompositionLocalOf { SpatialMotion.Off }
internal val LocalFlatContrast = staticCompositionLocalOf { false }
internal val LocalFlatTactile = staticCompositionLocalOf { true }
internal val LocalFlatBack = staticCompositionLocalOf<MutableState<Float>?> { null }

/** Native Compose throughout: no texture, renderer thread, model upload or hidden 3D engine. */
@Composable
fun SpatialSceneRoot(
    modifier: Modifier = Modifier,
    motion: SpatialMotion = SpatialMotion.Live,
    tactile: Boolean = true,
    opaque: Boolean = false,
    navigationProgress: Float = 0f,
    content: @Composable BoxScope.() -> Unit,
) {
    if (LocalInspectionMode.current) {
        // The same Compose drawing path, with no device power/thermal observers.
        CompositionLocalProvider(
            LocalFlatContrast provides opaque,
            LocalFlatMotion provides SpatialMotion.Off,
            LocalFlatTactile provides false,
        ) { SpatialWindow(modifier, content) }
        return
    }
    val counters = remember { FlatDrawStats() }
    val context = LocalContext.current.applicationContext
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    val power = remember(context) { context.getSystemService(PowerManager::class.java) }
    var foreground by remember { mutableStateOf(false) }
    var systemMotion by remember { mutableStateOf(ValueAnimator.areAnimatorsEnabled()) }
    var severeThermal by remember { mutableStateOf(power.currentThermalStatus >= PowerManager.THERMAL_STATUS_SEVERE) }
    var constrained by remember { mutableStateOf(power.isPowerSaveMode ||
        power.currentThermalStatus >= PowerManager.THERMAL_STATUS_MODERATE) }
    DisposableEffect(context, lifecycle, power) {
        fun refresh() {
            foreground = lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)
            systemMotion = ValueAnimator.areAnimatorsEnabled()
            severeThermal = power.currentThermalStatus >= PowerManager.THERMAL_STATUS_SEVERE
            constrained = power.isPowerSaveMode ||
                power.currentThermalStatus >= PowerManager.THERMAL_STATUS_MODERATE
        }
        val observer = LifecycleEventObserver { _, _ -> refresh() }
        // Settings notifications can arrive before ValueAnimator updates its cached
        // scale. Listen to the animation policy itself, including re-enabling it.
        val durationScaleListener = ValueAnimator.DurationScaleChangeListener { scale ->
            systemMotion = scale > 0f
        }
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context?, intent: Intent?) { refresh() }
        }
        val thermal = PowerManager.OnThermalStatusChangedListener { refresh() }
        lifecycle.addObserver(observer)
        ValueAnimator.registerDurationScaleChangeListener(durationScaleListener)
        context.registerReceiver(receiver, IntentFilter(PowerManager.ACTION_POWER_SAVE_MODE_CHANGED),
            Context.RECEIVER_NOT_EXPORTED)
        power.addThermalStatusListener(context.mainExecutor, thermal)
        refresh()
        onDispose {
            lifecycle.removeObserver(observer)
            ValueAnimator.unregisterDurationScaleChangeListener(durationScaleListener)
            context.unregisterReceiver(receiver)
            power.removeThermalStatusListener(thermal)
        }
    }
    val effective = flatMotionPolicy(motion, foreground, systemMotion, constrained, severeThermal)
    CompositionLocalProvider(LocalFlatContrast provides opaque, LocalFlatDrawStats provides counters, LocalFlatMotion provides effective, LocalFlatTactile provides tactile) {
        SpatialWindow(modifier.graphicsLayer {
            val progress = if (effective == SpatialMotion.Off) 0f
                else navigationProgress.takeIf { it.isFinite() }?.coerceIn(0f, 1f) ?: 0f
            translationX = size.width * .06f * progress
            alpha = 1f - .10f * progress
        }, content)
    }
}

@Composable
fun SpatialWindow(modifier: Modifier = Modifier, content: @Composable BoxScope.() -> Unit) {
    val back = remember { mutableStateOf(0f) }
    val motion = LocalFlatMotion.current
    Box(modifier.graphicsLayer {
        val progress = if (motion == SpatialMotion.Off) 0f else back.value
        translationX = size.width * .06f * progress
        alpha = 1f - .10f * progress
    }.background(LocalSpectrumPalette.current.backgroundTop)) {
        CompositionLocalProvider(LocalFlatBack provides back) { content() }
    }
}

/** The 2D edition never allocates a Filament engine. These are renderer counters, not FPS claims. */
@Composable
fun spatialDiagnostics(): SpatialDiagnostics = SpatialDiagnostics()

/** Animated decoration is drawn locally. Financial geometry never participates in motion. */
@Composable
internal fun SpatialCanvas(primitives: List<SpatialPrimitive>, modifier: Modifier = Modifier) {
    val counters = LocalFlatDrawStats.current
    val motion = LocalFlatMotion.current
    var visible by remember { mutableStateOf(false) }
    val phase = remember { Animatable(0f) }
    val states = primitives.map { it.asset to it.state }
    val canMove = visible && motion != SpatialMotion.Off && primitives.any { it.motionAllowed }
    val loading = primitives.any { it.motionAllowed && it.state == SpatialState.Loading }
    val looping = primitives.any { it.motionAllowed &&
        (it.state == SpatialState.Loading || (it.asset as? SpatialAsset.Catalogue)?.name in setOf("brand", "orbit")) }
    LaunchedEffect(states, canMove, motion) {
        phase.snapTo(0f)
        if (canMove) {
            do {
                phase.animateTo(1f, tween(if (motion == SpatialMotion.Live) 1400 else 320,
                    easing = if (loading) LinearEasing else FastOutSlowInEasing))
                phase.snapTo(0f)
                if (looping && !loading && motion == SpatialMotion.Live) delay(2200)
            } while (looping && motion == SpatialMotion.Live)
        }
    }
    Canvas(modifier.onGloballyPositioned {
        val bounds = it.boundsInWindow()
        visible = bounds.width > 0f && bounds.height > 0f
    }) {
        // Read animation in the draw phase; editor and screen layouts do not recompose per frame.
        val progress = if (canMove) phase.value else 0f
        if (counters != null) counters.operations++
        primitives.forEach { drawFlatPrimitive(it, if (it.motionAllowed) progress else 0f) }
    }
}
