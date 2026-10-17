package ru.omnicio.app.ui.spectrum

import android.animation.ValueAnimator
import androidx.activity.ComponentActivity
import androidx.activity.compose.LocalActivity
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.AnimationVector1D
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.tween
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver

/**
 * A draw-phase clock for native Spectrum visuals.
 *
 * The loop exists only while its composable is on screen, the Activity is started,
 * the user has allowed Spectrum motion, and Android animators are enabled. Callers
 * read [Animatable.value] from Canvas or graphicsLayer so a frame does not recompose
 * the surrounding screen.
 */
@Composable
internal fun rememberSpectrumLivePhase(
    motionAllowed: Boolean,
    durationMillis: Int,
): Animatable<Float, AnimationVector1D> {
    require(durationMillis > 0)
    val active = rememberSpectrumActive()

    val phase = remember { Animatable(0f) }
    val enabled = motionAllowed && active && ValueAnimator.areAnimatorsEnabled()
    LaunchedEffect(enabled, durationMillis) {
        phase.snapTo(0f)
        if (enabled) {
            repeat(2) {
                phase.animateTo(
                    targetValue = 1f,
                    animationSpec = tween(durationMillis = durationMillis, easing = LinearEasing),
                )
                phase.snapTo(0f)
            }
        }
    }
    return phase
}


@Composable
private fun rememberSpectrumActive(): Boolean {
    val lifecycle = (LocalActivity.current as? ComponentActivity)?.lifecycle
    var active by remember(lifecycle) {
        mutableStateOf(lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) ?: false)
    }
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, _ ->
            active = lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) ?: false
        }
        lifecycle?.addObserver(observer)
        onDispose { lifecycle?.removeObserver(observer) }
    }

    return active
}
