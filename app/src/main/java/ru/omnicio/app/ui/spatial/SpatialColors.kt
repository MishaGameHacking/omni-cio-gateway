package ru.omnicio.app.ui.spatial

import androidx.compose.runtime.Immutable
import androidx.compose.ui.graphics.Color
import ru.omnicio.app.ui.spectrum.SpectrumPalette
import ru.omnicio.app.ui.theme.analystPressedColor

@Immutable
internal data class SpatialSurfaceColors(val fill: Color, val foreground: Color, val border: Color)

/** The real surface and its foreground use the same state calculation. */
internal fun spatialSurfaceColors(
    palette: SpectrumPalette,
    color: Color,
    state: SpatialState,
    interactive: Boolean,
    emphasized: Boolean,
    highContrast: Boolean,
): SpatialSurfaceColors {
    if (state == SpatialState.Disabled) return SpatialSurfaceColors(
        palette.semantic.disabledContainer, palette.semantic.disabledInk, palette.colors.outlineVariant)
    val foreground = palette.foregroundFor(color)
    val neutral = color in listOf(palette.colors.background, palette.colors.surface, palette.colors.surfaceVariant,
        palette.colors.surfaceBright, palette.colors.surfaceDim, palette.colors.surfaceContainerLowest,
        palette.colors.surfaceContainerLow, palette.colors.surfaceContainer, palette.colors.surfaceContainerHigh,
        palette.colors.surfaceContainerHighest)
    // Neutral cards can contain secondary text; retain its contrast under the pressed layer.
    val fill = if (state == SpatialState.Pressed) analystPressedColor(color, foreground, if (neutral) .04f else .08f) else color
    val border = when {
        state == SpatialState.Selected -> if (color == palette.colors.primary) palette.colors.onPrimary else palette.colors.primary
        state == SpatialState.Attention -> palette.rose
        color == palette.colors.primary -> color
        interactive || emphasized || highContrast -> palette.colors.outline
        else -> palette.colors.outlineVariant
    }
    return SpatialSurfaceColors(fill, foreground, border)
}

/** Mode is an asset/control decision, never a comparison against a literal white ink. */
internal fun spatialIconMode(asset: String): SpatialColorMode = when (asset) {
    "brand", "orbit", "avatar", "analyst" -> SpatialColorMode.Decorative
    else -> SpatialColorMode.Monochrome
}

internal fun spatialIconInk(palette: SpectrumPalette, asset: String, tint: Color, state: SpatialState): Color = when {
    state == SpatialState.Disabled -> palette.semantic.disabledInk
    tint != Color.Unspecified -> tint
    asset == "error" -> palette.rose
    asset == "warning" || asset == "risk" -> palette.amber
    state == SpatialState.Success -> palette.emerald
    state == SpatialState.Attention -> palette.amber
    else -> palette.cyan
}

@Immutable
internal data class FlatArtworkColors(
    val ink: Color, val teal: Color, val violet: Color, val amber: Color, val rose: Color,
)

internal fun flatArtworkColors(
    palette: SpectrumPalette, tint: Color, mode: SpatialColorMode, state: SpatialState,
): FlatArtworkColors {
    val ink = if (state == SpatialState.Disabled) palette.semantic.disabledInk else tint
    if (mode == SpatialColorMode.Monochrome || state == SpatialState.Disabled)
        return FlatArtworkColors(ink, ink, ink, ink, ink)
    return FlatArtworkColors(ink, palette.cyan, palette.violet, palette.amber, palette.rose)
}

@Immutable
internal data class SpatialToggleColors(val track: Color, val thumb: Color, val outline: Color)

internal fun spatialToggleColors(palette: SpectrumPalette, checked: Boolean, enabled: Boolean): SpatialToggleColors = when {
    !enabled -> SpatialToggleColors(palette.semantic.disabledContainer, palette.semantic.disabledInk, palette.colors.outlineVariant)
    checked -> SpatialToggleColors(palette.colors.primary, palette.colors.onPrimary, palette.colors.primary)
    else -> SpatialToggleColors(palette.cardStrong, palette.colors.outline, palette.colors.outline)
}

/** Explicit per-observation colors avoid assigning a separate series to only index zero. */
internal fun historyBarColors(palette: SpectrumPalette, values: List<Double?>): List<Color> =
    values.map { if (it != null && it < 0.0) palette.rose else palette.blue }
