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
 * Native text moves with the texture while the actual meshes also recede in Z.
 */
@Composable
fun SpatialBackHandler(enabled: Boolean = true, onBack: () -> Unit) {
    val window = LocalSpatialWindow.current
    val action by rememberUpdatedState(onBack)
    DisposableEffect(window) { onDispose { window?.updateLocalBackProgress(0f) } }
    PredictiveBackHandler(enabled) { events ->
        try {
            events.collect { window?.updateLocalBackProgress(it.progress) }
            action()
        } finally {
            window?.updateLocalBackProgress(0f)
        }
    }
}

/** One user action, one native pulse. Android's own haptic setting is respected. */
@Composable
fun rememberSpatialHapticClick(onClick: () -> Unit): () -> Unit {
    val view = LocalView.current
    val owner = LocalSpatialOwner.current
    val action by rememberUpdatedState(onClick)
    return remember(view, owner) {
        {
            if (owner?.tactile == true) view.performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
            action()
        }
    }
}
