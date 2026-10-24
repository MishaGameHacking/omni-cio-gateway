package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.progressBarRangeInfo
import androidx.compose.ui.semantics.ProgressBarRangeInfo
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spatial.*
import ru.omnicio.app.ui.workspace.InterfaceDensity
import ru.omnicio.app.ui.workspace.LocalWorkspacePreferences

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
    backgroundTop = Color(0xFF10131D),
    backgroundBottom = Color(0xFF171C29),
    card = Color(0xFF1A2030),
    cardStrong = Color(0xFF252C40),
    cyan = Color(0xFF68D8C5),
    blue = Color(0xFFA6ABFF),
    violet = Color(0xFFB6A2FF),
    rose = Color(0xFFF68FAB),
    emerald = Color(0xFF68D8AE),
    amber = Color(0xFFF5C771),
)

val LightSpectrumPalette = SpectrumPalette(
    backgroundTop = Color(0xFFF7F8FC),
    backgroundBottom = Color(0xFFEEF0F8),
    card = Color.White,
    cardStrong = Color(0xFFEEEBFA),
    cyan = Color(0xFF087C74),
    blue = Color(0xFF5844BE),
    violet = Color(0xFF7051C5),
    rose = Color(0xFFAB3962),
    emerald = Color(0xFF08765E),
    amber = Color(0xFF875900),
)

val LocalSpectrumPalette = staticCompositionLocalOf { DarkSpectrumPalette }

// White labels retain >=4.5:1 contrast over every interpolated stop. Bright
// accent color is reserved for decoration, never a white-text background.
internal val SpectrumPrimaryStops = listOf(
    Color(0xFF5844BE), Color(0xFF6549C4), Color(0xFF714BC2),
)


@Composable
fun SpectrumBackground(modifier: Modifier = Modifier, content: @Composable BoxScope.() -> Unit) {
    // Shared spacing and native surfaces unify every destination.
    Box(modifier, contentAlignment = Alignment.TopCenter) {
        CompositionLocalProvider(LocalContentColor provides MaterialTheme.colorScheme.onBackground) {
            Box(Modifier.widthIn(max = 840.dp).fillMaxSize(), content = content)
        }
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
    val compact = LocalWorkspacePreferences.current.value.density == InterfaceDensity.COMPACT
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val focused by interaction.collectIsFocusedAsState()
    val click = rememberSpatialHapticClick { onClick?.invoke() }
    val clickable = if (onClick == null) Modifier else Modifier.heightIn(min = 48.dp)
        .clickable(interactionSource = interaction, indication = null, role = Role.Button, onClick = click)
    SpatialSurface(modifier.then(clickable), color = if (emphasized) palette.cardStrong else palette.card,
        state = when { pressed -> SpatialState.Pressed; focused -> SpatialState.Selected; else -> SpatialState.Idle }, emphasized = emphasized) {
        CompositionLocalProvider(LocalContentColor provides MaterialTheme.colorScheme.onSurface) {
            Column(Modifier.fillMaxWidth().padding(if (compact) 14.dp else 20.dp),
                verticalArrangement = Arrangement.spacedBy(if (compact) 8.dp else 10.dp), content = content)
        }
    }
}

@Composable
fun SpectrumBadge(text: String, modifier: Modifier = Modifier, accent: Color = LocalSpectrumPalette.current.cyan) {
    SpatialSurface(modifier, SpatialSurfaceKind.Chip, color = lerp(LocalSpectrumPalette.current.card, accent, .13f)) {
        Text(text, Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
            color = MaterialTheme.colorScheme.onSurface,
            style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold)
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
    Row(modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            if (eyebrow.isNotBlank()) Text(eyebrow.uppercase(),
                color = LocalSpectrumPalette.current.violet, style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.SemiBold)
            SpatialSurface(kind = SpatialSurfaceKind.Heading, color = LocalSpectrumPalette.current.cardStrong) {
                Text(title, Modifier.padding(vertical = 2.dp).semantics { heading() },
                    style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface)
            }
            if (subtitle.isNotBlank()) Text(subtitle, color = MaterialTheme.colorScheme.onSurfaceVariant,
                style = MaterialTheme.typography.bodyMedium)
        }
        SpectrumIcon(symbol, Modifier.size(48.dp), selected = true, tile = true, motionAllowed = true)
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
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val focused by interaction.collectIsFocusedAsState()
    val click = rememberSpatialHapticClick(onClick)
    val state = when { !enabled -> SpatialState.Disabled; pressed -> SpatialState.Pressed; focused -> SpatialState.Selected; else -> SpatialState.Idle }
    SpatialSurface(modifier.clickable(interactionSource = interaction, indication = null,
        enabled = enabled, role = Role.Button, onClick = click), SpatialSurfaceKind.Button,
        color = SpectrumPrimaryStops.first(), state = state, emphasized = true) {
        Row(Modifier.fillMaxWidth().heightIn(min = 54.dp).padding(horizontal = 18.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
            if (symbol != null) {
                SpatialIcon(symbol.asset, Modifier.size(26.dp), tint = Color.White, state = state)
                Spacer(Modifier.width(9.dp))
            }
            Text(text, color = if (enabled) Color.White else MaterialTheme.colorScheme.onSurfaceVariant,
                fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
        }
    }
}

@Composable
fun SpectrumSecondaryButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) {
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val focused by interaction.collectIsFocusedAsState()
    val click = rememberSpatialHapticClick(onClick)
    SpatialSurface(modifier.clickable(interactionSource = interaction, indication = null,
        enabled = enabled, role = Role.Button, onClick = click), SpatialSurfaceKind.Button,
        color = LocalSpectrumPalette.current.cardStrong,
        state = when { !enabled -> SpatialState.Disabled; pressed -> SpatialState.Pressed; focused -> SpatialState.Selected; else -> SpatialState.Idle }) {
        Box(Modifier.fillMaxWidth().heightIn(min = 52.dp).padding(horizontal = 16.dp, vertical = 12.dp),
            contentAlignment = Alignment.Center) {
            Text(text, color = MaterialTheme.colorScheme.onSurface, fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.Center)
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
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            SpatialSurface(Modifier.size(48.dp), SpatialSurfaceKind.Chip,
                color = lerp(LocalSpectrumPalette.current.cardStrong, accent, .12f)) {
                SpatialIcon(symbol.asset, Modifier.fillMaxSize().padding(8.dp), tint = accent, state = SpatialState.Selected)
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
    SpatialSurface(modifier, SpatialSurfaceKind.Chip, color = lerp(LocalSpectrumPalette.current.card, accent, .12f)) {
        Column(Modifier.padding(horizontal = 14.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(value, color = MaterialTheme.colorScheme.onSurface, fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.titleMedium)
            Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelSmall)
        }
    }
}

@Composable
fun SpectrumProgressBar(fraction: Float, modifier: Modifier = Modifier, accent: Color = LocalSpectrumPalette.current.cyan) {
    if (!fraction.isFinite()) return
    val progress = fraction.coerceIn(0f, 1f)
    SpatialSurface(modifier.fillMaxWidth().height(8.dp).semantics {
        progressBarRangeInfo = ProgressBarRangeInfo(progress, 0f..1f)
    }, SpatialSurfaceKind.Chip, color = LocalSpectrumPalette.current.cardStrong) {
        if (progress > 0f) SpatialSurface(Modifier.fillMaxWidth(progress).fillMaxHeight(),
            SpatialSurfaceKind.Chip, color = accent) { }
    }
}

/** Original vector illustration; motion is decorative and never represents account values. */
@Composable
fun SpectrumBrandOrb(modifier: Modifier = Modifier, compact: Boolean = false) {
    SpatialIcon(if (compact) "analyst" else "brand", modifier.aspectRatio(1f),
        tint = LocalSpectrumPalette.current.cyan, motionAllowed = true)
}

