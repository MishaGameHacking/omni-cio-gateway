package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.Canvas
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.sin

/** The nine live element families approved in the Analyst AI Spectrum reference. */
@Immutable
enum class SpectrumLiveFeature(
    val description: String,
    internal val durationMillis: Int,
) {
    Charts("Живые графики", 2_800),
    Indicators("Анимированные индикаторы", 3_200),
    Spatial("Двухмерные и пространственные элементы", 4_200),
    RgbEffects("RGB-эффекты иконок", 3_600),
    Assistant("Интерактивный ИИ-ассистент", 3_400),
    Notifications("Умные уведомления", 2_600),
    Recommendations("Персональные рекомендации", 3_000),
    RiskControl("Контроль рисков", 3_800),
    WorldMarkets("Анализ мировых рынков", 5_200),
}

/**
 * Resolution-independent, programmatic artwork. No bitmap, remote image, GIF,
 * WebView, or broker-owned graphic is used. Every family has its own motion
 * language instead of applying one generic spin to all icons.
 */
@Composable
fun SpectrumLiveFeatureIcon(
    feature: SpectrumLiveFeature,
    modifier: Modifier = Modifier,
    motionAllowed: Boolean = true,
) {
    val palette = LocalSpectrumPalette.current
    val dark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val phase = rememberSpectrumLivePhase(motionAllowed, feature.durationMillis)

    Canvas(
        modifier = modifier.semantics { contentDescription = feature.description },
    ) {
        if (size.minDimension <= 0f) return@Canvas
        val unit = size.minDimension / LIVE_ARTWORK_SIZE
        val left = (size.width - size.minDimension) / 2f
        val top = (size.height - size.minDimension) / 2f
        withTransform({
            translate(left, top)
            scale(unit, unit, Offset.Zero)
        }) {
            val t = phase.value
            drawLiveHalo(palette, dark, t)
            when (feature) {
                SpectrumLiveFeature.Charts -> drawLiveCharts(palette, t)
                SpectrumLiveFeature.Indicators -> drawLiveIndicator(palette, t)
                SpectrumLiveFeature.Spatial -> drawLiveSpatial(palette, t)
                SpectrumLiveFeature.RgbEffects -> drawLiveGem(palette, t)
                SpectrumLiveFeature.Assistant -> drawLiveAssistant(palette, t)
                SpectrumLiveFeature.Notifications -> drawLiveBell(palette, t)
                SpectrumLiveFeature.Recommendations -> drawLiveTarget(palette, t)
                SpectrumLiveFeature.RiskControl -> drawLiveShield(palette, t)
                SpectrumLiveFeature.WorldMarkets -> drawLiveGlobe(palette, t)
            }
        }
    }
}

private fun DrawScope.drawLiveHalo(palette: SpectrumPalette, dark: Boolean, t: Float) {
    val orbit = (2f * PI.toFloat() * t)
    val center = Offset(
        64f + cos(orbit) * 5f,
        64f + sin(orbit) * 4f,
    )
    drawCircle(
        brush = Brush.radialGradient(
            listOf(
                palette.cyan.copy(alpha = if (dark) 0.16f else 0.08f),
                palette.violet.copy(alpha = if (dark) 0.10f else 0.04f),
                Color.Transparent,
            ),
            center = center,
            radius = 61f,
        ),
        radius = 61f,
        center = center,
    )
}

private fun DrawScope.drawLiveCharts(palette: SpectrumPalette, t: Float) {
    val colors = listOf(palette.emerald, palette.cyan, palette.blue, palette.violet, palette.rose)
    repeat(5) { index ->
        val wave = (sin((t * 2f * PI + index * 0.82f).toDouble()).toFloat() + 1f) / 2f
        val height = 25f + index * 8f + wave * 15f
        drawRoundRect(
            brush = Brush.verticalGradient(listOf(colors[index], colors[index].copy(alpha = 0.35f))),
            topLeft = Offset(18f + index * 19f, 105f - height),
            size = Size(12f, height),
            cornerRadius = CornerRadius(5f, 5f),
        )
    }
    val line = Path().apply {
        moveTo(17f, 82f)
        repeat(6) { index ->
            val x = 17f + index * 18.5f
            val y = 70f - index * 6f + sin((t * 2f * PI + index).toDouble()).toFloat() * 5f
            lineTo(x, y)
        }
    }
    drawPath(line, palette.emerald, style = Stroke(3f, cap = StrokeCap.Round, join = StrokeJoin.Round))
    drawCircle(palette.emerald, 4f, Offset(109.5f, 40f + sin(t * 2f * PI).toFloat() * 5f))
}

private fun DrawScope.drawLiveIndicator(palette: SpectrumPalette, t: Float) {
    drawCircle(palette.cardStrong.copy(alpha = 0.92f), 42f, Offset(64f, 64f))
    drawArc(
        brush = Brush.sweepGradient(
            listOf(palette.cyan, palette.emerald, palette.amber, palette.rose, palette.violet, palette.cyan),
            Offset(64f, 64f),
        ),
        startAngle = -90f + t * 360f,
        sweepAngle = 282f,
        useCenter = false,
        topLeft = Offset(20f, 20f),
        size = Size(88f, 88f),
        style = Stroke(12f, cap = StrokeCap.Round),
    )
    val needle = -130f + 260f * ((sin((t * 2f * PI).toDouble()).toFloat() + 1f) / 2f)
    withTransform({ rotate(needle, Offset(64f, 64f)) }) {
        drawLine(palette.cyan, Offset(64f, 64f), Offset(64f, 37f), 4f, StrokeCap.Round)
    }
    drawCircle(palette.cyan, 6f, Offset(64f, 64f))
}

private fun DrawScope.drawLiveSpatial(palette: SpectrumPalette, t: Float) {
    val shift = sin((t * 2f * PI).toDouble()).toFloat() * 5f
    val top = Offset(64f, 18f + shift)
    val left = Offset(25f + shift * 0.35f, 48f)
    val right = Offset(103f - shift * 0.35f, 48f)
    val center = Offset(64f, 74f)
    val bottom = Offset(64f, 111f - shift)
    val topFace = Path().apply { moveTo(top.x, top.y); lineTo(right.x, right.y); lineTo(center.x, center.y); lineTo(left.x, left.y); close() }
    val leftFace = Path().apply { moveTo(left.x, left.y); lineTo(center.x, center.y); lineTo(bottom.x, bottom.y); lineTo(27f, 80f); close() }
    val rightFace = Path().apply { moveTo(right.x, right.y); lineTo(101f, 80f); lineTo(bottom.x, bottom.y); lineTo(center.x, center.y); close() }
    drawPath(topFace, Brush.linearGradient(listOf(palette.cyan, palette.blue), top, center))
    drawPath(leftFace, Brush.linearGradient(listOf(palette.blue, palette.violet.copy(alpha = 0.65f)), left, bottom))
    drawPath(rightFace, Brush.linearGradient(listOf(palette.violet, palette.rose.copy(alpha = 0.72f)), right, bottom))
    drawPath(topFace, palette.cyan.copy(alpha = 0.8f), style = Stroke(2f, join = StrokeJoin.Round))
}

private fun DrawScope.drawLiveGem(palette: SpectrumPalette, t: Float) {
    val pulse = 0.92f + 0.08f * ((sin((t * 2f * PI).toDouble()).toFloat() + 1f) / 2f)
    withTransform({ scale(pulse, pulse, Offset(64f, 64f)); rotate(t * 18f - 9f, Offset(64f, 64f)) }) {
        val gem = Path().apply {
            moveTo(64f, 14f)
            lineTo(103f, 54f)
            lineTo(64f, 114f)
            lineTo(25f, 54f)
            close()
        }
        drawPath(
            gem,
            Brush.linearGradient(
                listOf(palette.cyan, palette.blue, palette.violet, palette.rose),
                Offset(25f, 20f),
                Offset(103f, 110f),
            ),
        )
        drawLine(Color.White.copy(alpha = 0.65f), Offset(64f, 17f), Offset(64f, 110f), 2f)
        drawLine(Color.White.copy(alpha = 0.45f), Offset(27f, 54f), Offset(101f, 54f), 2f)
        drawLine(Color.White.copy(alpha = 0.35f), Offset(25f, 54f), Offset(64f, 83f), 2f)
        drawLine(Color.White.copy(alpha = 0.35f), Offset(103f, 54f), Offset(64f, 83f), 2f)
    }
}

private fun DrawScope.drawLiveAssistant(palette: SpectrumPalette, t: Float) {
    val bob = sin((t * 2f * PI).toDouble()).toFloat() * 3f
    val blink = if (t in 0.46f..0.52f) 1.5f else 8f
    withTransform({ translate(top = bob) }) {
        drawLine(palette.violet, Offset(64f, 25f), Offset(64f, 14f), 4f, StrokeCap.Round)
        drawCircle(palette.rose.copy(alpha = 0.28f), 9f, Offset(64f, 10f))
        drawCircle(palette.rose, 4f, Offset(64f, 10f))
        drawRoundRect(
            brush = Brush.linearGradient(listOf(palette.cyan, palette.blue, palette.violet), Offset(24f, 30f), Offset(105f, 92f)),
            topLeft = Offset(21f, 28f),
            size = Size(86f, 61f),
            cornerRadius = CornerRadius(23f, 23f),
        )
        drawRoundRect(palette.backgroundTop.copy(alpha = 0.92f), Offset(29f, 36f), Size(70f, 45f), CornerRadius(17f, 17f))
        drawRoundRect(palette.cyan, Offset(42f, 51f + (8f - blink) / 2f), Size(14f, blink), CornerRadius(6f, 6f))
        drawRoundRect(palette.violet, Offset(72f, 51f + (8f - blink) / 2f), Size(14f, blink), CornerRadius(6f, 6f))
        drawArc(palette.cyan, 20f, 140f, false, Offset(51f, 61f), Size(26f, 12f), style = Stroke(2.5f, cap = StrokeCap.Round))
        drawRoundRect(
            brush = Brush.verticalGradient(listOf(palette.cardStrong, palette.backgroundTop)),
            topLeft = Offset(39f, 93f),
            size = Size(50f, 25f),
            cornerRadius = CornerRadius(12f, 12f),
        )
        drawCircle(palette.emerald, 5f, Offset(64f, 105f))
    }
}

private fun DrawScope.drawLiveBell(palette: SpectrumPalette, t: Float) {
    val envelope = sin((t * 2f * PI).toDouble()).toFloat()
    val tilt = if (t < 0.42f) envelope * 10f else 0f
    withTransform({ rotate(tilt, Offset(64f, 67f)) }) {
        val bell = Path().apply {
            moveTo(36f, 84f)
            quadraticTo(44f, 74f, 44f, 55f)
            cubicTo(44f, 25f, 84f, 25f, 84f, 55f)
            quadraticTo(84f, 74f, 92f, 84f)
            close()
        }
        drawPath(bell, Brush.verticalGradient(listOf(palette.rose, palette.violet, palette.blue), 26f, 91f))
        drawLine(palette.cyan, Offset(32f, 86f), Offset(96f, 86f), 5f, StrokeCap.Round)
        drawArc(palette.rose.copy(alpha = 0.7f), 200f, 140f, false, Offset(19f, 20f), Size(90f, 78f), style = Stroke(3f, cap = StrokeCap.Round))
        drawCircle(palette.amber, 6f, Offset(64f, 97f))
    }
}

private fun DrawScope.drawLiveTarget(palette: SpectrumPalette, t: Float) {
    val ripple = (t * 1.5f) % 1f
    drawCircle(palette.rose.copy(alpha = (1f - ripple) * 0.24f), 24f + ripple * 33f, Offset(61f, 66f), style = Stroke(4f))
    drawCircle(palette.rose.copy(alpha = 0.18f), 44f, Offset(61f, 66f))
    drawCircle(palette.rose, 36f, Offset(61f, 66f), style = Stroke(7f))
    drawCircle(palette.cyan, 22f, Offset(61f, 66f), style = Stroke(6f))
    drawCircle(palette.amber, 8f, Offset(61f, 66f))
    val tip = Offset(108f, 18f + sin(t * 2f * PI).toFloat() * 2f)
    drawLine(Color.White.copy(alpha = 0.9f), tip, Offset(65f, 61f), 5f, StrokeCap.Round)
    drawLine(palette.rose, Offset(96f, 17f), tip, 6f, StrokeCap.Round)
    drawLine(palette.rose, Offset(109f, 18f), Offset(109f, 31f), 6f, StrokeCap.Round)
}

private fun DrawScope.drawLiveShield(palette: SpectrumPalette, t: Float) {
    val breathe = 0.96f + abs(sin((t * PI).toDouble()).toFloat()) * 0.05f
    withTransform({ scale(breathe, breathe, Offset(64f, 64f)) }) {
        val shield = Path().apply {
            moveTo(64f, 14f)
            lineTo(102f, 29f)
            lineTo(102f, 62f)
            cubicTo(102f, 89f, 84f, 105f, 64f, 116f)
            cubicTo(44f, 105f, 26f, 89f, 26f, 62f)
            lineTo(26f, 29f)
            close()
        }
        drawPath(shield, Brush.linearGradient(listOf(palette.cyan, palette.emerald, palette.blue), Offset(26f, 18f), Offset(102f, 112f)))
        drawPath(shield, Color.White.copy(alpha = 0.48f), style = Stroke(2f, join = StrokeJoin.Round))
        val scanY = 34f + t * 56f
        drawLine(Color.White.copy(alpha = 0.55f), Offset(36f, scanY), Offset(92f, scanY), 2f, StrokeCap.Round)
        drawLine(palette.backgroundTop, Offset(45f, 64f), Offset(59f, 78f), 7f, StrokeCap.Round)
        drawLine(palette.backgroundTop, Offset(59f, 78f), Offset(84f, 48f), 7f, StrokeCap.Round)
    }
}

private fun DrawScope.drawLiveGlobe(palette: SpectrumPalette, t: Float) {
    drawCircle(Brush.radialGradient(listOf(palette.blue.copy(alpha = 0.32f), palette.backgroundTop.copy(alpha = 0.72f)), Offset(54f, 47f), 54f), 43f, Offset(64f, 64f))
    drawCircle(palette.cyan, 43f, Offset(64f, 64f), style = Stroke(4f))
    drawOval(palette.blue.copy(alpha = 0.88f), Offset(41f, 21f), Size(46f, 86f), style = Stroke(2.5f))
    val longitudeShift = sin((t * 2f * PI).toDouble()).toFloat() * 7f
    drawOval(palette.violet.copy(alpha = 0.72f), Offset(50f + longitudeShift, 21f), Size(28f - longitudeShift * 0.3f, 86f), style = Stroke(2f))
    drawLine(palette.cyan.copy(alpha = 0.8f), Offset(24f, 64f), Offset(104f, 64f), 2.5f)
    drawArc(palette.rose.copy(alpha = 0.75f), 180f, 180f, false, Offset(28f, 36f), Size(72f, 56f), style = Stroke(2f))
    withTransform({ rotate(t * 360f, Offset(64f, 64f)) }) {
        drawCircle(palette.emerald, 5f, Offset(64f, 11f))
        drawCircle(palette.emerald.copy(alpha = 0.18f), 11f, Offset(64f, 11f))
    }
}

private const val LIVE_ARTWORK_SIZE = 128f
