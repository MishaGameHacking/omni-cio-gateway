package ru.omnicio.app.ui.spectrum

import android.animation.ValueAnimator
import androidx.activity.ComponentActivity
import androidx.activity.compose.LocalActivity
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.RoundRect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.graphics.graphicsLayer
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver

/** Decorative native artwork; the containing control supplies its accessible name. */
enum class SpectrumSymbol {
    Home, Portfolio, Market, Ideas, Pulse, Messages, Profile, Risk, Allocation,
    Update, Sources, Analyst, Education, Robot, Bell, Target, Settings,
}

@Composable
fun SpectrumIcon(symbol: SpectrumSymbol, modifier: Modifier = Modifier, selected: Boolean = false,
    tile: Boolean = true, motionAllowed: Boolean = false) {
    val lifecycle = (LocalActivity.current as? ComponentActivity)?.lifecycle
    var active by remember(lifecycle) { mutableStateOf(lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) ?: false) }
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, _ -> active = lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) ?: false }
        lifecycle?.addObserver(observer)
        onDispose { lifecycle?.removeObserver(observer) }
    }
    val progress = remember { Animatable(0f) }
    LaunchedEffect(symbol, selected, active, motionAllowed) {
        progress.snapTo(0f)
        if (selected && active && motionAllowed && ValueAnimator.areAnimatorsEnabled()) {
            progress.animateTo(1f, tween(150))
            progress.animateTo(0f, tween(300))
        }
    }
    val animated = modifier.graphicsLayer { translationY = -2f * progress.value }
    when (symbol) {
        SpectrumSymbol.Analyst -> SpectrumBrain(animated)
        SpectrumSymbol.Robot -> SpectrumRobot(animated)
        else -> SpectrumGlyph(symbol, animated, selected, tile)
    }
}

@Composable
private fun SpectrumGlyph(symbol: SpectrumSymbol, modifier: Modifier, selected: Boolean, tile: Boolean) {
    val palette = LocalSpectrumPalette.current
    val muted = MaterialTheme.colorScheme.onSurfaceVariant
    val accent = when (symbol) {
        SpectrumSymbol.Risk -> palette.emerald
        SpectrumSymbol.Target -> palette.rose
        SpectrumSymbol.Ideas, SpectrumSymbol.Settings -> palette.violet
        SpectrumSymbol.Education, SpectrumSymbol.Update -> palette.blue
        else -> palette.cyan
    }
    val geometry = remember(symbol) { glyphGeometry(symbol) }
    Canvas(modifier) {
        if (size.minDimension <= 0f) return@Canvas
        val factor = size.minDimension / 128f
        withTransform({ translate((size.width - size.minDimension) / 2f, (size.height - size.minDimension) / 2f); scale(factor, factor, Offset.Zero) }) {
            if (tile) {
                drawRoundRect(Brush.linearGradient(listOf(accent.copy(alpha = .22f), palette.cardStrong, palette.card)),
                    Offset(7f, 7f), Size(114f, 114f), CornerRadius(28f))
                drawRoundRect(accent.copy(alpha = .35f), Offset(7f, 7f), Size(114f, 114f), CornerRadius(28f), style = Stroke(1.2f))
            }
            val vivid = selected || tile
            val fill = Brush.linearGradient(listOf(accent.copy(alpha = if (vivid) .95f else .13f),
                (if (vivid) palette.blue else muted).copy(alpha = if (vivid) .45f else .07f)), Offset(35f, 25f), Offset(104f, 106f))
            drawPath(geometry.body, fill)
            if (vivid) drawPath(geometry.body, accent.copy(alpha = .13f), style = Stroke(13f, cap = StrokeCap.Round, join = StrokeJoin.Round))
            val ink = if (vivid) accent else muted
            drawPath(geometry.body, ink, style = Stroke(3f, cap = StrokeCap.Round, join = StrokeJoin.Round))
            drawPath(geometry.detail, if (vivid) Color(0xFFE0FAFF) else muted,
                style = Stroke(3.4f, cap = StrokeCap.Round, join = StrokeJoin.Round))
        }
    }
}

private data class GlyphGeometry(val body: Path, val detail: Path = Path())
private fun glyphGeometry(symbol: SpectrumSymbol): GlyphGeometry = when (symbol) {
    SpectrumSymbol.Home -> homeGlyph()
    SpectrumSymbol.Portfolio -> portfolioGlyph()
    SpectrumSymbol.Market, SpectrumSymbol.Pulse -> marketGlyph()
    SpectrumSymbol.Ideas -> diamondGlyph()
    SpectrumSymbol.Messages -> messagesGlyph()
    SpectrumSymbol.Profile -> profileGlyph()
    SpectrumSymbol.Risk -> riskGlyph()
    SpectrumSymbol.Allocation -> allocationGlyph()
    SpectrumSymbol.Update -> updateGlyph()
    SpectrumSymbol.Sources, SpectrumSymbol.Education -> bookGlyph()
    SpectrumSymbol.Bell -> bellGlyph()
    SpectrumSymbol.Target -> targetGlyph()
    SpectrumSymbol.Settings -> settingsGlyph()
    SpectrumSymbol.Analyst, SpectrumSymbol.Robot -> diamondGlyph()
}

private fun homeGlyph() = GlyphGeometry(Path().apply {
    moveTo(25f, 59f); lineTo(64f, 25f); lineTo(103f, 59f); lineTo(94f, 59f)
    lineTo(94f, 100f); lineTo(73f, 100f); lineTo(73f, 76f); lineTo(55f, 76f)
    lineTo(55f, 100f); lineTo(34f, 100f); lineTo(34f, 59f); close()
}, Path().apply { moveTo(35f, 58f); lineTo(64f, 33f); lineTo(92f, 58f) })

private fun portfolioGlyph() = GlyphGeometry(Path().apply {
    addRoundRect(RoundRect(Rect(27f, 43f, 101f, 97f), CornerRadius(13f)))
    moveTo(48f, 43f); lineTo(48f, 30f); lineTo(80f, 30f); lineTo(80f, 43f); close()
}, Path().apply {
    moveTo(29f, 62f); quadraticTo(64f, 83f, 99f, 62f)
    moveTo(56f, 69f); lineTo(56f, 80f); lineTo(72f, 80f); lineTo(72f, 69f)
})

private fun marketGlyph() = GlyphGeometry(Path().apply {
    addRoundRect(RoundRect(Rect(28f, 77f, 43f, 102f), CornerRadius(4f)))
    addRoundRect(RoundRect(Rect(56f, 57f, 71f, 102f), CornerRadius(4f)))
    addRoundRect(RoundRect(Rect(84f, 34f, 99f, 102f), CornerRadius(4f)))
}, Path().apply { moveTo(29f, 58f); lineTo(56f, 37f); lineTo(68f, 44f); lineTo(94f, 20f); moveTo(78f, 21f); lineTo(96f, 20f); lineTo(96f, 37f) })

private fun diamondGlyph() = GlyphGeometry(Path().apply {
    moveTo(64f, 20f); lineTo(97f, 58f); lineTo(64f, 106f); lineTo(31f, 58f); close()
}, Path().apply {
    moveTo(31f, 58f); lineTo(97f, 58f); moveTo(64f, 20f); lineTo(51f, 58f); lineTo(64f, 106f)
    moveTo(64f, 20f); lineTo(77f, 58f); lineTo(64f, 106f)
})

private fun messagesGlyph() = GlyphGeometry(Path().apply {
    moveTo(38f, 29f); lineTo(91f, 29f); quadraticTo(102f, 29f, 102f, 42f)
    lineTo(102f, 80f); quadraticTo(102f, 92f, 89f, 92f); lineTo(58f, 92f)
    lineTo(32f, 107f); lineTo(32f, 92f); quadraticTo(24f, 88f, 24f, 80f)
    lineTo(24f, 42f); quadraticTo(24f, 29f, 38f, 29f); close()
}, Path().apply { moveTo(41f, 51f); lineTo(83f, 51f); moveTo(41f, 66f); lineTo(73f, 66f) })

private fun profileGlyph() = GlyphGeometry(Path().apply {
    addOval(Rect(46f, 25f, 82f, 62f)); moveTo(28f, 101f)
    cubicTo(28f, 59f, 100f, 59f, 100f, 101f); close()
}, Path().apply { moveTo(44f, 85f); quadraticTo(64f, 96f, 84f, 85f) })

private fun riskGlyph() = GlyphGeometry(Path().apply {
    moveTo(64f, 21f); lineTo(99f, 35f); lineTo(97f, 67f)
    quadraticTo(94f, 93f, 64f, 108f); quadraticTo(34f, 93f, 31f, 67f)
    lineTo(29f, 35f); close()
}, Path().apply { moveTo(46f, 61f); lineTo(60f, 76f); lineTo(84f, 47f) })

private fun allocationGlyph() = GlyphGeometry(Path().apply {
    moveTo(59f, 27f); arcTo(Rect(22f, 27f, 96f, 101f), 270f, -270f, false)
    lineTo(59f, 64f); close(); moveTo(72f, 23f); quadraticTo(102f, 27f, 106f, 56f)
    lineTo(72f, 56f); close()
})

private fun updateGlyph() = GlyphGeometry(Path().apply {
    moveTo(55f, 24f); lineTo(73f, 24f); lineTo(73f, 63f); lineTo(92f, 63f)
    lineTo(64f, 89f); lineTo(36f, 63f); lineTo(55f, 63f); close()
}, Path().apply { moveTo(29f, 86f); lineTo(29f, 104f); lineTo(99f, 104f); lineTo(99f, 86f) })

private fun bookGlyph() = GlyphGeometry(Path().apply {
    moveTo(64f, 37f); quadraticTo(43f, 24f, 24f, 33f); lineTo(24f, 94f)
    quadraticTo(45f, 87f, 64f, 102f); quadraticTo(83f, 87f, 104f, 94f)
    lineTo(104f, 33f); quadraticTo(85f, 24f, 64f, 37f); close()
}, Path().apply {
    moveTo(64f, 38f); lineTo(64f, 101f); moveTo(36f, 48f); lineTo(51f, 51f)
    moveTo(36f, 61f); lineTo(51f, 64f); moveTo(77f, 51f); lineTo(92f, 48f)
    moveTo(77f, 64f); lineTo(92f, 61f)
})

private fun bellGlyph() = GlyphGeometry(Path().apply {
    moveTo(31f, 91f); quadraticTo(41f, 83f, 41f, 58f); cubicTo(41f, 25f, 87f, 25f, 87f, 58f)
    quadraticTo(87f, 83f, 97f, 91f); close()
}, Path().apply { moveTo(54f, 101f); quadraticTo(64f, 114f, 74f, 101f); moveTo(64f, 27f); lineTo(64f, 21f) })

private fun targetGlyph() = GlyphGeometry(Path().apply { addOval(Rect(25f, 29f, 99f, 103f)) }, Path().apply {
    addOval(Rect(42f, 46f, 82f, 86f)); moveTo(62f, 66f); lineTo(105f, 23f)
    moveTo(86f, 24f); lineTo(86f, 42f); lineTo(104f, 42f)
})

private fun settingsGlyph() = GlyphGeometry(Path().apply {
    moveTo(46f, 25f); lineTo(82f, 25f); lineTo(104f, 64f); lineTo(82f, 103f)
    lineTo(46f, 103f); lineTo(24f, 64f); close()
}, Path().apply { addOval(Rect(47f, 47f, 81f, 81f)) })
