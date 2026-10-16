package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

/** Slow, draw-only aurora used only by the mandatory update journey. */
@Composable
fun SpectrumUpdateBackdrop(
    motionAllowed: Boolean,
    modifier: Modifier = Modifier,
    content: @Composable BoxScope.() -> Unit,
) {
    val palette = LocalSpectrumPalette.current
    val dark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val phase = rememberSpectrumLivePhase(motionAllowed, 12_000)
    val base = if (dark) {
        listOf(Color(0xFF020713), Color(0xFF071226), Color(0xFF03111F), Color(0xFF020713))
    } else {
        listOf(Color(0xFFF7F9FF), Color(0xFFEAF2FF), Color(0xFFF5F0FF))
    }

    Box(modifier = modifier.background(Brush.verticalGradient(base))) {
        Canvas(Modifier.fillMaxSize()) {
            if (size.minDimension <= 0f) return@Canvas
            val t = phase.value
            val angle = t * 2f * PI.toFloat()
            val min = size.minDimension
            val first = Offset(
                size.width * (0.78f + cos(angle.toDouble()).toFloat() * 0.09f),
                size.height * (0.16f + sin(angle.toDouble()).toFloat() * 0.05f),
            )
            val second = Offset(
                size.width * (0.18f + cos((angle + 2.1f).toDouble()).toFloat() * 0.08f),
                size.height * (0.72f + sin((angle + 2.1f).toDouble()).toFloat() * 0.06f),
            )
            drawCircle(
                Brush.radialGradient(
                    listOf(palette.rose.copy(alpha = if (dark) 0.20f else 0.08f), Color.Transparent),
                    first,
                    min * 0.74f,
                ),
                min * 0.74f,
                first,
            )
            drawCircle(
                Brush.radialGradient(
                    listOf(palette.violet.copy(alpha = if (dark) 0.18f else 0.07f), Color.Transparent),
                    second,
                    min * 0.72f,
                ),
                min * 0.72f,
                second,
            )
            drawCircle(
                Brush.radialGradient(
                    listOf(palette.cyan.copy(alpha = if (dark) 0.10f else 0.045f), Color.Transparent),
                    Offset(size.width * 0.54f, size.height * (0.52f + sin((angle * 0.7f).toDouble()).toFloat() * 0.06f)),
                    min * 0.58f,
                ),
                min * 0.58f,
                Offset(size.width * 0.54f, size.height * (0.52f + sin((angle * 0.7f).toDouble()).toFloat() * 0.06f)),
            )

            if (dark) {
                repeat(28) { index ->
                    val x = ((index * 73) % 101) / 100f * size.width
                    val baseY = ((index * 41 + 17) % 97) / 100f
                    val y = ((baseY + t * (0.025f + (index % 4) * 0.006f)) % 1f) * size.height
                    val alpha = if (index % 6 == 0) 0.27f else 0.12f
                    drawCircle(
                        color = MaterialTheme.colorScheme.onBackground.copy(alpha = alpha),
                        radius = if (index % 6 == 0) 1.8f else 1f,
                        center = Offset(x, y),
                    )
                }
            }

            val orbitCenter = Offset(size.width * 0.5f, size.height * 0.24f)
            val orbitWidth = min * 0.76f
            val orbitHeight = min * 0.28f
            drawArc(
                color = palette.cyan.copy(alpha = if (dark) 0.18f else 0.10f),
                startAngle = 195f + t * 35f,
                sweepAngle = 205f,
                useCenter = false,
                topLeft = Offset(orbitCenter.x - orbitWidth / 2f, orbitCenter.y - orbitHeight / 2f),
                size = Size(orbitWidth, orbitHeight),
                style = Stroke(width = 1.5f, cap = StrokeCap.Round),
            )
        }
        content()
    }
}

/** Native animated warning mark for a required update; never a bitmap or GIF. */
@Composable
fun SpectrumUpdateAlert(
    updateRequired: Boolean,
    motionAllowed: Boolean,
    modifier: Modifier = Modifier,
) {
    val palette = LocalSpectrumPalette.current
    val dark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val phase = rememberSpectrumLivePhase(motionAllowed, 2_600)
    val accent = if (updateRequired) MaterialTheme.colorScheme.error else palette.cyan
    val description = if (updateRequired) {
        "Требуется обязательное обновление Analyst AI"
    } else {
        "Analyst AI проверяет актуальную версию"
    }

    Canvas(
        modifier = modifier
            .aspectRatio(1f)
            .semantics { contentDescription = description },
    ) {
        if (size.minDimension <= 0f) return@Canvas
        val unit = size.minDimension / UPDATE_ARTWORK_SIZE
        val dx = (size.width - size.minDimension) / 2f
        val dy = (size.height - size.minDimension) / 2f
        withTransform({
            translate(dx, dy)
            scale(unit, unit, Offset.Zero)
        }) {
            val t = phase.value
            val wave = (sin((t * 2f * PI).toDouble()).toFloat() + 1f) / 2f
            val center = Offset(64f, 63f)
            drawCircle(
                brush = Brush.radialGradient(
                    listOf(
                        accent.copy(alpha = (if (dark) 0.22f else 0.12f) + wave * 0.12f),
                        accent.copy(alpha = 0.05f),
                        Color.Transparent,
                    ),
                    center = center,
                    radius = 58f,
                ),
                radius = 58f,
                center = center,
            )
            repeat(3) { index ->
                val local = (t + index / 3f) % 1f
                drawCircle(
                    color = accent.copy(alpha = (1f - local) * 0.24f),
                    radius = 35f + local * 25f,
                    center = center,
                    style = Stroke(width = 2.2f),
                )
            }
            drawArc(
                brush = Brush.sweepGradient(
                    listOf(Color.Transparent, palette.rose, palette.amber, Color.Transparent),
                    center,
                ),
                startAngle = -90f + t * 360f,
                sweepAngle = 110f,
                useCenter = false,
                topLeft = Offset(13f, 12f),
                size = Size(102f, 102f),
                style = Stroke(width = 4f, cap = StrokeCap.Round),
            )

            val scale = 0.97f + wave * 0.035f
            withTransform({ scale(scale, scale, center) }) {
                val triangle = Path().apply {
                    moveTo(64f, 16f)
                    quadraticTo(69f, 16f, 73f, 24f)
                    lineTo(112f, 94f)
                    quadraticTo(116f, 103f, 105f, 103f)
                    lineTo(23f, 103f)
                    quadraticTo(12f, 103f, 17f, 94f)
                    lineTo(56f, 24f)
                    quadraticTo(59f, 16f, 64f, 16f)
                    close()
                }
                drawPath(
                    path = triangle,
                    brush = Brush.linearGradient(
                        listOf(accent, palette.rose, palette.amber),
                        Offset(28f, 18f),
                        Offset(102f, 103f),
                    ),
                )
                drawPath(
                    path = triangle,
                    color = Color.White.copy(alpha = if (dark) 0.58f else 0.42f),
                    style = Stroke(width = 2.2f, join = androidx.compose.ui.graphics.StrokeJoin.Round),
                )
                drawLine(
                    color = Color.White,
                    start = Offset(64f, 42f),
                    end = Offset(64f, 72f),
                    strokeWidth = 8f,
                    cap = StrokeCap.Round,
                )
                drawCircle(Color.White, 5f, Offset(64f, 87f))
            }
        }
    }
}

private const val UPDATE_ARTWORK_SIZE = 128f
