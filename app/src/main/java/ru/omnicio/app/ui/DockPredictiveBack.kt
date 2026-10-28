package ru.omnicio.app.ui

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
