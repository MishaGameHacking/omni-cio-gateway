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
import ru.omnicio.app.ui.spectrum.SpectrumPalette
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.sin

/** Original vector artwork. All proportions are logical units, never downloaded images. */
private data class FlatBounds(val width: Float, val height: Float, val left: Float, val top: Float)

internal fun DrawScope.drawFlatPrimitive(item: SpatialPrimitive, phase: Float, palette: SpectrumPalette) {
    val rect = item.rect
    val bounds = FlatBounds(size.width * rect.width, size.height * rect.height,
        size.width * rect.left, size.height * rect.top)
    if (bounds.width <= 0f || bounds.height <= 0f) return
    when (val asset = item.asset) {
        is SpatialAsset.Wedge -> drawFlatWedge(asset, item, palette, bounds)
        is SpatialAsset.Glyph -> drawFlatGlyph(asset, item, palette, bounds)
        is SpatialAsset.Catalogue -> drawFlatCatalogue(asset, item, phase, palette, bounds)
    }
}

private fun DrawScope.drawFlatWedge(asset: SpatialAsset.Wedge, item: SpatialPrimitive,
    palette: SpectrumPalette, bounds: FlatBounds) {
    val (width, height, left, top) = bounds
    val color = item.color
    val side = min(width, height)
    val thickness = side * (1f - asset.hollow.toFloat()) / 2f
    val inset = thickness / 2f
    drawArc(color, (asset.start * 360 - 90).toFloat(), (asset.sweep * 360).toFloat(), false,
        Offset(left + (width - side) / 2 + inset, top + (height - side) / 2 + inset),
        Size(side - thickness, side - thickness), style = Stroke(thickness))
    val center = Offset(left + width / 2, top + height / 2)
    val inner = side * asset.hollow.toFloat() / 2
    val outer = side / 2
    if (asset.sweep < 1.0) {
        for (fraction in listOf(asset.start, asset.start + asset.sweep)) {
            val angle = (fraction * 360 - 90) * PI / 180
            val direction = Offset(cos(angle).toFloat(), sin(angle).toFloat())
            drawLine(palette.semantic.chartSeparator, center + direction * inner,
                center + direction * outer, strokeWidth = min(1.dp.toPx(), thickness / 4))
        }
    }
    if (item.state == SpatialState.Selected) {
        val edge = min(1.5.dp.toPx(), thickness / 4)
        fun outline(radius: Float, ink: Color) {
            drawArc(ink, (asset.start * 360 - 90).toFloat(), (asset.sweep * 360).toFloat(), false,
                center - Offset(radius, radius), Size(radius * 2, radius * 2), style = Stroke(edge))
        }
        // Every stroke is inside the original annulus and exact angular interval.
        outline(outer - edge / 2, palette.semantic.chartSelectedOuter)
        outline(outer - edge * 1.5f, palette.semantic.chartSelectedInner)
        outline(inner + edge / 2, palette.semantic.chartSelectedOuter)
        outline(inner + edge * 1.5f, palette.semantic.chartSelectedInner)
    }

}

private fun DrawScope.drawFlatGlyph(asset: SpatialAsset.Glyph, item: SpatialPrimitive,
    palette: SpectrumPalette, bounds: FlatBounds) {
    val (width, height, left, top) = bounds
    val artwork = flatArtworkColors(palette, item.color, item.colorMode, item.state)
    val side = min(width, height)
    drawCircle(artwork.ink.copy(alpha = .15f), side / 2, Offset(left + width / 2, top + height / 2))
    val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        this.color = artwork.ink.toArgb(); textSize = side * .52f
        typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
        textAlign = Paint.Align.CENTER
    }
    drawContext.canvas.nativeCanvas.drawText(asset.letter.toString(), left + width / 2,
        top + height / 2 - (paint.ascent() + paint.descent()) / 2, paint)

}

private fun DrawScope.drawFlatCatalogue(asset: SpatialAsset.Catalogue, item: SpatialPrimitive,
    phase: Float, palette: SpectrumPalette, bounds: FlatBounds) {
    if (asset.name in setOf("bar", "surface", "button", "chip", "input", "dock", "heading"))
        drawFlatSurface(asset, item, palette, bounds)
    else drawFlatCatalogueIcon(asset, item, phase, palette, bounds)
}

private fun DrawScope.drawFlatSurface(asset: SpatialAsset.Catalogue, item: SpatialPrimitive,
    palette: SpectrumPalette, bounds: FlatBounds) {
    val (width, height, left, top) = bounds
    val color = item.color
    val radius = if (asset.name == "bar") 0f else min(width, height) * .28f
    drawRoundRect(color, Offset(left, top), Size(width, height), CornerRadius(radius))
    if (item.outlineColor != Color.Unspecified) {
        val edge = min(1.dp.toPx(), min(width, height) / 4)
        drawRoundRect(item.outlineColor, Offset(left + edge / 2, top + edge / 2),
            Size(width - edge, height - edge), CornerRadius((radius - edge / 2).coerceAtLeast(0f)),
            style = Stroke(edge))
    }
    if (asset.name == "bar" && item.state == SpatialState.Selected) {
        val edge = min(1.5.dp.toPx(), min(width, height) / 5f)
        drawRect(palette.semantic.chartSelectedOuter, Offset(left + edge / 2, top + edge / 2),
            Size(width - edge, height - edge), style = Stroke(edge))
        drawRect(palette.semantic.chartSelectedInner, Offset(left + edge * 1.5f, top + edge * 1.5f),
            Size(width - edge * 3, height - edge * 3), style = Stroke(edge))
    }

}

private fun DrawScope.drawFlatCatalogueIcon(asset: SpatialAsset.Catalogue, item: SpatialPrimitive,
    phase: Float, palette: SpectrumPalette, bounds: FlatBounds) {
    val (width, height, left, top) = bounds
    val artwork = flatArtworkColors(palette, item.color, item.colorMode, item.state)
    val side = min(width, height)
    val pulse = ((1.0 - cos(phase * PI * 2.0)) / 2.0).toFloat()
    val decorative = asset.name in setOf("orbit", "brand", "avatar")
    withTransform({
        translate(left + (width - side) / 2, top + (height - side) / 2)
        scale(side / 100f, side / 100f, Offset.Zero)
        if (item.motionAllowed) {
            translate(0f, if (decorative) -2f * pulse else 0f)
            scale(1f + .035f * pulse, 1f + .035f * pulse, Offset(50f, 50f))
        }
    }) {
        if (item.colorMode == SpatialColorMode.Decorative && item.state != SpatialState.Disabled)
            clayIcon(asset.name, phase, item.state)
        else flatIcon(asset.name, artwork, phase, item.state, item.outlineColor)
    }

}

internal fun DrawScope.flatIcon(name: String, colors: FlatArtworkColors, phase: Float,
    state: SpatialState, outline: Color) {
    FlatIconPainter(this, colors, phase, state, outline).draw(name)
}

private class FlatIconPainter(
    scope: DrawScope,
    private val colors: FlatArtworkColors,
    private val phase: Float,
    private val state: SpatialState,
    private val outline: Color,
) : DrawScope by scope {
    private val ink = colors.ink
    private val teal = colors.teal
    private val violet = colors.violet
    private val amber = colors.amber
    private val rose = colors.rose
    private val stroke = Stroke(6f, cap = StrokeCap.Round)
    private fun line(a: Float, b: Float, c: Float, d: Float, color: Color = ink, width: Float = 6f) =
        drawLine(color, Offset(a, b), Offset(c, d), width, StrokeCap.Round)
    private fun path(points: List<Pair<Float, Float>>, color: Color = ink, fill: Boolean = false, closed: Boolean = false) {
        val p = Path().apply {
            moveTo(points[0].first, points[0].second)
            points.drop(1).forEach { lineTo(it.first, it.second) }
            if (closed) close()
        }
        if (fill) drawPath(p, color) else drawPath(p, color, style = stroke)
    }
    private fun box(x: Float, y: Float, w: Float, h: Float, color: Color = ink, fill: Boolean = false, radius: Float = 9f) {
        if (fill) drawRoundRect(color, Offset(x,y), Size(w,h), CornerRadius(radius))
        else drawRoundRect(color, Offset(x,y), Size(w,h), CornerRadius(radius), style = stroke)
    }
    private fun circle(x: Float, y: Float, radius: Float, color: Color = ink, fill: Boolean = false) {
        if (fill) drawCircle(color, radius, Offset(x,y)) else drawCircle(color, radius, Offset(x,y), style = stroke)
    }
    private fun check() = path(listOf(25f to 51f, 43f to 69f, 76f to 33f), ink)

    fun draw(name: String) {
        if (drawWorkspaceSymbols(name) || drawAppearanceSymbols(name) || drawNavigationSymbols(name) || drawAnalysisSymbols(name) || drawMarketSymbols(name) || drawUtilitySymbols(name) || drawControlSymbols(name) || drawStrategySymbols(name)) return
        circle(50f, 50f, 30f, ink); circle(50f, 50f, 10f, teal, true)
    }

    private fun drawWorkspaceSymbols(name: String): Boolean {
        when (name) {
            "brain" -> {
                val left = Path().apply {
                    moveTo(46f, 18f); cubicTo(31f, 9f, 20f, 20f, 23f, 31f)
                    cubicTo(8f, 33f, 8f, 50f, 18f, 57f)
                    cubicTo(11f, 71f, 27f, 85f, 39f, 78f)
                    cubicTo(43f, 87f, 49f, 83f, 49f, 73f); lineTo(49f, 27f)
                    cubicTo(49f, 22f, 49f, 19f, 46f, 18f); close()
                }
                drawPath(left, teal.copy(alpha=.18f)); drawPath(left, teal, style=Stroke(5f,cap=StrokeCap.Round))
                withTransform({ translate(100f,0f); scale(-1f,1f,Offset.Zero) }) {
                    drawPath(left, violet.copy(alpha=.18f)); drawPath(left, violet, style=Stroke(5f,cap=StrokeCap.Round))
                }
                path(listOf(23f to 31f,35f to 37f,35f to 47f),teal)
                path(listOf(18f to 57f,29f to 54f,37f to 62f),teal)
                path(listOf(77f to 31f,65f to 37f,65f to 47f),violet)
                path(listOf(82f to 57f,71f to 54f,63f to 62f),violet)
                circle(50f,49f,5f,amber,true)
            }
            "decisions" -> {
                box(24f,17f,53f,67f,ink.copy(alpha=.12f),true);box(24f,17f,53f,67f,violet)
                box(38f,11f,25f,13f,teal,true,4f)
                path(listOf(34f to 50f,45f to 61f,68f to 37f),teal)
                line(37f,73f,62f,73f,ink,4f)
            }
            "strategy" -> {
                line(50f,78f,50f,49f,teal);line(50f,49f,25f,30f,violet);line(50f,49f,76f,29f,amber)
                circle(50f,79f,9f,teal,true);box(15f,13f,21f,21f,violet,false,5f)
                path(listOf(66f to 16f,83f to 16f,83f to 33f),amber)
            }
            "reports" -> {
                path(listOf(23f to 13f,60f to 13f,78f to 31f,78f to 85f,23f to 85f),ink,false,true)
                path(listOf(60f to 14f,60f to 32f,77f to 32f),violet)
                line(34f,70f,34f,57f,teal,7f);line(49f,70f,49f,45f,violet,7f);line(64f,70f,64f,53f,amber,7f)
            }
            "timeline" -> {
                line(24f,20f,24f,82f,violet,4f)
                for (y in listOf(24f,50f,77f)) { circle(24f,y,6f,teal,true);line(39f,y,76f,y,ink,5f) }
                line(39f,34f,59f,34f,violet,3f);line(39f,60f,68f,60f,violet,3f)
            }
            "events" -> {
                box(17f,23f,66f,59f,ink.copy(alpha=.12f),true);box(17f,23f,66f,59f,violet)
                line(32f,15f,32f,31f,teal);line(68f,15f,68f,31f,teal);line(19f,39f,81f,39f,violet,4f)
                path(listOf(52f to 45f,40f to 62f,53f to 62f,45f to 76f,67f to 56f,54f to 56f),amber,true,true)
            }
            else -> return false
        }
        return true
    }

    private fun drawAppearanceSymbols(name: String): Boolean {
        when (name) {
            "rules" -> {
                line(23f,15f,23f,84f,violet,4f);line(50f,15f,50f,84f,teal,4f);line(77f,15f,77f,84f,violet,4f)
                box(15f,30f,16f,14f,teal,true,5f);box(42f,57f,16f,14f,amber,true,5f);box(69f,23f,16f,14f,ink,true,5f)
            }
            "appearance" -> {
                val palette = Path().apply { moveTo(51f,14f);cubicTo(7f,11f,5f,74f,40f,84f)
                    cubicTo(64f,91f,48f,66f,64f,62f);cubicTo(93f,68f,92f,17f,51f,14f);close() }
                drawPath(palette, violet.copy(alpha=.18f));drawPath(palette,ink,style=stroke)
                circle(31f,34f,6f,teal,true);circle(51f,27f,6f,violet,true)
                circle(71f,36f,6f,amber,true);circle(26f,56f,6f,rose,true)
            }
            "devices" -> {
                box(13f,21f,54f,40f,violet,false,5f);line(39f,61f,39f,75f,violet);line(25f,77f,51f,77f,violet)
                box(59f,36f,26f,49f,teal,true,5f);box(63f,41f,18f,32f,ink.copy(alpha=.25f),true,2f)
                circle(72f,79f,2f,ink,true)
            }
            "recent" -> {
                drawArc(violet,215f,295f,false,Offset(18f,18f),Size(65f,65f),style=stroke)
                path(listOf(14f to 22f,15f to 43f,35f to 40f),teal)
                path(listOf(51f to 31f,51f to 52f,66f to 61f),teal)
            }
            "new_features" -> {
                path(listOf(50f to 12f,60f to 38f,87f to 49f,60f to 59f,50f to 86f,40f to 59f,13f to 49f,40f to 38f),violet,true,true)
                path(listOf(79f to 12f,82f to 20f,91f to 23f,82f to 26f,79f to 34f,76f to 26f,68f to 23f,76f to 20f),teal,true,true)
                circle(21f,78f,5f,amber,true)
            }
            "home" -> {
                path(listOf(15f to 45f,50f to 16f,85f to 45f), violet)
                box(25f,43f,50f,39f,ink.copy(alpha=.13f),true)
                path(listOf(25f to 46f,25f to 81f,75f to 81f,75f to 46f))
                box(43f,59f,16f,22f,teal,true,4f)
            }
            else -> return false
        }
        return true
    }

    private fun drawNavigationSymbols(name: String): Boolean {
        when (name) {
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
            else -> return false
        }
        return true
    }

    private fun drawAnalysisSymbols(name: String): Boolean {
        when (name) {
            "risk", "warning", "error" -> {
                if(name=="risk") {
                    path(listOf(50f to 12f,80f to 24f,77f to 57f,66f to 74f,50f to 86f,34f to 74f,23f to 57f,20f to 24f),amber.copy(alpha=.18f),true,true)
                    path(listOf(50f to 12f,80f to 24f,77f to 57f,66f to 74f,50f to 86f,34f to 74f,23f to 57f,20f to 24f),amber,false,true)
                } else {
                    val warning = if (name == "error") rose else amber
                    path(listOf(50f to 14f,88f to 80f,12f to 80f),warning.copy(alpha=.15f),true,true)
                    path(listOf(50f to 14f,88f to 80f,12f to 80f),warning,false,true)
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
                if(state==SpatialState.Attention)line(41f,66f,59f,66f,amber)
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
            else -> return false
        }
        return true
    }

    private fun drawMarketSymbols(name: String): Boolean {
        when (name) {
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
            else -> return false
        }
        return true
    }

    private fun drawUtilitySymbols(name: String): Boolean {
        when (name) {
            "check" -> check()
            "search" -> {circle(43f,42f,24f);line(62f,61f,82f,81f,teal)}
            "back" -> {line(21f,50f,81f,50f);path(listOf(44f to 25f,20f to 50f,44f to 75f))}
            "forward", "arrow" -> {line(19f,50f,79f,50f);path(listOf(56f to 25f,80f to 50f,56f to 75f))}
            "close" -> {line(28f,28f,72f,72f);line(72f,28f,28f,72f)}
            "plus" -> {line(24f,50f,76f,50f);line(50f,24f,50f,76f)}
            else -> return false
        }
        return true
    }

    private fun drawControlSymbols(name: String): Boolean {
        when (name) {
            "minus" -> line(24f,50f,76f,50f)
            "chevron_down" -> path(listOf(26f to 38f, 50f to 62f, 74f to 38f))
            "chevron_up" -> path(listOf(26f to 62f, 50f to 38f, 74f to 62f))
            "capital" -> {
                path(listOf(50f to 12f,80f to 24f,76f to 58f,66f to 74f,50f to 86f,34f to 74f,24f to 58f,20f to 24f),teal,true,true)
                path(listOf(35f to 49f,46f to 61f,67f to 35f),colors.highlight)
            }
            "income" -> {
                box(19f,22f,62f,59f,colors.highlight,true)
                box(19f,22f,62f,18f,teal,true,5f)
                circle(51f,61f,16f,amber,true)
                line(51f,50f,51f,71f,colors.highlight,4f);line(42f,58f,59f,58f,colors.highlight,4f)
            }
            "balanced" -> {
                line(50f,19f,50f,80f,violet,8f);line(25f,81f,75f,81f,violet,8f)
                line(19f,32f,81f,32f,teal,6f)
                path(listOf(25f to 34f,12f to 62f,38f to 62f),amber,true,true)
                path(listOf(75f to 34f,62f to 62f,88f to 62f),teal,true,true)
                circle(50f,23f,7f,amber,true)
            }
            else -> return false
        }
        return true
    }

    private fun drawStrategySymbols(name: String): Boolean {
        when (name) {
            "growth" -> {
                box(18f,60f,14f,23f,teal,true,4f);box(42f,45f,14f,38f,violet,true,4f)
                box(66f,31f,14f,52f,teal,true,4f)
                path(listOf(17f to 44f,40f to 26f,52f to 32f,79f to 12f),amber)
                path(listOf(62f to 12f,79f to 12f,79f to 28f),amber)
            }
            "dividends" -> {
                box(20f,68f,60f,14f,amber,true,7f)
                box(28f,52f,52f,14f,amber,true,7f)
                line(49f,54f,49f,20f,teal,6f)
                drawOval(teal,Offset(23f,18f),Size(25f,16f))
                drawOval(violet,Offset(51f,10f),Size(27f,20f))
            }
            "monogram" -> {
                circle(50f,50f,32f,ink,true)
                if (outline != Color.Unspecified) drawCircle(outline, 30f, Offset(50f,50f), style = Stroke(4f))
            }
            else -> return false
        }
        return true
    }
}
