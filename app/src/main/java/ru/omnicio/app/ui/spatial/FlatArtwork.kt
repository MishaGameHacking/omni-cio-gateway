package ru.omnicio.app.ui.spatial

import android.graphics.Paint
import android.graphics.Typeface
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.unit.dp
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.sin

/** Original vector artwork. All proportions are logical units, never downloaded images. */
internal fun DrawScope.drawFlatPrimitive(item: SpatialPrimitive, phase: Float) {
    val rect = item.rect
    val width = size.width * rect.width
    val height = size.height * rect.height
    if (width <= 0f || height <= 0f) return
    val left = size.width * rect.left
    val top = size.height * rect.top
    val color = if (item.state == SpatialState.Disabled) item.color.copy(alpha = .38f) else item.color
    when (val asset = item.asset) {
        is SpatialAsset.Wedge -> {
            val side = min(width, height)
            val thickness = side * (1f - asset.hollow.toFloat()) / 2f
            val inset = thickness / 2f
            drawArc(color, (asset.start * 360 - 90).toFloat(), (asset.sweep * 360).toFloat(), false,
                Offset(left + (width - side) / 2 + inset, top + (height - side) / 2 + inset),
                Size(side - thickness, side - thickness), style = Stroke(thickness))
        }
        is SpatialAsset.Glyph -> {
            val side = min(width, height)
            drawCircle(color.copy(alpha = .15f), side / 2, Offset(left + width / 2, top + height / 2))
            val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                this.color = color.toArgb(); textSize = side * .52f
                typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
                textAlign = Paint.Align.CENTER
            }
            drawContext.canvas.nativeCanvas.drawText(asset.letter.toString(), left + width / 2,
                top + height / 2 - (paint.ascent() + paint.descent()) / 2, paint)
        }
        is SpatialAsset.Catalogue -> {
            if (asset.name in setOf("bar", "surface", "button", "chip", "input", "dock", "heading")) {
                val radius = if (asset.name == "bar") 0f else min(width, height) * .28f
                drawRoundRect(color, Offset(left, top), Size(width, height), CornerRadius(radius))
                if (asset.name == "bar" && item.state == SpatialState.Selected) {
                    val edge = min(2.dp.toPx(), min(width, height) / 3f)
                    drawRect(Color.White.copy(alpha = .85f), Offset(left + edge / 2, top + edge / 2),
                        Size(width - edge, height - edge), style = Stroke(edge))
                }
            } else {
                val side = min(width, height)
                val pulse = sin(phase * PI).toFloat()
                val decorative = asset.name in setOf("orbit", "brand", "avatar")
                withTransform({
                    translate(left + (width - side) / 2, top + (height - side) / 2)
                    scale(side / 100f, side / 100f, Offset.Zero)
                    if (item.motionAllowed) {
                        translate(0f, if (decorative) -2f * pulse else 0f)
                        scale(1f + .035f * pulse, 1f + .035f * pulse, Offset(50f, 50f))
                    }
                }) { flatIcon(asset.name, color, phase, item.state) }
            }
        }
    }
}

private fun DrawScope.flatIcon(name: String, ink: Color, phase: Float, state: SpatialState) {
    val white = ink == Color.White
    val teal = if (white) ink else Color(0xFF16A99B)
    val violet = if (white) ink else Color(0xFF8065E8)
    val amber = if (white) ink else Color(0xFFEFAF43)
    val rose = if (white) ink else Color(0xFFE76E8E)
    val stroke = Stroke(6f, cap = StrokeCap.Round)
    fun line(a: Float, b: Float, c: Float, d: Float, color: Color = ink, width: Float = 6f) =
        drawLine(color, Offset(a, b), Offset(c, d), width, StrokeCap.Round)
    fun path(points: List<Pair<Float, Float>>, color: Color = ink, fill: Boolean = false, closed: Boolean = false) {
        val p = Path().apply {
            moveTo(points[0].first, points[0].second)
            points.drop(1).forEach { lineTo(it.first, it.second) }
            if (closed) close()
        }
        if (fill) drawPath(p, color) else drawPath(p, color, style = stroke)
    }
    fun box(x: Float, y: Float, w: Float, h: Float, color: Color = ink, fill: Boolean = false, radius: Float = 9f) {
        if (fill) drawRoundRect(color, Offset(x,y), Size(w,h), CornerRadius(radius))
        else drawRoundRect(color, Offset(x,y), Size(w,h), CornerRadius(radius), style = stroke)
    }
    fun circle(x: Float, y: Float, radius: Float, color: Color = ink, fill: Boolean = false) {
        if (fill) drawCircle(color, radius, Offset(x,y)) else drawCircle(color, radius, Offset(x,y), style = stroke)
    }
    fun check() = path(listOf(25f to 51f, 43f to 69f, 76f to 33f), teal)
    when (name) {
        "home" -> {
            path(listOf(15f to 45f,50f to 16f,85f to 45f), violet)
            box(25f,43f,50f,39f,ink.copy(alpha=.13f),true)
            path(listOf(25f to 46f,25f to 81f,75f to 81f,75f to 46f))
            box(43f,59f,16f,22f,teal,true,4f)
        }
        "portfolio" -> {
            box(17f,31f,66f,49f,ink.copy(alpha=.13f),true)
            box(17f,31f,66f,49f)
            box(35f,19f,30f,12f,violet,false,5f)
            line(20f,50f,80f,50f,teal); box(44f,45f,12f,15f,amber,true,3f)
        }
        "ideas" -> {
            circle(50f,40f,23f,amber,true)
            path(listOf(35f to 61f,39f to 70f,61f to 70f,65f to 61f),ink)
            line(41f,81f,59f,81f); line(50f,37f,50f,60f,violet)
            line(13f,38f,19f,38f,amber);line(81f,38f,87f,38f,amber);line(50f,7f,50f,12f,amber)
        }
        "pulse", "charts", "stock" -> {
            box(17f,53f,13f,30f,teal,true,4f)
            box(43f,39f,13f,44f,violet,true,4f)
            box(69f,22f,13f,61f,ink,true,4f)
            path(listOf(18f to 36f,39f to 21f,53f to 27f,77f to 12f),amber)
        }
        "messages" -> {
            box(16f,19f,68f,53f,violet.copy(alpha=.16f),true,16f)
            path(listOf(28f to 72f,28f to 86f,44f to 72f),violet)
            box(16f,19f,68f,53f,violet,false,16f)
            (0..2).forEach { circle(33f+17f*it,46f,4f,if(it==1)teal else ink,true) }
        }
        "education", "sources", "bond" -> {
            box(23f,15f,54f,70f,ink.copy(alpha=.12f),true)
            box(23f,15f,54f,70f)
            line(35f,34f,65f,34f,violet);line(35f,48f,65f,48f,teal);line(35f,62f,54f,62f)
            if(name=="education")path(listOf(40f to 15f,40f to 31f,48f to 26f,56f to 31f,56f to 15f),amber,true,true)
        }
        "profile" -> {
            circle(50f,31f,16f,violet,true)
            val p=Path().apply { moveTo(20f,83f); cubicTo(20f,43f,80f,43f,80f,83f);close() }
            drawPath(p,teal.copy(alpha=.22f)); drawPath(p,ink,style=stroke)
        }
        "risk", "warning", "error" -> {
            if(name=="risk") {
                path(listOf(50f to 12f,80f to 24f,77f to 57f,66f to 74f,50f to 86f,34f to 74f,23f to 57f,20f to 24f),amber.copy(alpha=.18f),true,true)
                path(listOf(50f to 12f,80f to 24f,77f to 57f,66f to 74f,50f to 86f,34f to 74f,23f to 57f,20f to 24f),amber,false,true)
            } else {
                path(listOf(50f to 14f,88f to 80f,12f to 80f),rose.copy(alpha=.15f),true,true)
                path(listOf(50f to 14f,88f to 80f,12f to 80f),rose,false,true)
            }
            line(50f,35f,50f,55f);circle(50f,68f,3.5f,ink,true)
        }
        "allocation", "fund" -> {
            drawArc(violet,0f,235f,false,Offset(20f,20f),Size(60f,60f),style=Stroke(15f))
            drawArc(teal,245f,70f,false,Offset(20f,20f),Size(60f,60f),style=Stroke(15f))
            drawArc(amber,325f,25f,false,Offset(20f,20f),Size(60f,60f),style=Stroke(15f))
        }
        "update" -> {
            drawArc(teal,25f,275f,false,Offset(17f,17f),Size(66f,66f),style=stroke)
            path(listOf(71f to 11f,73f to 31f,53f to 29f),teal)
            line(50f,37f,50f,65f,violet);path(listOf(38f to 54f,50f to 67f,62f to 54f),violet)
        }
        "avatar", "analyst" -> {
            box(18f,26f,64f,54f,violet.copy(alpha=.16f),true,20f)
            box(18f,26f,64f,54f,violet,false,20f)
            line(50f,16f,50f,25f,teal);circle(50f,12f,4f,amber,true)
            val blink = if(phase > .48f && phase < .56f) 1.5f else 4f
            drawOval(ink,Offset(31f,43f),Size(8f,blink*2))
            drawOval(ink,Offset(61f,43f),Size(8f,blink*2))
            if(state==SpatialState.Attention)line(41f,66f,59f,66f,rose)
            else drawArc(teal,20f,140f,false,Offset(38f,52f),Size(24f,16f),style=Stroke(4f,cap=StrokeCap.Round))
        }
        "brand", "orbit" -> {
            circle(50f,50f,36f,violet.copy(alpha=.13f),true)
            drawArc(violet,-70f+sin(phase*PI).toFloat()*25f,270f,false,Offset(9f,9f),Size(82f,82f),style=Stroke(3f))
            box(28f,50f,11f,20f,teal,true,4f);box(45f,38f,11f,32f,violet,true,4f);box(62f,26f,11f,44f,ink,true,4f)
            circle(83f,25f,7f,amber,true);circle(17f,77f,5f,rose,true)
            if(state==SpatialState.Loading) {
                drawArc(teal,phase*360f,85f,false,Offset(3f,3f),Size(94f,94f),style=Stroke(4f,cap=StrokeCap.Round))
            }
        }
        "notifications" -> {
            val p=Path().apply { moveTo(22f,70f);lineTo(29f,58f);lineTo(29f,39f);cubicTo(29f,10f,71f,10f,71f,39f);lineTo(71f,58f);lineTo(78f,70f);close() }
            drawPath(p,amber.copy(alpha=.22f));drawPath(p,ink,style=stroke);drawArc(violet,0f,180f,false,Offset(41f,75f),Size(18f,12f),style=stroke)
            circle(76f,24f,9f,rose,true)
        }
        "market", "globe" -> {
            circle(50f,50f,34f,teal.copy(alpha=.10f),true);circle(50f,50f,34f,teal)
            drawOval(violet,Offset(35f,16f),Size(30f,68f),style=Stroke(4f))
            line(18f,50f,82f,50f,teal,4f);line(24f,33f,76f,33f,teal,3f);line(24f,67f,76f,67f,teal,3f)
        }
        "goal" -> {
            circle(49f,52f,32f,violet);circle(49f,52f,18f,teal);circle(49f,52f,5f,teal,true)
            line(49f,52f,80f,20f,amber);path(listOf(65f to 20f,80f to 20f,80f to 35f),amber)
        }
        "settings" -> {
            repeat(8) { i ->
                val angle=i*PI/4
                line(50f+27f*cos(angle).toFloat(),50f+27f*sin(angle).toFloat(),
                    50f+37f*cos(angle).toFloat(),50f+37f*sin(angle).toFloat(),violet,9f)
            }
            circle(50f,50f,26f,violet);circle(50f,50f,10f,teal)
        }
        "calendar" -> {
            box(18f,24f,64f,59f);line(18f,42f,82f,42f,violet)
            line(34f,16f,34f,31f,violet);line(66f,16f,66f,31f,violet)
            box(30f,52f,13f,13f,teal,true,3f);line(54f,57f,69f,57f);line(32f,73f,68f,73f)
        }
        "bookmark" -> path(listOf(29f to 16f,71f to 16f,71f to 84f,50f to 68f,29f to 84f),violet,false,true)
        "currency" -> {
            circle(50f,50f,35f,amber.copy(alpha=.15f),true);circle(50f,50f,35f,amber)
            path(listOf(39f to 76f,39f to 27f,55f to 27f,65f to 33f,65f to 44f,55f to 51f,32f to 51f))
            line(32f,63f,58f,63f)
        }
        "check" -> check()
        "search" -> {circle(43f,42f,24f);line(62f,61f,82f,81f,teal)}
        "back" -> {line(21f,50f,81f,50f);path(listOf(44f to 25f,20f to 50f,44f to 75f))}
        "forward", "arrow" -> {line(19f,50f,79f,50f);path(listOf(56f to 25f,80f to 50f,56f to 75f))}
        "close" -> {line(28f,28f,72f,72f);line(72f,28f,28f,72f)}
        "plus" -> {line(24f,50f,76f,50f);line(50f,24f,50f,76f)}
        "minus" -> line(24f,50f,76f,50f)
        "monogram" -> circle(50f,50f,32f,ink,true)
        else -> {circle(50f,50f,30f,ink);circle(50f,50f,10f,teal,true)}
    }
}
