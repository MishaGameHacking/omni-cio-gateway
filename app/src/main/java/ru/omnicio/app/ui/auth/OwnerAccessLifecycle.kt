package ru.omnicio.app.ui.auth

import androidx.compose.runtime.*
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.activity.ComponentActivity
import androidx.activity.compose.LocalActivity

internal data class OwnerAccessLifecycle(val gate: OwnerAccessGate, val foreground: Boolean)

/** Invalidation is synchronous with ON_STOP, before any queued completion can publish access. */
@Composable
internal fun rememberOwnerAccessLifecycle(onBackground: () -> Unit = {}): OwnerAccessLifecycle {
    val lifecycle = (LocalActivity.current as? ComponentActivity)?.lifecycle
    val currentBackground by rememberUpdatedState(onBackground)
    // Begin locked. ComponentActivity's LifecycleRegistry brings a newly added
    // observer up to its current state, replaying ON_START when already started.
    val gate = remember(lifecycle) { OwnerAccessGate(false) }
    var foreground by remember(lifecycle) { mutableStateOf(false) }
    DisposableEffect(lifecycle, gate) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> { gate.foreground(); foreground = true }
                Lifecycle.Event.ON_STOP -> {
                    gate.background()
                    foreground = false
                    currentBackground()
                }
                else -> Unit
            }
        }
        lifecycle?.addObserver(observer)
        onDispose {
            gate.background()
            lifecycle?.removeObserver(observer)
        }
    }
    return OwnerAccessLifecycle(gate, foreground)
}
