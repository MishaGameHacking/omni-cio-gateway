package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.text.font.FontWeight
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
                    listOf(palette.backgroundTop, palette.backgroundBottom, palette.backgroundTop)
                } else {
                    listOf(palette.backgroundTop, palette.backgroundBottom)
                },
            ),
        ),
    ) {
        Canvas(Modifier.fillMaxSize()) {
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(palette.violet.copy(alpha = if (dark) 0.18f else 0.08f), Color.Transparent),
                    center = Offset(size.width * 0.90f, size.height * 0.08f),
                    radius = size.minDimension * 0.72f,
                ),
                radius = size.minDimension * 0.72f,
                center = Offset(size.width * 0.90f, size.height * 0.08f),
            )
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(palette.cyan.copy(alpha = if (dark) 0.13f else 0.06f), Color.Transparent),
                    center = Offset(size.width * 0.04f, size.height * 0.78f),
                    radius = size.minDimension * 0.62f,
                ),
                radius = size.minDimension * 0.62f,
                center = Offset(size.width * 0.04f, size.height * 0.78f),
            )
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
    val interactive = if (onClick == null) Modifier else Modifier.clickable(onClick = onClick)
    Card(
        modifier = modifier.then(interactive),
        shape = shape,
        colors = CardDefaults.cardColors(
            containerColor = when {
                emphasized && dark -> palette.cardStrong.copy(alpha = 0.97f)
                dark -> palette.card.copy(alpha = 0.96f)
                emphasized -> palette.cardStrong
                else -> palette.card
            },
        ),
        border = BorderStroke(
            width = 1.dp,
            brush = Brush.linearGradient(
                colors = listOf(
                    palette.cyan.copy(alpha = if (emphasized) 0.64f else 0.24f),
                    palette.violet.copy(alpha = if (emphasized) 0.68f else 0.24f),
                    palette.rose.copy(alpha = if (emphasized) 0.42f else 0.12f),
                ),
            ),
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = if (dark) 0.dp else 2.dp),
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
        border = BorderStroke(1.dp, accent.copy(alpha = 0.36f)),
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
            color = accent,
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.SemiBold,
        )
    }
}
