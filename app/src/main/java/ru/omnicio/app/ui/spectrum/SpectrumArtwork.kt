package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform

/**
 * Original resolution-independent Analyst AI character.
 *
 * The artwork is rendered entirely with Compose primitives. It is not a copied
 * screenshot, remote image, animated GIF, or broker asset, so it scales cleanly
 * on Android 16 displays and remains available offline.
 */
@Composable
fun SpectrumRobot(modifier: Modifier = Modifier) {
    Canvas(modifier = modifier) {
        inArtworkCoordinates {
            val shell = Brush.linearGradient(
                colors = listOf(
                    Color(0xFF83F2FF),
                    Color(0xFF268BFA),
                    Color(0xFF5A35C8),
                ),
                start = Offset(54f, 48f),
                end = Offset(202f, 224f),
            )

            drawGlow(
                color = Color(0xFF237CFF),
                center = Offset(128f, 128f),
                radius = 124f,
            )
            drawGlow(
                color = Color(0xFF8B4DFF),
                center = Offset(128f, 34f),
                radius = 28f,
            )

            val torso = Path().apply {
                moveTo(91f, 157f)
                quadraticTo(124f, 148f, 157f, 157f)
                lineTo(167f, 215f)
                quadraticTo(124f, 242f, 83f, 215f)
                close()
            }
            drawPath(path = torso, brush = shell)

            drawRoundRect(
                brush = shell,
                topLeft = Offset(49f, 162f),
                size = Size(24f, 67f),
                cornerRadius = CornerRadius(12f),
            )
            drawRoundRect(
                brush = shell,
                topLeft = Offset(179f, 155f),
                size = Size(24f, 67f),
                cornerRadius = CornerRadius(12f),
            )
            drawRoundRect(
                brush = shell,
                topLeft = Offset(26f, 83f),
                size = Size(19f, 40f),
                cornerRadius = CornerRadius(8f),
            )
            drawRoundRect(
                brush = shell,
                topLeft = Offset(210f, 83f),
                size = Size(19f, 40f),
                cornerRadius = CornerRadius(8f),
            )

            drawLine(
                color = Color(0xFF64DFFF),
                start = Offset(128f, 38f),
                end = Offset(128f, 55f),
                strokeWidth = 5f,
                cap = StrokeCap.Round,
            )
            drawCircle(
                color = Color(0xFFA384FF),
                radius = 7f,
                center = Offset(128f, 30f),
            )

            drawRoundRect(
                brush = shell,
                topLeft = Offset(40f, 50f),
                size = Size(177f, 105f),
                cornerRadius = CornerRadius(37f),
            )
            drawRoundRect(
                color = Color(0xFF050E27),
                topLeft = Offset(50f, 60f),
                size = Size(156f, 83f),
                cornerRadius = CornerRadius(29f),
            )

            drawRoundRect(
                color = Color(0xFF42E8FF),
                topLeft = Offset(78f, 84f),
                size = Size(18f, 26f),
                cornerRadius = CornerRadius(9f),
            )
            drawRoundRect(
                color = Color(0xFF42E8FF),
                topLeft = Offset(159f, 84f),
                size = Size(18f, 26f),
                cornerRadius = CornerRadius(9f),
            )

            val smile = Path().apply {
                moveTo(113f, 118f)
                quadraticTo(128f, 129f, 143f, 118f)
            }
            drawPath(
                path = smile,
                color = Color(0xFF86EFFF),
                style = Stroke(width = 3.5f, cap = StrokeCap.Round),
            )

            drawCircle(
                color = Color(0xFF063152),
                radius = 17f,
                center = Offset(126f, 189f),
            )
            drawCircle(
                color = Color(0xFF24D6E7),
                radius = 10f,
                center = Offset(126f, 189f),
                style = Stroke(width = 2f),
            )
            drawLine(
                color = Color(0xFFC2F8FF).copy(alpha = 0.8f),
                start = Offset(74f, 64f),
                end = Offset(106f, 61f),
                strokeWidth = 2f,
                cap = StrokeCap.Round,
            )
        }
    }
}

private fun DrawScope.drawGlow(color: Color, center: Offset, radius: Float) {
    drawCircle(
        brush = Brush.radialGradient(
            colors = listOf(
                color.copy(alpha = 0.25f),
                color.copy(alpha = 0.06f),
                Color.Transparent,
            ),
            center = center,
            radius = radius,
        ),
        radius = radius,
        center = center,
    )
}

private fun DrawScope.inArtworkCoordinates(block: DrawScope.() -> Unit) {
    if (size.minDimension <= 0f) return
    val scale = size.minDimension / ARTWORK_SIZE
    withTransform(
        transformBlock = {
            translate(
                left = (size.width - size.minDimension) / 2f,
                top = (size.height - size.minDimension) / 2f,
            )
            scale(
                scaleX = scale,
                scaleY = scale,
                pivot = Offset.Zero,
            )
        },
        drawBlock = block,
    )
}

private const val ARTWORK_SIZE = 256f
