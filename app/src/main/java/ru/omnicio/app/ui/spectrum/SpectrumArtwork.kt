package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
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

/** Original resolution-independent artwork, not a screenshot or a remote image dependency. */
@Composable
fun SpectrumBrain(modifier: Modifier = Modifier) {
    val outline = remember { brainOutline() }
    val circuits = remember { brainCircuits() }
    Canvas(modifier) { artCoordinates {
        glow(Color(0xFF6143E8), Offset(128f, 128f), 123f)
        val brush = Brush.linearGradient(listOf(Color(0xFF28DFFF), Color(0xFF3989FF), Color(0xFFA35CFF)), Offset(30f, 170f), Offset(221f, 69f))
        drawPath(outline, Color(0xFF07142D))
        drawPath(outline, brush, style = Stroke(20f), alpha = .09f)
        drawPath(outline, brush, style = Stroke(10f), alpha = .18f)
        drawPath(outline, brush, style = Stroke(3.5f, cap = StrokeCap.Round))
        drawPath(circuits, brush, style = Stroke(2.4f, cap = StrokeCap.Round))
        listOf(Offset(71f, 85f), Offset(92f, 137f), Offset(62f, 160f), Offset(164f, 72f), Offset(182f, 129f), Offset(159f, 176f)).forEach {
            drawCircle(Color(0xFF57DFFF).copy(alpha = .20f), 8f, it)
            drawCircle(Color(0xFFA9F4FF), 2.8f, it)
        }
    } }
}

private fun brainOutline() = Path().apply {
    moveTo(125f, 44f)
    cubicTo(104f, 19f, 77f, 28f, 74f, 50f)
    cubicTo(49f, 39f, 31f, 58f, 38f, 82f)
    cubicTo(13f, 90f, 14f, 122f, 34f, 132f)
    cubicTo(13f, 157f, 24f, 181f, 46f, 184f)
    cubicTo(40f, 214f, 74f, 230f, 92f, 208f)
    cubicTo(104f, 235f, 124f, 216f, 125f, 195f)
    close()
    moveTo(132f, 44f)
    cubicTo(153f, 19f, 180f, 28f, 183f, 50f)
    cubicTo(208f, 39f, 226f, 58f, 219f, 82f)
    cubicTo(244f, 90f, 243f, 122f, 223f, 132f)
    cubicTo(244f, 157f, 233f, 181f, 211f, 184f)
    cubicTo(217f, 214f, 183f, 230f, 165f, 208f)
    cubicTo(153f, 235f, 133f, 216f, 132f, 195f)
    close()
}

private fun brainCircuits() = Path().apply {
    moveTo(74f, 50f); cubicTo(63f, 69f, 69f, 81f, 88f, 79f); lineTo(101f, 65f); lineTo(101f, 46f)
    moveTo(39f, 84f); lineTo(58f, 94f); lineTo(59f, 119f); lineTo(84f, 119f); lineTo(92f, 137f)
    moveTo(34f, 132f); lineTo(62f, 144f); lineTo(62f, 160f)
    moveTo(48f, 184f); lineTo(76f, 176f); lineTo(96f, 187f); lineTo(96f, 207f)
    moveTo(113f, 93f); lineTo(96f, 101f); lineTo(96f, 117f)
    moveTo(125f, 161f); lineTo(105f, 153f); lineTo(88f, 161f)
    moveTo(183f, 50f); cubicTo(194f, 69f, 188f, 81f, 169f, 79f); lineTo(156f, 65f); lineTo(156f, 46f)
    moveTo(218f, 84f); lineTo(199f, 94f); lineTo(198f, 119f); lineTo(173f, 119f); lineTo(165f, 137f)
    moveTo(223f, 132f); lineTo(195f, 144f); lineTo(195f, 162f)
    moveTo(209f, 184f); lineTo(181f, 176f); lineTo(161f, 187f); lineTo(161f, 207f)
    moveTo(144f, 93f); lineTo(161f, 101f); lineTo(161f, 117f)
    moveTo(132f, 161f); lineTo(152f, 153f); lineTo(169f, 161f)
}

@Composable
fun SpectrumRobot(modifier: Modifier = Modifier) {
    Canvas(modifier) { artCoordinates {
        glow(Color(0xFF237CFF), Offset(124f, 126f), 124f)
        val shell = Brush.linearGradient(listOf(Color(0xFF7BEAFF), Color(0xFF268BFA), Color(0xFF42309A)), Offset(62f, 60f), Offset(205f, 217f))
        val torso = Path().apply { moveTo(91f, 157f); quadraticTo(124f, 148f, 157f, 157f); lineTo(167f, 215f); quadraticTo(124f, 242f, 83f, 215f); close() }
        drawPath(torso, shell)
        drawRoundRect(shell, Offset(49f, 162f), Size(24f, 67f), CornerRadius(12f))
        drawRoundRect(shell, Offset(179f, 155f), Size(24f, 67f), CornerRadius(12f))
        drawRoundRect(shell, Offset(26f, 83f), Size(19f, 40f), CornerRadius(8f))
        drawRoundRect(shell, Offset(210f, 83f), Size(19f, 40f), CornerRadius(8f))
        drawLine(Color(0xFF64DFFF), Offset(127f, 38f), Offset(127f, 55f), 5f, StrokeCap.Round)
        glow(Color(0xFF7F48FF), Offset(127f, 30f), 19f)
        drawCircle(Color(0xFFA384FF), 7f, Offset(127f, 30f))
        drawRoundRect(shell, Offset(40f, 50f), Size(177f, 105f), CornerRadius(37f))
        drawRoundRect(Color(0xFF050E27), Offset(50f, 60f), Size(156f, 83f), CornerRadius(29f))
        drawRoundRect(Color(0xFF42E8FF), Offset(78f, 84f), Size(18f, 26f), CornerRadius(9f))
        drawRoundRect(Color(0xFF42E8FF), Offset(159f, 84f), Size(18f, 26f), CornerRadius(9f))
        val smile = Path().apply { moveTo(113f, 118f); quadraticTo(128f, 129f, 143f, 118f) }
        drawPath(smile, Color(0xFF86EFFF), style = Stroke(3.5f, cap = StrokeCap.Round))
        drawCircle(Color(0xFF063152), 17f, Offset(126f, 189f))
        drawCircle(Color(0xFF24D6E7), 10f, Offset(126f, 189f), style = Stroke(2f))
        drawLine(Color(0xFFC2F8FF).copy(alpha = .8f), Offset(74f, 64f), Offset(106f, 61f), 2f, StrokeCap.Round)
    } }
}

@Composable
fun SpectrumGlobe(modifier: Modifier = Modifier) {
    val land = remember { globeLand() }
    Canvas(modifier) { artCoordinates {
        val middle = Offset(128f, 128f)
        glow(Color(0xFF2C68DF), middle, 126f)
        drawCircle(Brush.radialGradient(listOf(Color(0xFF0B507A), Color(0xFF092E63), Color(0xFF050A29)), Offset(96f, 85f), 150f), 81f, middle)
        drawPath(land, Brush.linearGradient(listOf(Color(0xFF32B6CD), Color(0xFF3766B7)), Offset(60f, 61f), Offset(172f, 190f)))
        globeGrid()
        drawCircle(Brush.linearGradient(listOf(Color(0xFF75EEFF), Color(0xFF394EF2), Color(0xFF9F55E1))), 81f, middle, style = Stroke(2.2f))
        withTransform({ rotate(-23f, middle) }) {
            drawOval(Color(0xFF2BDFF8).copy(alpha = .65f), Offset(12f, 83f), Size(232f, 90f), style = Stroke(1.4f))
            drawArc(Brush.linearGradient(listOf(Color(0xFF04EBD2), Color(0xFF8C40FD))), 6f, 156f, false, Offset(8f, 78f), Size(240f, 100f), style = Stroke(4f, cap = StrokeCap.Round))
            drawCircle(Color(0xFF68FFFF), 4f, Offset(238f, 131f))
        }
        withTransform({ rotate(36f, middle) }) {
            drawOval(Color(0xFFAF6BFF).copy(alpha = .48f), Offset(7f, 97f), Size(242f, 65f), style = Stroke(1.3f))
        }
        listOf(Offset(37f, 72f), Offset(207f, 43f), Offset(222f, 181f), Offset(67f, 215f)).forEach {
            glow(Color(0xFF53CFFF), it, 9f)
            drawCircle(Color(0xFFCCFDFF), 1.8f, it)
        }
    } }
}

private fun DrawScope.globeGrid() {
    val grid = Color(0xFF49BDDE).copy(alpha = .22f)
    drawOval(grid, Offset(74f, 47f), Size(108f, 162f), style = Stroke(.8f))
    drawOval(grid, Offset(105f, 47f), Size(46f, 162f), style = Stroke(.8f))
    drawOval(grid, Offset(47f, 92f), Size(162f, 72f), style = Stroke(.8f))
    drawOval(grid, Offset(58f, 65f), Size(140f, 40f), style = Stroke(.8f))
    drawOval(grid, Offset(58f, 155f), Size(140f, 40f), style = Stroke(.8f))
}

private fun globeLand() = Path().apply {
    moveTo(88f, 62f); lineTo(119f, 53f); lineTo(144f, 56f); lineTo(159f, 69f)
    lineTo(148f, 78f); lineTo(160f, 90f); lineTo(146f, 108f); lineTo(133f, 103f)
    lineTo(117f, 122f); lineTo(108f, 144f); lineTo(94f, 157f); lineTo(80f, 140f)
    lineTo(82f, 116f); lineTo(66f, 103f); lineTo(69f, 80f); close()
    moveTo(130f, 130f); lineTo(153f, 116f); lineTo(176f, 124f); lineTo(188f, 147f)
    lineTo(175f, 168f); lineTo(166f, 191f); lineTo(146f, 181f); lineTo(151f, 159f); close()
    moveTo(173f, 73f); lineTo(188f, 87f); lineTo(192f, 105f); lineTo(176f, 100f); close()
}

private fun DrawScope.glow(color: Color, center: Offset, radius: Float) {
    drawCircle(Brush.radialGradient(listOf(color.copy(alpha = .25f), color.copy(alpha = .05f), Color.Transparent), center, radius), radius, center)
}
private fun DrawScope.artCoordinates(block: DrawScope.() -> Unit) {
    if (size.minDimension <= 0f) return
    val factor = size.minDimension / 256f
    withTransform({ translate((size.width - size.minDimension) / 2f, (size.height - size.minDimension) / 2f); scale(factor, factor, Offset.Zero) }, block)
}
