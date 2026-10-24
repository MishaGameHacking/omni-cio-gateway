package ru.omnicio.app.ui.spatial

import android.view.HapticFeedbackConstants
import androidx.activity.compose.PredictiveBackHandler
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.platform.LocalView
import kotlinx.coroutines.flow.collect

/**
 * Local destinations use their current window's existing scene. A cancelled
 * gesture never commits navigation and both cancellation and commit reset depth.
 * Native content follows the gesture; cancellation restores the original screen.
 */
@Composable
fun SpatialBackHandler(enabled: Boolean = true, onBack: () -> Unit) {
    val back = LocalFlatBack.current
    val action by rememberUpdatedState(onBack)
    DisposableEffect(back) { onDispose { back?.value = 0f } }
    PredictiveBackHandler(enabled) { events ->
        try {
            events.collect { back?.value = it.progress.takeIf(Float::isFinite)?.coerceIn(0f, 1f) ?: 0f }
            action()
        } finally {
            back?.value = 0f
        }
    }
}

/** One user action, one native pulse. Android's own haptic setting is respected. */
enum class SpatialHaptic { Action, Selection, Confirmed, Rejected }

@Composable
fun rememberSpatialHapticFeedback(): (SpatialHaptic) -> Unit {
    val view = LocalView.current
    val tactile = LocalFlatTactile.current
    return remember(view, tactile) {
        { kind ->
            if (tactile) view.performHapticFeedback(when (kind) {
                SpatialHaptic.Action -> HapticFeedbackConstants.VIRTUAL_KEY
                SpatialHaptic.Selection -> HapticFeedbackConstants.SEGMENT_TICK
                SpatialHaptic.Confirmed -> HapticFeedbackConstants.CONFIRM
                SpatialHaptic.Rejected -> HapticFeedbackConstants.REJECT
            })
        }
    }
}

@Composable
fun rememberSpatialHapticClick(onClick: () -> Unit): () -> Unit =
    rememberSpatialHapticClick(SpatialHaptic.Action, onClick)

@Composable
fun rememberSpatialHapticClick(kind: SpatialHaptic, onClick: () -> Unit): () -> Unit {
    val feedback = rememberSpatialHapticFeedback()
    val action by rememberUpdatedState(onClick)
    return remember(feedback, kind) {
        {
            feedback(kind)
            action()
        }
    }
}
