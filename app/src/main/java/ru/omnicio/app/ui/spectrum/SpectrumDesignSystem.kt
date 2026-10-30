package ru.omnicio.app.ui.spectrum

import androidx.compose.foundation.clickable
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.ColorScheme
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
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.drawscope.clipRect
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
import ru.omnicio.app.ui.workspace.AccentStyle
import ru.omnicio.app.ui.theme.AnalystSemanticColors
import ru.omnicio.app.ui.theme.analystColors

@Immutable
data class SpectrumPalette(
    val colors: ColorScheme,
    val semantic: AnalystSemanticColors,
    val chartSeries: List<Color>,
) {
    // Compatible names retain call-site meaning; only cyan follows the action accent.
    val backgroundTop: Color get() = colors.background
    val backgroundBottom: Color get() = colors.background
    val card: Color get() = colors.surface
    val cardStrong: Color get() = colors.surfaceContainerHighest
    val cyan: Color get() = colors.primary
    val blue: Color get() = semantic.info
    val violet: Color get() = colors.tertiary
    val rose: Color get() = colors.error
    val emerald: Color get() = semantic.success
    val amber: Color get() = semantic.warning

    fun containerFor(accent: Color): Color = when (accent) {
        cyan -> colors.primaryContainer
        blue -> semantic.infoContainer
        violet -> colors.tertiaryContainer
        rose -> colors.errorContainer
        emerald -> semantic.successContainer
        amber -> semantic.warningContainer
        else -> colors.surfaceContainer
    }

    fun foregroundFor(fill: Color): Color = when (fill) {
        colors.primary -> colors.onPrimary
        colors.primaryContainer -> colors.onPrimaryContainer
        colors.secondary -> colors.onSecondary
        colors.secondaryContainer -> colors.onSecondaryContainer
        colors.tertiary -> colors.onTertiary
        colors.tertiaryContainer -> colors.onTertiaryContainer
        colors.error -> colors.onError
        colors.errorContainer -> colors.onErrorContainer
        semantic.success -> semantic.onSuccess
        semantic.successContainer -> semantic.onSuccessContainer
        semantic.warning -> semantic.onWarning
        semantic.warningContainer -> semantic.onWarningContainer
        semantic.info -> semantic.onInfo
        semantic.infoContainer -> semantic.onInfoContainer
        else -> colors.onSurface
    }
}

fun spectrumPalette(dark: Boolean, accent: AccentStyle = AccentStyle.AURORA): SpectrumPalette {
    val resolved = analystColors(dark, accent)
    return SpectrumPalette(resolved.material, resolved.semantic, resolved.chartSeries)
}

val DarkSpectrumPalette = spectrumPalette(dark = true)
// Legacy preview alias: there is no second production colorway.
val LightSpectrumPalette = spectrumPalette(dark = false)

val LocalSpectrumPalette = staticCompositionLocalOf { DarkSpectrumPalette }

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
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val focused by interaction.collectIsFocusedAsState()
    val click = rememberSpatialHapticClick { onClick?.invoke() }
    val clickable = if (onClick == null) Modifier else Modifier.heightIn(min = 48.dp)
        .clickable(interactionSource = interaction, indication = null, role = Role.Button, onClick = click)
    SpatialSurface(modifier.then(clickable), color = if (emphasized) palette.cardStrong else palette.card,
        state = when { pressed -> SpatialState.Pressed; focused -> SpatialState.Selected; else -> SpatialState.Idle },
        emphasized = emphasized, interactive = onClick != null) {
        CompositionLocalProvider(LocalContentColor provides MaterialTheme.colorScheme.onSurface) {
            Column(Modifier.fillMaxWidth().padding(14.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp), content = content)
        }
    }
}

@Composable
fun SpectrumBadge(text: String, modifier: Modifier = Modifier, accent: Color = LocalSpectrumPalette.current.cyan) {
    val palette = LocalSpectrumPalette.current
    val fill = palette.containerFor(accent)
    SpatialSurface(modifier, SpatialSurfaceKind.Chip, color = fill) {
        Text(text, Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
            color = palette.foregroundFor(fill),
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
        ru.omnicio.app.ui.AnalystHeaderMenu()
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
        if (ru.omnicio.app.ui.LocalOpenNavigationMenu.current == null)
            SpectrumIcon(symbol, Modifier.size(32.dp), selected = true, tile = false, motionAllowed = false)
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
        color = if (enabled) MaterialTheme.colorScheme.primary else LocalSpectrumPalette.current.semantic.disabledContainer, state = state) {
        Row(Modifier.fillMaxWidth().heightIn(min = 48.dp).padding(horizontal = 16.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
            if (symbol != null) {
                SpatialIcon(symbol.asset, Modifier.size(26.dp),
                    tint = if (enabled) MaterialTheme.colorScheme.onPrimary else LocalSpectrumPalette.current.semantic.disabledInk,
                    state = state, colorMode = SpatialColorMode.Monochrome)
                Spacer(Modifier.width(9.dp))
            }
            Text(text, color = if (enabled) MaterialTheme.colorScheme.onPrimary else LocalSpectrumPalette.current.semantic.disabledInk,
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
        Box(Modifier.fillMaxWidth().heightIn(min = 48.dp).padding(horizontal = 16.dp, vertical = 10.dp),
            contentAlignment = Alignment.Center) {
            Text(text, color = if (enabled) MaterialTheme.colorScheme.onSurface else LocalSpectrumPalette.current.semantic.disabledInk, fontWeight = FontWeight.SemiBold,
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
            SpatialIcon(symbol.asset, Modifier.size(24.dp), tint = accent,
                state = SpatialState.Selected, colorMode = SpatialColorMode.Monochrome)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(title, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                Text(subtitle, color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
fun SpectrumMetricPill(label: String, value: String, modifier: Modifier = Modifier, accent: Color = LocalSpectrumPalette.current.blue) {
    val palette = LocalSpectrumPalette.current
    val fill = palette.containerFor(accent)
    val ink = palette.foregroundFor(fill)
    SpatialSurface(modifier, SpatialSurfaceKind.Chip, color = fill) {
        Column(Modifier.padding(horizontal = 14.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(value, color = ink, fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.titleMedium)
            Text(label, color = ink, style = MaterialTheme.typography.labelSmall)
        }
    }
}

/** The fill always represents the supplied fraction; only its light cycles. */
@Composable
fun SpectrumProgressBar(fraction: Float, modifier: Modifier = Modifier, accent: Color = LocalSpectrumPalette.current.cyan,
    enabled: Boolean = true) {
    if (!fraction.isFinite()) return
    val progress = fraction.coerceIn(0f, 1f)
    val palette = LocalSpectrumPalette.current
    val light = rememberLiveDecoration(enabled && progress > 0f && progress < 1f)
    Canvas(modifier.fillMaxWidth().height(10.dp).then(light.modifier).semantics {
        progressBarRangeInfo = ProgressBarRangeInfo(progress, 0f..1f)
    }) {
        val radius = CornerRadius(size.height / 2)
        drawRoundRect(if (enabled) palette.colors.surfaceContainerHighest else palette.semantic.disabledContainer, cornerRadius = radius)
        if (progress > 0f) {
            val width = size.width * progress
            drawRoundRect(Brush.horizontalGradient(if (enabled) listOf(accent, palette.colors.secondary)
                else listOf(palette.semantic.disabledInk, palette.semantic.disabledInk)),
                size = Size(width, size.height), cornerRadius = radius)
            // A draw-only highlight stays within the real filled fraction.
            val phase = light.phase.value
            if (phase > 0f) clipRect(right = width) {
                val band = size.height * 3f
                val x = (width + band * 2) * phase - band
                drawRect(Brush.horizontalGradient(listOf(Color.Transparent,
                    palette.colors.onBackground.copy(alpha = .32f), Color.Transparent), x - band, x + band),
                    topLeft = Offset(x - band, 1f), size = Size(band * 2, (size.height - 2).coerceAtLeast(0f)))
            }
        }
    }
}

/** Original vector illustration; motion is decorative and never represents account values. */
@Composable
fun SpectrumBrandOrb(modifier: Modifier = Modifier, compact: Boolean = false) {
    SpatialIcon(if (compact) "analyst" else "brand", modifier.aspectRatio(1f),
        tint = LocalSpectrumPalette.current.cyan, motionAllowed = true)
}




