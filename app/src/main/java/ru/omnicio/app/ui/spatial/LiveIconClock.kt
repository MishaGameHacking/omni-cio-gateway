package ru.omnicio.app.ui.spatial

import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.boundsInWindow
import androidx.compose.ui.layout.onGloballyPositioned
import kotlinx.coroutines.isActive

/** One frame source per visible scene, independent of portfolio or network state. */
internal class LiveIconClock {
    val phase = mutableFloatStateOf(0f)
    private val owners = mutableStateMapOf<Any, Unit>()
    val activeCount: Int get() = owners.size
    fun attach(owner: Any) { owners[owner] = Unit }
    fun detach(owner: Any) { owners.remove(owner) }
}

internal val LocalLiveIconClock = staticCompositionLocalOf<LiveIconClock?> { null }

internal fun decorativeLoopPhase(elapsedNanos: Long): Float =
    (elapsedNanos.coerceAtLeast(0L) % 4_800_000_000L).toFloat() / 4_800_000_000f

@Composable
internal fun rememberLiveIconClock(motion: SpatialMotion): LiveIconClock {
    val clock = remember { LiveIconClock() }
    val running = motion == SpatialMotion.Live && clock.activeCount > 0
    LaunchedEffect(running) {
        clock.phase.floatValue = 0f
        if (running) {
            var origin: Long? = null
            while (isActive) withFrameNanos { now ->
                val start = origin ?: now.also { origin = it }
                clock.phase.floatValue = decorativeLoopPhase(now - start)
            }
        }
    }
    return clock
}

internal data class LiveDecoration(val modifier: Modifier, val phase: State<Float>)

/** Clipped bounds become empty when a lazy/scrolling item leaves its viewport. */
@Composable
internal fun rememberLiveDecoration(enabled: Boolean): LiveDecoration {
    val clock = LocalLiveIconClock.current
    val motion = LocalFlatMotion.current
    val owner = remember { Any() }
    var visible by remember { mutableStateOf(false) }
    val active = enabled && visible && motion == SpatialMotion.Live && clock != null
    DisposableEffect(clock, active) {
        if (active) clock?.attach(owner)
        onDispose { clock?.detach(owner) }
    }
    val still = rememberUpdatedState(0f)
    return LiveDecoration(Modifier.onGloballyPositioned {
        val clipped = it.boundsInWindow()
        visible = clipped.width > 0f && clipped.height > 0f
    }, if (active) clock!!.phase else still)
}
