package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
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
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

/** Canonical Analyst AI Spectrum palette approved by the owner on 2026-10-13. */
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
    backgroundTop = Color(0xFF020A16),
    backgroundBottom = Color(0xFF07192B),
    card = Color(0xFF071A2A),
    cardStrong = Color(0xFF0B2940),
    cyan = Color(0xFF36E0FF),
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

@Composable
fun SpectrumBackground(
    modifier: Modifier = Modifier,
    content: @Composable BoxScope.() -> Unit,
) {
    val palette = LocalSpectrumPalette.current
    val dark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    Box(
        modifier = modifier.background(
            Brush.verticalGradient(
                colors = if (dark) {
                    listOf(
                        palette.backgroundTop,
                        Color(0xFF03111F),
                        palette.backgroundBottom,
                        palette.backgroundTop,
                    )
                } else {
                    listOf(palette.backgroundTop, palette.backgroundBottom, Color(0xFFF8FAFF))
                },
            ),
        ),
    ) {
        Canvas(Modifier.fillMaxSize()) {
            if (size.minDimension <= 0f) return@Canvas
            val radius = size.minDimension
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        palette.violet.copy(alpha = if (dark) 0.22f else 0.09f),
                        Color.Transparent,
                    ),
                    center = Offset(size.width * 0.92f, size.height * 0.06f),
                    radius = radius * 0.82f,
                ),
                radius = radius * 0.82f,
                center = Offset(size.width * 0.92f, size.height * 0.06f),
            )
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        palette.cyan.copy(alpha = if (dark) 0.16f else 0.07f),
                        Color.Transparent,
                    ),
                    center = Offset(size.width * 0.02f, size.height * 0.74f),
                    radius = radius * 0.72f,
                ),
                radius = radius * 0.72f,
                center = Offset(size.width * 0.02f, size.height * 0.74f),
            )
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        palette.rose.copy(alpha = if (dark) 0.08f else 0.035f),
                        Color.Transparent,
                    ),
                    center = Offset(size.width * 0.70f, size.height * 0.62f),
                    radius = radius * 0.55f,
                ),
                radius = radius * 0.55f,
                center = Offset(size.width * 0.70f, size.height * 0.62f),
            )
            if (dark) {
                val star = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.11f)
                repeat(24) { index ->
                    val x = ((index * 73) % 101) / 100f * size.width
                    val y = ((index * 41 + 17) % 97) / 100f * size.height
                    val dot = if (index % 5 == 0) 1.8f else 1.0f
                    drawCircle(star, radius = dot, center = Offset(x, y))
                }
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
    val shape = RoundedCornerShape(24.dp)
    val interactive = if (onClick == null) {
        Modifier
    } else {
        Modifier.clip(shape).clickable(role = Role.Button, onClick = onClick)
    }
    Card(
        modifier = modifier.then(interactive),
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
        border = BorderStroke(
            width = 1.dp,
            brush = Brush.linearGradient(
                colors = listOf(
                    palette.cyan.copy(alpha = if (emphasized) 0.72f else 0.28f),
                    palette.blue.copy(alpha = if (emphasized) 0.46f else 0.18f),
                    palette.violet.copy(alpha = if (emphasized) 0.72f else 0.28f),
                    palette.rose.copy(alpha = if (emphasized) 0.40f else 0.12f),
                ),
            ),
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = if (dark) 0.dp else 3.dp),
    ) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(18.dp),
            content = content,
        )
    }
}

@Composable
fun SpectrumBadge(
    text: String,
    modifier: Modifier = Modifier,
    accent: Color = LocalSpectrumPalette.current.cyan,
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(999.dp),
        color = accent.copy(alpha = 0.14f),
        contentColor = MaterialTheme.colorScheme.onSurface,
        border = BorderStroke(1.dp, accent.copy(alpha = 0.40f)),
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
            color = MaterialTheme.colorScheme.onSurface,
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

@Composable
fun SpectrumPageHeader(
    title: String,
    subtitle: String,
    symbol: SpectrumSymbol,
    modifier: Modifier = Modifier,
    eyebrow: String = "Analyst AI",
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        SpectrumIcon(
            symbol = symbol,
            modifier = Modifier.size(58.dp),
            selected = true,
            tile = true,
            motionAllowed = false,
        )
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(
                text = eyebrow,
                color = LocalSpectrumPalette.current.cyan,
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                text = title,
                style = MaterialTheme.typography.headlineLarge,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = subtitle,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
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
    val palette = LocalSpectrumPalette.current
    val brush = if (enabled) {
        Brush.horizontalGradient(listOf(palette.cyan, palette.blue, palette.violet))
    } else {
        Brush.horizontalGradient(
            listOf(
                MaterialTheme.colorScheme.surfaceVariant,
                MaterialTheme.colorScheme.surfaceVariant,
            ),
        )
    }
    Surface(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier,
        color = Color.Transparent,
        contentColor = Color.White,
        shape = RoundedCornerShape(18.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 54.dp)
                .background(brush)
                .padding(horizontal = 18.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.Center,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (symbol != null) {
                SpectrumIcon(
                    symbol = symbol,
                    modifier = Modifier.size(26.dp),
                    selected = true,
                    tile = false,
                    motionAllowed = false,
                )
                Spacer(Modifier.width(9.dp))
            }
            Text(text, color = Color.White, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
fun SpectrumSecondaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    val palette = LocalSpectrumPalette.current
    Surface(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier,
        shape = RoundedCornerShape(18.dp),
        color = palette.cardStrong.copy(alpha = if (enabled) 0.78f else 0.45f),
        contentColor = MaterialTheme.colorScheme.onSurface,
        border = BorderStroke(1.dp, palette.blue.copy(alpha = 0.40f)),
    ) {
        Box(
            modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp).padding(horizontal = 16.dp),
            contentAlignment = Alignment.Center,
        ) {
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
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Surface(
                modifier = Modifier.size(48.dp),
                shape = RoundedCornerShape(16.dp),
                color = accent.copy(alpha = 0.14f),
                border = BorderStroke(1.dp, accent.copy(alpha = 0.35f)),
            ) {
                SpectrumIcon(
                    symbol = symbol,
                    modifier = Modifier.padding(8.dp),
                    selected = true,
                    tile = false,
                    motionAllowed = false,
                )
            }
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(title, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                Text(
                    subtitle,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}

@Composable
fun SpectrumMetricPill(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
    accent: Color = LocalSpectrumPalette.current.blue,
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(18.dp),
        color = accent.copy(alpha = 0.12f),
        contentColor = MaterialTheme.colorScheme.onSurface,
        border = BorderStroke(1.dp, accent.copy(alpha = 0.26f)),
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            Text(value, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
            Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelSmall)
        }
    }
}

@Composable
fun SpectrumProgressBar(
    fraction: Float,
    modifier: Modifier = Modifier,
    accent: Color = LocalSpectrumPalette.current.cyan,
) {
    val progress = fraction.coerceIn(0f, 1f)
    Box(
        modifier = modifier
            .fillMaxWidth()
            .height(8.dp)
            .clip(CircleShape)
            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.62f)),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth(progress)
                .fillMaxHeight()
                .background(
                    Brush.horizontalGradient(
                        listOf(accent.copy(alpha = 0.75f), accent, LocalSpectrumPalette.current.violet),
                    ),
                ),
        )
    }
}

@Composable
fun SpectrumBrandOrb(
    modifier: Modifier = Modifier,
    compact: Boolean = false,
) {
    val palette = LocalSpectrumPalette.current
    val dark = MaterialTheme.colorScheme.background.luminance() < 0.5f
    Canvas(modifier.aspectRatio(1f)) {
        if (size.minDimension <= 0f) return@Canvas
        val center = Offset(size.width / 2f, size.height / 2f)
        val radius = size.minDimension * 0.34f
        drawCircle(
            brush = Brush.radialGradient(
                colors = listOf(
                    palette.cyan.copy(alpha = if (dark) 0.34f else 0.18f),
                    palette.violet.copy(alpha = if (dark) 0.20f else 0.10f),
                    Color.Transparent,
                ),
                center = center,
                radius = size.minDimension * 0.50f,
            ),
            radius = size.minDimension * 0.50f,
            center = center,
        )
        drawCircle(
            brush = Brush.linearGradient(
                listOf(palette.cyan, palette.blue, palette.violet, palette.rose),
                start = Offset(center.x - radius, center.y - radius),
                end = Offset(center.x + radius, center.y + radius),
            ),
            radius = radius,
            center = center,
            style = Stroke(width = size.minDimension * 0.035f),
        )
        drawArc(
            color = palette.cyan.copy(alpha = 0.78f),
            startAngle = 210f,
            sweepAngle = 220f,
            useCenter = false,
            topLeft = Offset(center.x - radius * 1.30f, center.y - radius * 0.54f),
            size = Size(radius * 2.60f, radius * 1.08f),
            style = Stroke(width = size.minDimension * 0.024f, cap = StrokeCap.Round),
        )
        drawArc(
            color = palette.violet.copy(alpha = 0.78f),
            startAngle = 30f,
            sweepAngle = 220f,
            useCenter = false,
            topLeft = Offset(center.x - radius * 0.54f, center.y - radius * 1.30f),
            size = Size(radius * 1.08f, radius * 2.60f),
            style = Stroke(width = size.minDimension * 0.024f, cap = StrokeCap.Round),
        )
        val brain = Path().apply {
            moveTo(center.x - radius * 0.38f, center.y)
            cubicTo(
                center.x - radius * 0.72f,
                center.y - radius * 0.62f,
                center.x - radius * 0.06f,
                center.y - radius * 0.90f,
                center.x,
                center.y - radius * 0.38f,
            )
            cubicTo(
                center.x + radius * 0.06f,
                center.y - radius * 0.90f,
                center.x + radius * 0.72f,
                center.y - radius * 0.62f,
                center.x + radius * 0.38f,
                center.y,
            )
            cubicTo(
                center.x + radius * 0.72f,
                center.y + radius * 0.62f,
                center.x + radius * 0.06f,
                center.y + radius * 0.90f,
                center.x,
                center.y + radius * 0.38f,
            )
            cubicTo(
                center.x - radius * 0.06f,
                center.y + radius * 0.90f,
                center.x - radius * 0.72f,
                center.y + radius * 0.62f,
                center.x - radius * 0.38f,
                center.y,
            )
        }
        drawPath(
            brain,
            brush = Brush.linearGradient(listOf(palette.cyan, palette.violet, palette.rose)),
            style = Stroke(
                width = size.minDimension * if (compact) 0.038f else 0.046f,
                cap = StrokeCap.Round,
            ),
        )
        drawCircle(
            color = palette.cyan,
            radius = size.minDimension * 0.025f,
            center = Offset(center.x + radius * 0.72f, center.y - radius * 0.30f),
        )
    }
}
