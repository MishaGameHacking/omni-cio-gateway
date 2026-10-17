package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import ru.omnicio.app.ui.theme.LocalSpectrumMotionPreference
import ru.omnicio.app.ui.workspace.LocalWorkspacePreferences
import kotlin.math.cos
import kotlin.math.sin

/** Decorative orbital mark; never a chart, risk gauge or financial forecast. */
@Composable
fun SpectrumCapitalOrbit(modifier: Modifier = Modifier) {
    val palette = LocalSpectrumPalette.current
    val depth = LocalWorkspacePreferences.current.value.depth
    val phase = rememberSpectrumLivePhase(LocalSpectrumMotionPreference.current.enabled, 9000)
    Canvas(modifier) {
        val radius = size.minDimension * .34f
        if (radius <= 0) return@Canvas
        val center = Offset(size.width / 2, size.height / 2)
        drawCircle(Brush.radialGradient(listOf(palette.cyan.copy(alpha = .12f), Color.Transparent), center, radius * 1.7f), radius * 1.7f, center)
        if (depth) drawOval(Color.Black.copy(alpha = .22f), Offset(center.x - radius, center.y + radius * .65f), Size(radius * 2, radius * .35f))
        drawCircle(Brush.radialGradient(listOf(palette.cardStrong, palette.backgroundTop), center - Offset(radius * .4f, radius * .5f), radius * 1.8f), radius, center)
        val angle = phase.value * (Math.PI * 2).toFloat()
        listOf(-28f, 38f, 90f).forEachIndexed { index, rotation ->
            val color = listOf(palette.cyan, palette.violet, palette.blue)[index]
            rotate(rotation, center) {
                drawOval(color.copy(alpha = .48f), Offset(center.x - radius * 1.4f, center.y - radius * .44f),
                    Size(radius * 2.8f, radius * .88f), style = Stroke(radius * .016f))
                val point = Offset(center.x + cos(angle + index) * radius * 1.4f, center.y + sin(angle + index) * radius * .44f)
                drawCircle(color.copy(alpha = .14f), radius * .14f, point)
                drawCircle(color, radius * .055f, point)
            }
        }
        drawCircle(palette.cyan.copy(alpha = .8f), radius * .12f, center)
        drawCircle(palette.cyan.copy(alpha = .14f), radius * .22f, center)
    }
}
