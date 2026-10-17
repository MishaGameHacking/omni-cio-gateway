package ru.omnicio.app.ui.spatial

import android.view.TextureView
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.boundsInWindow
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette

internal val LocalSpatialOwner = staticCompositionLocalOf<SpatialOwner?> { null }
internal val LocalSpatialWindow = staticCompositionLocalOf<SpatialRenderWindow?> { null }

/**
 * Put inside the palette provider, outside screen navigation. Native text is drawn
 * above one transparent Filament texture. Assets are loaded after the first frame
 * so account values, controls and accessibility do not wait for decoration.
 */
@Composable
fun SpatialSceneRoot(
    modifier: Modifier = Modifier,
    motion: SpatialMotion = SpatialMotion.Live,
    tactile: Boolean = true,
    opaque: Boolean = false,
    navigationProgress: Float = 0f,
    content: @Composable BoxScope.() -> Unit,
) {
    val context = LocalContext.current.applicationContext
    val inspecting = LocalInspectionMode.current
    val palette = LocalSpectrumPalette.current
    var owner by remember(context) { mutableStateOf<SpatialOwner?>(null) }
    LaunchedEffect(context, inspecting) {
        if (!inspecting) {
            withFrameNanos { }
            owner = SpatialOwner(context)
        }
    }
    val active = owner
    DisposableEffect(active) { onDispose { active?.close() } }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    DisposableEffect(active, lifecycle) {
        val observer = LifecycleEventObserver { _, _ ->
            active?.foreground = lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)
        }
        active?.foreground = lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)
        lifecycle.addObserver(observer)
        onDispose { lifecycle.removeObserver(observer) }
    }
    SideEffect {
        active?.configure(palette, motion, tactile, opaque)
        active?.updateNavigationProgress(navigationProgress)
    }
    CompositionLocalProvider(LocalSpatialOwner provides active) {
        SpatialWindow(modifier.graphicsLayer {
            val progress = if (active?.effectiveMotion == SpatialMotion.Off) 0f
                else navigationProgress.takeIf { it.isFinite() }?.coerceIn(0f, 1f) ?: 0f
            translationX = size.width * .08f * progress
            alpha = 1f - .15f * progress
        }, content)
    }
}

/** A Dialog needs its own surface, but shares the Activity's engine and model pool. */
@Composable
fun SpatialWindow(modifier: Modifier = Modifier, content: @Composable BoxScope.() -> Unit) {
    val owner = LocalSpatialOwner.current
    val window = remember(owner) { owner?.createWindow() }
    val density = LocalDensity.current.density
    val palette = LocalSpectrumPalette.current
    DisposableEffect(owner, window) {
        onDispose { if (window != null) owner?.releaseWindow(window) }
    }
    Box(modifier.graphicsLayer {
        val progress = window?.localBackProgress ?: 0f
        translationX = size.width * .08f * progress
        alpha = 1f - .15f * progress
    }.background(palette.backgroundTop)) {
        if (window != null) {
            AndroidView(
                factory = { context -> TextureView(context).also(window::attach) },
                modifier = Modifier.matchParentSize().onGloballyPositioned {
                    window.origin = it.localToWindow(Offset.Zero)
                    window.density = density
                    owner?.invalidate()
                },
                update = { window.density = density },
            )
        }
        CompositionLocalProvider(LocalSpatialWindow provides window) { content() }
    }
}

@Composable
fun spatialDiagnostics(): SpatialDiagnostics =
    LocalSpatialOwner.current?.diagnostics ?: SpatialDiagnostics()

internal class SpatialPlacement(var bounds: Rect? = null, var clip: Rect? = null)

/** Registration only; every visible component is rendered by its window's scene. */
@Composable
internal fun SpatialCanvas(primitives: List<SpatialPrimitive>, modifier: Modifier = Modifier) {
    val owner = LocalSpatialOwner.current
    val window = LocalSpatialWindow.current
    val id = remember(owner, window) { owner?.id() ?: 0L }
    val placement = remember(window) { SpatialPlacement() }
    val latest by rememberUpdatedState(primitives)
    fun publish() {
        val bounds = placement.bounds ?: return
        val clip = placement.clip ?: return
        window?.put(SpatialSlot(id, bounds, clip, latest))
    }
    DisposableEffect(window, id) { onDispose { window?.remove(id) } }
    SideEffect { publish() }
    Box(modifier.onGloballyPositioned { coordinates ->
        val topLeft = coordinates.localToWindow(Offset.Zero)
        placement.bounds = Rect(topLeft.x, topLeft.y,
            topLeft.x + coordinates.size.width, topLeft.y + coordinates.size.height)
        // boundsInWindow intersects ancestor clips; original bounds preserve the
        // mesh's geometry when a lazy row is partly outside its scroll viewport.
        placement.clip = coordinates.boundsInWindow()
        publish()
    })
}
