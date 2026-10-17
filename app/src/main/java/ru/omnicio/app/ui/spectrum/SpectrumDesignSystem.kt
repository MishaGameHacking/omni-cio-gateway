package ru.omnicio.app.ui.spectrum

import ru.omnicio.app.ui.workspace.LocalWorkspacePreferences
import ru.omnicio.app.ui.workspace.InterfaceDensity
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

@Immutable
data class SpectrumPalette(
    val backgroundTop: Color,
    val backgroundBottom: Color,
    val card: Color,
    val cardStrong: Color,
    val cyan: Color,
    val blue: Color,
    val violet: Color,
    val rose: Color,
    val emerald: Color,
    val amber: Color,
)

val DarkSpectrumPalette = SpectrumPalette(
    backgroundTop = Color(0xFF090E18),
    backgroundBottom = Color(0xFF111827),
    card = Color(0xFF121D2B),
    cardStrong = Color(0xFF192A3B),
    cyan = Color(0xFF70E0D2),
    blue = Color(0xFF4C8DFF),
    violet = Color(0xFF8A5CFF),
    rose = Color(0xFFFF4FA3),
    emerald = Color(0xFF19E6A2),
    amber = Color(0xFFFFC857),
)

val LightSpectrumPalette = SpectrumPalette(
    backgroundTop = Color(0xFFF5F8FF),
    backgroundBottom = Color(0xFFEAF2FF),
    card = Color.White,
    cardStrong = Color(0xFFE7F1FF),
    cyan = Color(0xFF007C91),
    blue = Color(0xFF205FCF),
    violet = Color(0xFF6E43C8),
    rose = Color(0xFFA92A70),
    emerald = Color(0xFF007D63),
    amber = Color(0xFF8A5A00),
)

val LocalSpectrumPalette = staticCompositionLocalOf { DarkSpectrumPalette }

// White labels retain >=4.5:1 contrast over every interpolated stop. Bright
// cyan is reserved for the surrounding glow, never a white-text background.
internal val SpectrumPrimaryStops = listOf(
    Color(0xFF3158D5), Color(0xFF5036DA), Color(0xFF7136BF),
)

@Composable
fun SpectrumBackground(modifier: Modifier = Modifier, content: @Composable BoxScope.() -> Unit) {
    val palette = LocalSpectrumPalette.current
    val dark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val starColor = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.11f)
    Box(modifier.background(Brush.verticalGradient(
        if (dark) listOf(palette.backgroundTop, Color(0xFF0C1420), palette.backgroundBottom, palette.backgroundTop)
        else listOf(palette.backgroundTop, palette.backgroundBottom, Color(0xFFF8FAFF)),
    ))) {
        Canvas(Modifier.fillMaxSize()) {
            if (size.minDimension <= 0f) return@Canvas
            val radius = size.minDimension
            val glows = listOf(
                Triple(Offset(size.width * 0.92f, size.height * 0.06f), 0.82f, palette.violet.copy(alpha = if (dark) 0.11f else 0.06f)),
                Triple(Offset(size.width * 0.02f, size.height * 0.74f), 0.72f, palette.cyan.copy(alpha = if (dark) 0.08f else 0.04f)),
                Triple(Offset(size.width * 0.70f, size.height * 0.62f), 0.55f, palette.rose.copy(alpha = if (dark) 0.08f else 0.035f)),
            )
            glows.forEach { (center, factor, color) ->
                drawCircle(Brush.radialGradient(listOf(color, Color.Transparent), center, radius * factor), radius * factor, center)
            }
            if (dark) repeat(8) { index ->
                drawCircle(starColor, if (index % 5 == 0) 1.8f else 1f,
                    Offset(((index * 73) % 101) / 100f * size.width, ((index * 41 + 17) % 97) / 100f * size.height))
            }
        }
        content()
    }
}

@Composable
fun SpectrumCard(
    modifier: Modifier = Modifier,
    emphasized: Boolean = false,
    onClick: (() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    val palette = LocalSpectrumPalette.current
    val dark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    val prefs = LocalWorkspacePreferences.current.value
    val shape = RoundedCornerShape(28.dp)
    val interaction = if (onClick == null) Modifier else Modifier.clip(shape).clickable(role = Role.Button, onClick = onClick)
    Card(
        modifier = modifier.then(interaction),
        shape = shape,
        colors = CardDefaults.cardColors(
            containerColor = when {
                emphasized && dark -> palette.cardStrong.copy(alpha = 0.96f)
                dark -> palette.card.copy(alpha = 0.93f)
                emphasized -> palette.cardStrong
                else -> palette.card
            },
            contentColor = MaterialTheme.colorScheme.onSurface,
        ),
        border = BorderStroke(1.dp, Brush.linearGradient(listOf(
            palette.cyan.copy(alpha = if (emphasized) 0.42f else 0.09f),
            palette.blue.copy(alpha = if (emphasized) 0.24f else 0.08f),
            palette.violet.copy(alpha = if (emphasized) 0.42f else 0.09f),
            palette.rose.copy(alpha = if (emphasized) 0.18f else 0.06f),
        ))),
        elevation = CardDefaults.cardElevation(defaultElevation = if (prefs.depth) 3.dp else 0.dp),
    ) {
        Column(Modifier.fillMaxWidth().padding(if (prefs.density == InterfaceDensity.COMPACT) 14.dp else 20.dp), verticalArrangement = Arrangement.spacedBy(10.dp), content = content)
    }
}

@Composable
fun SpectrumBadge(text: String, modifier: Modifier = Modifier, accent: Color = LocalSpectrumPalette.current.cyan) {
    Surface(modifier = modifier, shape = RoundedCornerShape(999.dp), color = accent.copy(alpha = 0.14f),
        contentColor = MaterialTheme.colorScheme.onSurface, border = BorderStroke(1.dp, accent.copy(alpha = 0.40f))) {
        Text(text, Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
            style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
fun SpectrumPageHeader(
    title: String,
    subtitle: String,
    symbol: SpectrumSymbol,
    modifier: Modifier = Modifier,
    @Suppress("UNUSED_PARAMETER") eyebrow: String = "Analyst AI",
) {
    Row(modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(title, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            if (subtitle.isNotBlank()) Text(subtitle, color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodyMedium)
        }
        SpectrumIcon(symbol, Modifier.size(44.dp), selected = true, tile = true, motionAllowed = false)
    }
}

@Composable
fun SpectrumPrimaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    symbol: SpectrumSymbol? = null,
) {
    val colors = MaterialTheme.colorScheme
    val brush = Brush.horizontalGradient(if (enabled) SpectrumPrimaryStops else listOf(colors.surfaceVariant, colors.surfaceVariant))
    val labelColor = if (enabled) Color.White else colors.onSurfaceVariant
    Surface(onClick = onClick, enabled = enabled, modifier = modifier, color = Color.Transparent,
        contentColor = labelColor, shape = RoundedCornerShape(18.dp)) {
        Row(
            Modifier.fillMaxWidth().heightIn(min = 54.dp).background(brush).padding(horizontal = 18.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.Center,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (symbol != null) {
                SpectrumIcon(symbol, Modifier.size(26.dp), selected = true, tile = false, motionAllowed = false)
                Spacer(Modifier.width(9.dp))
            }
            Text(text, color = labelColor, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
        }
    }
}

@Composable
fun SpectrumSecondaryButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) {
    val palette = LocalSpectrumPalette.current
    Surface(onClick = onClick, enabled = enabled, modifier = modifier, shape = RoundedCornerShape(18.dp),
        color = palette.cardStrong.copy(alpha = if (enabled) 0.78f else 0.45f),
        contentColor = MaterialTheme.colorScheme.onSurface, border = BorderStroke(1.dp, palette.blue.copy(alpha = 0.40f))) {
        Box(Modifier.fillMaxWidth().heightIn(min = 52.dp).padding(horizontal = 16.dp, vertical = 12.dp), contentAlignment = Alignment.Center) {
            Text(text, fontWeight = FontWeight.SemiBold, textAlign = TextAlign.Center)
        }
    }
}

@Composable
fun SpectrumActionTile(
    title: String,
    subtitle: String,
    symbol: SpectrumSymbol,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    accent: Color = LocalSpectrumPalette.current.cyan,
) {
    SpectrumCard(modifier = modifier, onClick = onClick) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Surface(Modifier.size(48.dp), shape = RoundedCornerShape(16.dp), color = accent.copy(alpha = 0.14f),
                border = BorderStroke(1.dp, accent.copy(alpha = 0.35f))) {
                SpectrumIcon(symbol, Modifier.padding(8.dp), selected = true, tile = false, motionAllowed = false)
            }
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(title, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                Text(subtitle, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
fun SpectrumMetricPill(label: String, value: String, modifier: Modifier = Modifier, accent: Color = LocalSpectrumPalette.current.blue) {
    Surface(modifier, shape = RoundedCornerShape(18.dp), color = accent.copy(alpha = 0.12f),
        contentColor = MaterialTheme.colorScheme.onSurface, border = BorderStroke(1.dp, accent.copy(alpha = 0.26f))) {
        Column(Modifier.padding(horizontal = 14.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(value, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
            Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelSmall)
        }
    }
}

@Composable
fun SpectrumProgressBar(fraction: Float, modifier: Modifier = Modifier, accent: Color = LocalSpectrumPalette.current.cyan) {
    if (!fraction.isFinite()) return
    val progress = fraction.coerceIn(0f, 1f)
    Box(modifier.fillMaxWidth().height(8.dp).clip(CircleShape).background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.62f))) {
        Box(Modifier.fillMaxWidth(progress).fillMaxHeight().background(
            Brush.horizontalGradient(listOf(accent.copy(alpha = 0.75f), accent, LocalSpectrumPalette.current.violet)),
        ))
    }
}

/** Original vector brain mark, rendered by Compose rather than a mockup image. */
@Composable
fun SpectrumBrandOrb(modifier: Modifier = Modifier, compact: Boolean = false) {
    val palette = LocalSpectrumPalette.current
    val dark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    Canvas(modifier.aspectRatio(1f)) {
        if (size.minDimension <= 0f) return@Canvas
        val unit = size.minDimension / 128f
        withTransform({
            translate((size.width - size.minDimension) / 2f, (size.height - size.minDimension) / 2f)
            scale(unit, unit, Offset.Zero)
        }) {
            val center = Offset(64f, 64f)
            drawCircle(Brush.radialGradient(listOf(palette.cyan.copy(alpha = if (dark) 0.26f else 0.12f),
                palette.violet.copy(alpha = 0.10f), Color.Transparent), center, 63f), 63f, center)
            if (!compact) {
                drawCircle(Brush.radialGradient(listOf(palette.cardStrong, palette.backgroundTop.copy(alpha = 0.2f)),
                    Offset(46f, 39f), 74f), 46f, center)
                drawCircle(palette.blue.copy(alpha = 0.35f), 47f, center, style = Stroke(1f))
                drawArc(palette.cyan.copy(alpha = 0.60f), 195f, 240f, false, Offset(4f, 44f), Size(120f, 40f),
                    style = Stroke(1.5f, cap = StrokeCap.Round))
                drawArc(palette.violet.copy(alpha = 0.65f), 18f, 220f, false, Offset(41f, 4f), Size(46f, 120f),
                    style = Stroke(1.5f, cap = StrokeCap.Round))
                drawCircle(palette.cyan, 2f, Offset(112f, 52f))
                drawCircle(palette.rose, 1.5f, Offset(35f, 103f))
            }
            withTransform({ if (!compact) scale(0.72f, 0.72f, center) }) {
                val hemisphere = Path().apply {
                    moveTo(61f, 27f)
                    cubicTo(59f, 16f, 46f, 15f, 40f, 23f)
                    cubicTo(28f, 20f, 19f, 30f, 22f, 42f)
                    cubicTo(9f, 46f, 9f, 62f, 18f, 69f)
                    cubicTo(13f, 84f, 21f, 96f, 33f, 98f)
                    cubicTo(39f, 112f, 57f, 110f, 61f, 100f)
                    lineTo(61f, 27f)
                    moveTo(39f, 24f); cubicTo(48f, 32f, 39f, 38f, 35f, 39f)
                    moveTo(23f, 43f); cubicTo(39f, 40f, 46f, 48f, 41f, 58f)
                    moveTo(18f, 69f); cubicTo(28f, 64f, 37f, 74f, 35f, 86f)
                    moveTo(33f, 98f); cubicTo(34f, 86f, 45f, 82f, 50f, 91f)
                    moveTo(61f, 45f); cubicTo(51f, 44f, 48f, 52f, 53f, 60f)
                    moveTo(61f, 76f); cubicTo(53f, 73f, 46f, 72f, 43f, 65f)
                    cubicTo(35f, 65f, 29f, 57f, 31f, 51f)
                }
                val sides = listOf(palette.cyan, palette.violet)
                sides.forEachIndexed { index, color ->
                    withTransform({ if (index == 1) scale(-1f, 1f, center) }) {
                        if (dark) {
                            drawPath(hemisphere, color.copy(alpha = 0.10f), style = Stroke(11f, cap = StrokeCap.Round, join = StrokeJoin.Round))
                            drawPath(hemisphere, color.copy(alpha = 0.18f), style = Stroke(6f, cap = StrokeCap.Round, join = StrokeJoin.Round))
                        }
                        drawPath(hemisphere, color, style = Stroke(2.5f, cap = StrokeCap.Round, join = StrokeJoin.Round))
                        listOf(Offset(35f, 39f), Offset(53f, 60f), Offset(50f, 91f)).forEach { point -> drawCircle(color, 2.5f, point) }
                    }
                }
            }
        }
    }
}

