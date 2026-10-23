package ru.omnicio.app.ui.portfolio

import androidx.compose.animation.AnimatedVisibilityScope
import androidx.compose.animation.ExperimentalSharedTransitionApi
import androidx.compose.animation.SharedTransitionScope
import androidx.compose.animation.core.tween
import androidx.compose.runtime.Composable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Modifier
import ru.omnicio.app.data.portfolio.PortfolioPosition
import ru.omnicio.app.ui.spectrum.SpectrumSymbol
import ru.omnicio.app.ui.theme.LocalSpectrumMotionPreference
import ru.omnicio.app.ui.workspace.LocalWorkspacePreferences
import ru.omnicio.app.ui.workspace.MotionLevel

@OptIn(ExperimentalSharedTransitionApi::class)
internal data class InstrumentTransition(val shared: SharedTransitionScope, val visibility: AnimatedVisibilityScope)
internal val LocalInstrumentTransition = staticCompositionLocalOf<InstrumentTransition?> { null }

@OptIn(ExperimentalSharedTransitionApi::class)
@Composable
internal fun instrumentSharedModifier(key: String): Modifier {
    val context = LocalInstrumentTransition.current ?: return Modifier
    val duration = portfolioMotionDuration(320, 120)
    return with(context.shared) {
        Modifier.sharedElement(rememberSharedContentState("instrument:$key"), context.visibility,
            boundsTransform = { _, _ -> tween(duration) })
    }
}

@Composable
internal fun portfolioMotionDuration(live: Int, subdued: Int): Int =
    if (!android.animation.ValueAnimator.areAnimatorsEnabled()) 0 else when (LocalWorkspacePreferences.current.value.motion) {
        MotionLevel.LIVE -> live
        MotionLevel.SUBDUED -> subdued
        MotionLevel.OFF -> 0
    }

internal fun instrumentSymbol(position: PortfolioPosition): SpectrumSymbol = when (position.instrumentType) {
    "cash", "currency", "etf" -> SpectrumSymbol.Allocation
    "bond" -> SpectrumSymbol.Sources
    "share" -> SpectrumSymbol.Market
    else -> SpectrumSymbol.Portfolio
}
