package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Native Analyst AI design tokens. Financial meaning never depends on RGB decoration. */
@Immutable
data class SpectrumPalette(
    val backgroundTop: Color, val backgroundBottom: Color,
    val card: Color, val cardStrong: Color,
    val cyan: Color, val blue: Color, val violet: Color,
    val rose: Color, val emerald: Color, val amber: Color,
)

val DarkSpectrumPalette = SpectrumPalette(
    backgroundTop = Color(0xFF030C17), backgroundBottom = Color(0xFF071827),
    card = Color(0xFF071C2B), cardStrong = Color(0xFF0B2C41),
    cyan = Color(0xFF35DDFF), blue = Color(0xFF548BFF), violet = Color(0xFFA18AFF),
    rose = Color(0xFFFF7ABD), emerald = Color(0xFF18E2AC), amber = Color(0xFFFFCC66),
)
val LightSpectrumPalette = SpectrumPalette(
    backgroundTop = Color(0xFFF3F7FF), backgroundBottom = Color(0xFFEAF2FF),
    card = Color.White, cardStrong = Color(0xFFE6F1FF),
    cyan = Color(0xFF006B80), blue = Color(0xFF235AD3), violet = Color(0xFF663BC1),
    rose = Color(0xFFA62669), emerald = Color(0xFF006C50), amber = Color(0xFF845500),
)
val LocalSpectrumPalette = staticCompositionLocalOf { DarkSpectrumPalette }

@Composable
fun SpectrumBackground(modifier: Modifier = Modifier, content: @Composable BoxScope.() -> Unit) {
    val palette = LocalSpectrumPalette.current
    val dark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    Box(modifier.background(Brush.verticalGradient(listOf(palette.backgroundTop, palette.backgroundBottom, palette.backgroundTop)))) {
        Canvas(Modifier.fillMaxSize()) {
            if (size.minDimension <= 0f) return@Canvas
            val radius = size.minDimension * 0.72f
            val center = Offset(size.width * 0.95f, size.height * 0.12f)
            drawCircle(Brush.radialGradient(listOf(palette.blue.copy(alpha = if (dark) .10f else .05f), Color.Transparent), center, radius), radius, center)
            if (dark) {
                repeat(18) { index ->
                    val x = ((index * 37 + 11) % 101) / 101f * size.width
                    val y = ((index * 53 + 7) % 103) / 103f * size.height
                    drawCircle(palette.cyan.copy(alpha = .12f), .7.dp.toPx(), Offset(x, y))
                }
            }
        }
        content()
    }
}

@Composable
fun SpectrumCard(
    modifier: Modifier = Modifier, emphasized: Boolean = false,
    onClick: (() -> Unit)? = null, content: @Composable ColumnScope.() -> Unit,
) {
    val palette = LocalSpectrumPalette.current
    val shape = RoundedCornerShape(20.dp)
    val interaction = if (onClick == null) Modifier else Modifier.clip(shape).clickable(role = Role.Button, onClick = onClick)
    val border = Brush.linearGradient(listOf(
        palette.cyan.copy(alpha = if (emphasized) .58f else .26f),
        palette.blue.copy(alpha = .23f), palette.violet.copy(alpha = .24f),
    ))
    Card(
        modifier = modifier.then(interaction), shape = shape,
        colors = CardDefaults.cardColors(containerColor = palette.card, contentColor = MaterialTheme.colorScheme.onSurface),
        border = BorderStroke(1.dp, border),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Column(
            Modifier.fillMaxWidth().background(Brush.linearGradient(listOf(
                if (emphasized) palette.cardStrong else palette.card,
                palette.card,
            ))).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp), content = content,
        )
    }
}

@Composable
fun SpectrumBadge(text: String, modifier: Modifier = Modifier, accent: Color = LocalSpectrumPalette.current.cyan) {
    Surface(modifier, shape = RoundedCornerShape(8.dp), color = accent.copy(alpha = .10f),
        contentColor = accent, border = BorderStroke(1.dp, accent.copy(alpha = .28f))) {
        Text(text, Modifier.padding(horizontal = 9.dp, vertical = 5.dp), color = accent,
            style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold)
    }
}

/** A real Material button: focus, ripple, disabled state and a 52dp minimum target remain native. */
@Composable
fun SpectrumButton(
    onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true,
    emerald: Boolean = false, content: @Composable RowScope.() -> Unit,
) {
    val shape = RoundedCornerShape(12.dp)
    val colors = when {
        !enabled -> listOf(MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.surfaceVariant)
        emerald -> listOf(Color(0xFF007E61), Color(0xFF00694F))
        else -> listOf(Color(0xFF6938E8), Color(0xFF3154DE))
    }
    Button(
        onClick = onClick, enabled = enabled, shape = shape,
        modifier = modifier.heightIn(min = 52.dp).clip(shape).background(Brush.linearGradient(colors)),
        colors = ButtonDefaults.buttonColors(containerColor = Color.Transparent, contentColor = Color.White,
            disabledContainerColor = Color.Transparent, disabledContentColor = MaterialTheme.colorScheme.onSurfaceVariant),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
        border = BorderStroke(1.dp, Color.White.copy(alpha = if (enabled) .18f else .04f)),
        content = content,
    )
}

@Composable
fun SpectrumAction(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true, emerald: Boolean = false) {
    SpectrumButton(onClick, modifier.fillMaxWidth(), enabled, emerald) {
        Text(text, Modifier.weight(1f), fontWeight = FontWeight.SemiBold)
        Text("→", Modifier.padding(start = 10.dp), fontSize = 21.sp)
    }
}

@Composable
fun SpectrumIconButton(symbol: SpectrumSymbol, label: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    IconButton(onClick, modifier.sizeIn(minWidth = 48.dp, minHeight = 48.dp).semantics { contentDescription = label }) {
        SpectrumIcon(symbol, Modifier.size(36.dp), selected = true, tile = false)
    }
}

@Composable
fun SpectrumBrand(modifier: Modifier = Modifier, compact: Boolean = false) {
    Row(modifier, horizontalArrangement = Arrangement.spacedBy(9.dp), verticalAlignment = Alignment.CenterVertically) {
        SpectrumBrain(Modifier.size(if (compact) 34.dp else 52.dp))
        Text(buildAnnotatedString {
            append("Analyst ")
            withStyle(SpanStyle(color = LocalSpectrumPalette.current.cyan)) { append("AI") }
        }, style = if (compact) MaterialTheme.typography.titleMedium else MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold)
    }
}

@Composable
fun SpectrumHeader(title: String, subtitle: String? = null, symbol: SpectrumSymbol = SpectrumSymbol.Analyst, modifier: Modifier = Modifier) {
    Row(modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
        SpectrumIcon(symbol, Modifier.size(46.dp), selected = true)
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            if (subtitle != null) Text(subtitle, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
fun SpectrumSectionTitle(title: String, modifier: Modifier = Modifier) {
    Text(title, modifier, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
}

@Composable
fun SpectrumMessage(title: String, message: String, symbol: SpectrumSymbol = SpectrumSymbol.Analyst) {
    SpectrumCard(Modifier.fillMaxWidth()) {
        SpectrumHeader(title, symbol = symbol)
        Text(message, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
    }
}
