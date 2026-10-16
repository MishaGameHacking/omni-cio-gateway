package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
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
import kotlin.math.sin

/** Visible state of the native Analyst AI character, derived from real client state. */
@Immutable
enum class AnalystAvatarMood {
    Ready,
    Attention,
    Waiting,
}

/**
 * Original native 2D Analyst AI character. The animation is rendered by Compose
 * Canvas and runs only while the Activity is started and motion is enabled.
 */
@Composable
fun SpectrumAnalystAvatar(
    mood: AnalystAvatarMood,
    modifier: Modifier = Modifier,
    motionAllowed: Boolean = true,
) {
    val palette = LocalSpectrumPalette.current
    val colors = MaterialTheme.colorScheme
    val dark = colors.background.luminance() < 0.5f
    val phase = rememberSpectrumLivePhase(motionAllowed, 3_800)
    val accent = when (mood) {
        AnalystAvatarMood.Ready -> palette.emerald
        AnalystAvatarMood.Attention -> palette.amber
        AnalystAvatarMood.Waiting -> palette.blue
    }
    val description = when (mood) {
        AnalystAvatarMood.Ready -> "Analyst AI готов показать выводы по данным портфеля"
        AnalystAvatarMood.Attention -> "Analyst AI просит проверить данные портфеля"
        AnalystAvatarMood.Waiting -> "Analyst AI ожидает данные портфеля"
    }

    Canvas(
        modifier = modifier
            .aspectRatio(1f)
            .semantics { contentDescription = description },
    ) {
        if (size.minDimension <= 0f) return@Canvas
        val unit = size.minDimension / AVATAR_SIZE
        val dx = (size.width - size.minDimension) / 2f
        val dy = (size.height - size.minDimension) / 2f
        withTransform({
            translate(dx, dy)
            scale(unit, unit, Offset.Zero)
        }) {
            val t = phase.value
            val bob = sin((t * 2f * PI).toDouble()).toFloat() * 2.7f
            val blinkHeight = if (t in 0.47f..0.515f) 2f else 13f
            val pulse = (sin((t * 2f * PI).toDouble()).toFloat() + 1f) / 2f
            val center = Offset(90f, 86f)

            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        accent.copy(alpha = (if (dark) 0.24f else 0.12f) + pulse * 0.08f),
                        palette.violet.copy(alpha = if (dark) 0.12f else 0.05f),
                        Color.Transparent,
                    ),
                    center = center,
                    radius = 84f,
                ),
                radius = 84f,
                center = center,
            )
            drawArc(
                color = palette.cyan.copy(alpha = 0.48f),
                startAngle = 200f + t * 70f,
                sweepAngle = 190f,
                useCenter = false,
                topLeft = Offset(9f, 45f),
                size = Size(162f, 84f),
                style = Stroke(width = 1.8f, cap = StrokeCap.Round),
            )
            drawCircle(palette.cyan, radius = 2.5f, center = Offset(154f, 63f))
            drawCircle(palette.rose, radius = 2.2f, center = Offset(29f, 122f))
            drawOval(
                color = colors.onBackground.copy(alpha = if (dark) 0.16f else 0.08f),
                topLeft = Offset(45f - bob, 157f),
                size = Size(90f + bob * 2f, 12f),
            )

            withTransform({ translate(top = bob) }) {
                drawLine(palette.blue, Offset(90f, 31f), Offset(90f, 17f), 4f, StrokeCap.Round)
                drawCircle(accent.copy(alpha = 0.18f + pulse * 0.18f), radius = 9f + pulse * 2f, center = Offset(90f, 12f))
                drawCircle(accent, radius = 4.5f, center = Offset(90f, 12f))

                drawRoundRect(
                    color = palette.blue.copy(alpha = 0.42f),
                    topLeft = Offset(20f, 61f),
                    size = Size(18f, 35f),
                    cornerRadius = CornerRadius(9f, 9f),
                )
                drawRoundRect(
                    color = palette.violet.copy(alpha = 0.42f),
                    topLeft = Offset(142f, 61f),
                    size = Size(18f, 35f),
                    cornerRadius = CornerRadius(9f, 9f),
                )

                drawRoundRect(
                    brush = Brush.linearGradient(
                        listOf(palette.blue, palette.violet, palette.rose.copy(alpha = 0.82f)),
                        start = Offset(31f, 34f),
                        end = Offset(149f, 111f),
                    ),
                    topLeft = Offset(30f, 31f),
                    size = Size(120f, 82f),
                    cornerRadius = CornerRadius(28f, 28f),
                )
                drawRoundRect(
                    color = palette.backgroundTop.copy(alpha = if (dark) 0.94f else 0.82f),
                    topLeft = Offset(39f, 42f),
                    size = Size(102f, 58f),
                    cornerRadius = CornerRadius(21f, 21f),
                )
                drawRoundRect(
                    color = palette.cyan.copy(alpha = 0.52f),
                    topLeft = Offset(39f, 42f),
                    size = Size(102f, 58f),
                    cornerRadius = CornerRadius(21f, 21f),
                    style = Stroke(width = 1.6f),
                )

                val eyeTop = 60f + (13f - blinkHeight) / 2f
                drawRoundRect(
                    brush = Brush.horizontalGradient(listOf(palette.cyan, palette.blue)),
                    topLeft = Offset(55f, eyeTop),
                    size = Size(25f, blinkHeight),
                    cornerRadius = CornerRadius(7f, 7f),
                )
                drawRoundRect(
                    brush = Brush.horizontalGradient(listOf(palette.violet, palette.rose)),
                    topLeft = Offset(100f, eyeTop),
                    size = Size(25f, blinkHeight),
                    cornerRadius = CornerRadius(7f, 7f),
                )
                if (blinkHeight > 4f) {
                    drawCircle(Color.White.copy(alpha = 0.82f), 2.1f, Offset(72f, 64f))
                    drawCircle(Color.White.copy(alpha = 0.82f), 2.1f, Offset(117f, 64f))
                }

                val smile = Path().apply {
                    moveTo(71f, 84f)
                    cubicTo(80f, 93f, 100f, 93f, 109f, 84f)
                }
                drawPath(smile, accent, style = Stroke(width = 3f, cap = StrokeCap.Round))

                drawRoundRect(
                    color = palette.blue.copy(alpha = 0.66f),
                    topLeft = Offset(80f, 107f),
                    size = Size(20f, 13f),
                    cornerRadius = CornerRadius(6f, 6f),
                )
                drawRoundRect(
                    brush = Brush.verticalGradient(
                        listOf(palette.cardStrong.copy(alpha = 0.98f), palette.backgroundTop.copy(alpha = 0.92f)),
                    ),
                    topLeft = Offset(48f, 116f),
                    size = Size(84f, 47f),
                    cornerRadius = CornerRadius(20f, 20f),
                )
                drawRoundRect(
                    color = palette.violet.copy(alpha = 0.58f),
                    topLeft = Offset(48f, 116f),
                    size = Size(84f, 47f),
                    cornerRadius = CornerRadius(20f, 20f),
                    style = Stroke(width = 1.8f),
                )
                drawLine(palette.blue, Offset(49f, 130f), Offset(30f, 145f), 7f, StrokeCap.Round)
                drawLine(palette.violet, Offset(131f, 130f), Offset(150f, 145f), 7f, StrokeCap.Round)
                drawCircle(palette.cyan.copy(alpha = 0.86f), 5.5f, Offset(27f, 148f))
                drawCircle(palette.rose.copy(alpha = 0.86f), 5.5f, Offset(153f, 148f))

                drawCircle(accent.copy(alpha = 0.16f + pulse * 0.12f), radius = 15f, center = Offset(90f, 139f))
                drawCircle(accent, radius = 11f, center = Offset(90f, 139f), style = Stroke(width = 2f))
                drawLine(accent, Offset(90f, 130f), Offset(90f, 148f), 2.2f, StrokeCap.Round)
                drawLine(accent, Offset(83f, 136f), Offset(97f, 142f), 2.2f, StrokeCap.Round)
                drawLine(accent, Offset(83f, 142f), Offset(97f, 136f), 2.2f, StrokeCap.Round)
            }
        }
    }
}

private const val AVATAR_SIZE = 180f
