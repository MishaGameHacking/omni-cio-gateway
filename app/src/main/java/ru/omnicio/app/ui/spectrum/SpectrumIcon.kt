package ru.omnicio.app.ui.spectrum

import android.animation.ValueAnimator
import androidx.activity.ComponentActivity
import androidx.activity.compose.LocalActivity
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.RoundRect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.graphics.luminance
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver

/** RGB identifies an interface action, never gain/loss, rating or AI certainty. */
enum class SpectrumSymbol { Portfolio, Ideas, Pulse, Messages, Profile, Risk, Allocation, Update, Sources, Analyst }

/** A decorative icon. The surrounding button MUST provide a visible text label.
 * One finite animation on selection; no looping GIF decoder in a long list.
 * Caller passes its persisted reduce-motion preference via motionAllowed.
 */
@Composable
fun SpectrumIcon(
    symbol: SpectrumSymbol,
    modifier: Modifier = Modifier,
    selected: Boolean = false,
    tile: Boolean = true,
    motionAllowed: Boolean = false,
) {
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
    val motion = remember { Animatable(0f) }
    LaunchedEffect(symbol, selected, active, motionAllowed) {
        motion.snapTo(0f)
        if (selected && active && motionAllowed && ValueAnimator.areAnimatorsEnabled()) {
            motion.animateTo(1f, tween(180))
            motion.animateTo(0f, tween(420))
        }
    }
    val dark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val colors = if (dark) listOf(Color(0xFF57DDE6), Color(0xFF76A9FA), Color(0xFFAF99FF), Color(0xFFF190C5))
        else listOf(Color(0xFF006C78), Color(0xFF326FC8), Color(0xFF6E4EAD), Color(0xFFA6367A))
    val muted = MaterialTheme.colorScheme.onSurfaceVariant
    val shape = remember(symbol) { spectrumPath(symbol) }
    Canvas(modifier) {
        val unit = size.minDimension / 128f
        withTransform({
            translate((size.width - size.minDimension) / 2, (size.height - size.minDimension) / 2)
            scale(unit, unit, Offset.Zero)
            translate(top = if (active && motionAllowed) -2f * motion.value else 0f)
        }) {
            if (tile) {
                drawRoundRect(Brush.linearGradient(listOf(colors[1].copy(alpha=.13f), colors[2].copy(alpha=.03f)),
                    start=Offset.Zero, end=Offset(128f,128f)),
                    topLeft=Offset(12f,12f), size=Size(104f,104f), cornerRadius=CornerRadius(30f,30f))
            }
            val brush: Brush = if (selected || tile) Brush.linearGradient(colors,
                start=Offset(24f,24f), end=Offset(101f,106f)) else SolidColor(muted)
            drawPath(shape, brush=brush, style=Stroke(width=6f, cap=StrokeCap.Round, join=StrokeJoin.Round))
        }
    }
}

private fun spectrumPath(symbol: SpectrumSymbol): Path = Path().apply {
    when (symbol) {
        SpectrumSymbol.Portfolio -> {
            addRoundRect(RoundRect(Rect(30f,43f,98f,92f),CornerRadius(13f,13f)))
            moveTo(49f,43f); lineTo(49f,30f); lineTo(79f,30f); lineTo(79f,43f)
            moveTo(31f,62f); quadraticTo(64f,80f,97f,62f)
            moveTo(59f,65f); lineTo(59f,75f); lineTo(69f,75f); lineTo(69f,65f)
        }
        SpectrumSymbol.Ideas -> {
            addOval(Rect(31f,30f,83f,82f)); moveTo(77f,76f); lineTo(97f,96f)
            moveTo(44f,56f); lineTo(70f,56f); moveTo(57f,43f); lineTo(57f,69f)
        }
        SpectrumSymbol.Pulse -> {
            addOval(Rect(29f,29f,99f,99f)); moveTo(25f,67f); lineTo(47f,67f)
            lineTo(57f,43f); lineTo(71f,88f); lineTo(80f,67f); lineTo(103f,67f)
        }
        SpectrumSymbol.Messages -> {
            moveTo(38f,31f); lineTo(91f,31f); quadraticTo(101f,31f,101f,43f)
            lineTo(101f,81f); quadraticTo(101f,92f,89f,92f); lineTo(56f,92f)
            lineTo(35f,105f); lineTo(35f,92f); quadraticTo(25f,92f,25f,82f)
            lineTo(25f,44f); quadraticTo(25f,31f,38f,31f); close()
            moveTo(43f,51f); lineTo(83f,51f); moveTo(43f,65f); lineTo(74f,65f)
        }
        SpectrumSymbol.Profile -> {
            addOval(Rect(47f,28f,81f,62f)); moveTo(32f,97f)
            cubicTo(32f,56f,96f,56f,96f,97f); close()
        }
        SpectrumSymbol.Risk -> {
            moveTo(64f,24f); lineTo(96f,37f); lineTo(96f,65f)
            quadraticTo(95f,89f,64f,105f); quadraticTo(32f,89f,32f,65f)
            lineTo(32f,37f); close(); moveTo(47f,62f); lineTo(59f,75f); lineTo(83f,47f)
        }
        SpectrumSymbol.Allocation -> {
            moveTo(61f,27f); arcTo(Rect(24f,27f,98f,101f),270f,-270f,false)
            lineTo(61f,64f); close(); moveTo(73f,25f)
            quadraticTo(99f,28f,103f,55f); lineTo(73f,55f); close()
        }
        SpectrumSymbol.Update -> {
            moveTo(64f,25f); lineTo(64f,78f); moveTo(44f,58f); lineTo(64f,79f); lineTo(84f,58f)
            moveTo(31f,79f); lineTo(31f,100f); lineTo(97f,100f); lineTo(97f,79f)
        }
        SpectrumSymbol.Sources -> {
            moveTo(35f,24f); lineTo(80f,24f); lineTo(98f,42f); lineTo(98f,103f)
            lineTo(26f,103f); lineTo(26f,24f); close(); moveTo(79f,24f); lineTo(79f,44f); lineTo(98f,44f)
            moveTo(43f,59f); lineTo(79f,59f); moveTo(43f,73f); lineTo(72f,73f)
            moveTo(43f,87f); lineTo(61f,87f)
        }
        SpectrumSymbol.Analyst -> {
            addOval(Rect(48f,48f,80f,80f))
            moveTo(24f,64f); cubicTo(24f,30f,104f,30f,104f,64f)
            cubicTo(104f,98f,24f,98f,24f,64f); close()
            moveTo(64f,23f); cubicTo(29f,23f,29f,105f,64f,105f)
            cubicTo(99f,105f,99f,23f,64f,23f); close()
        }
    }
}
