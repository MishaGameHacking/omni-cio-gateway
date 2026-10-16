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

/** Visible state of the on-device Analyst AI character. */
@Immutable
enum class AnalystAvatarMood {
    Ready,
    Attention,
    Waiting,
}

/**
 * Original native 2D character for Analyst AI.
 *
 * The avatar is rendered entirely with Compose Canvas: no remote image, GIF or
 * broker artwork is loaded. Its mood is derived by the caller from real client
 * state and never pretends that a model has completed work it did not perform.
 */
@Composable
fun SpectrumAnalystAvatar(
    mood: AnalystAvatarMood,
    modifier: Modifier = Modifier,
) {
    val palette = LocalSpectrumPalette.current
    val dark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val accent = when (mood) {
        AnalystAvatarMood.Ready -> palette.emerald
        AnalystAvatarMood.Attention -> palette.amber
        AnalystAvatarMood.Waiting -> palette.blue
    }
    val description = when (mood) {
        AnalystAvatarMood.Ready -> "Analyst AI готов показать выводы"
        AnalystAvatarMood.Attention -> "Analyst AI просит проверить данные"
        AnalystAvatarMood.Waiting -> "Analyst AI ожидает данные портфеля"
    }

    Canvas(
        modifier
            .aspectRatio(1f)
            .semantics { contentDescription = description },
    ) {
        if (size.minDimension <= 0f) return@Canvas
        val unit = size.minDimension / 180f
        val dx = (size.width - size.minDimension) / 2f
        val dy = (size.height - size.minDimension) / 2f

        withTransform({
            translate(dx, dy)
            scale(unit, unit, Offset.Zero)
        }) {
            val center = Offset(90f, 86f)
            val glowAlpha = if (dark) 0.30f else 0.14f

            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        accent.copy(alpha = glowAlpha),
                        palette.violet.copy(alpha = glowAlpha * 0.55f),
                        Color.Transparent,
                    ),
                    center = center,
                    radius = 84f,
                ),
                radius = 84f,
                center = center,
            )

            drawCircle(
                color = palette.cyan.copy(alpha = if (dark) 0.34f else 0.20f),
                radius = 72f,
                center = center,
                style = Stroke(width = 1.4f),
            )
            drawArc(
                color = palette.violet.copy(alpha = 0.62f),
                startAngle = 205f,
                sweepAngle = 178f,
                useCenter = false,
                topLeft = Offset(9f, 45f),
                size = Size(162f, 84f),
                style = Stroke(width = 2.1f, cap = StrokeCap.Round),
            )
            drawCircle(palette.cyan, radius = 2.5f, center = Offset(154f, 63f))
            drawCircle(palette.rose, radius = 2.2f, center = Offset(29f, 122f))

            // Grounding shadow keeps the character readable in both themes.
            drawOval(
                color = MaterialTheme.colorScheme.onBackground.copy(alpha = if (dark) 0.16f else 0.09f),
                topLeft = Offset(45f, 157f),
                size = Size(90f, 12f),
            )

            // Antenna and status light.
            drawLine(
                color = palette.blue,
                start = Offset(90f, 31f),
                end = Offset(90f, 17f),
                strokeWidth = 4f,
                cap = StrokeCap.Round,
            )
            drawCircle(accent.copy(alpha = 0.25f), radius = 9f, center = Offset(90f, 12f))
            drawCircle(accent, radius = 4.5f, center = Offset(90f, 12f))

            // Ear modules.
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

            // Head shell and glass face.
            drawRoundRect(
                brush = Brush.linearGradient(
                    listOf(
                        palette.blue.copy(alpha = if (dark) 0.96f else 0.78f),
                        palette.violet.copy(alpha = if (dark) 0.90f else 0.66f),
                        palette.rose.copy(alpha = if (dark) 0.76f else 0.48f),
                    ),
                    start = Offset(31f, 34f),
                    end = Offset(149f, 111f),
                ),
                topLeft = Offset(30f, 31f),
                size = Size(120f, 82f),
                cornerRadius = CornerRadius(28f, 28f),
            )
            drawRoundRect(
                color = palette.backgroundTop.copy(alpha = if (dark) 0.92f else 0.80f),
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

            // Eyes and highlights.
            drawRoundRect(
                brush = Brush.horizontalGradient(listOf(palette.cyan, palette.blue)),
                topLeft = Offset(55f, 60f),
                size = Size(25f, 14f),
                cornerRadius = CornerRadius(7f, 7f),
            )
            drawRoundRect(
                brush = Brush.horizontalGradient(listOf(palette.violet, palette.rose)),
                topLeft = Offset(100f, 60f),
                size = Size(25f, 14f),
                cornerRadius = CornerRadius(7f, 7f),
            )
            drawCircle(Color.White.copy(alpha = 0.82f), radius = 2.1f, center = Offset(72f, 64f))
            drawCircle(Color.White.copy(alpha = 0.82f), radius = 2.1f, center = Offset(117f, 64f))

            val smile = Path().apply {
                moveTo(71f, 84f)
                cubicTo(80f, 93f, 100f, 93f, 109f, 84f)
            }
            drawPath(smile, accent, style = Stroke(width = 3f, cap = StrokeCap.Round))

            // Neck, torso and arms.
            drawRoundRect(
                color = palette.blue.copy(alpha = 0.66f),
                topLeft = Offset(80f, 107f),
                size = Size(20f, 13f),
                cornerRadius = CornerRadius(6f, 6f),
            )
            drawRoundRect(
                brush = Brush.verticalGradient(
                    listOf(
                        palette.cardStrong.copy(alpha = 0.98f),
                        palette.backgroundTop.copy(alpha = if (dark) 0.96f else 0.82f),
                    ),
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

            // Chest mark ties the character to the Analyst AI brain identity.
            drawCircle(accent.copy(alpha = 0.18f), radius = 15f, center = Offset(90f, 139f))
            drawCircle(accent, radius = 11f, center = Offset(90f, 139f), style = Stroke(width = 2f))
            drawLine(accent, Offset(90f, 130f), Offset(90f, 148f), 2.2f, StrokeCap.Round)
            drawLine(accent, Offset(83f, 136f), Offset(97f, 142f), 2.2f, StrokeCap.Round)
            drawLine(accent, Offset(83f, 142f), Offset(97f, 136f), 2.2f, StrokeCap.Round)
        }
    }
}
