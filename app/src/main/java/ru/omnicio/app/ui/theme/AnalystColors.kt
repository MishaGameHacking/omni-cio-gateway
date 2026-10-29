package ru.omnicio.app.ui.theme

import androidx.compose.material3.ColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Immutable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.compositeOver
import ru.omnicio.app.ui.workspace.AccentStyle

/** Extra semantic colors stay independent of a user's selected action accent. */
@Immutable
data class AnalystSemanticColors(
    val success: Color,
    val onSuccess: Color,
    val successContainer: Color,
    val onSuccessContainer: Color,
    val warning: Color,
    val onWarning: Color,
    val warningContainer: Color,
    val onWarningContainer: Color,
    val info: Color,
    val onInfo: Color,
    val infoContainer: Color,
    val onInfoContainer: Color,
    val disabledInk: Color,
    val disabledContainer: Color,
    val chartGrid: Color,
    val chartAxis: Color,
    val chartSeparator: Color,
    val chartSelectedInner: Color,
    val chartSelectedOuter: Color,
)

@Immutable
data class AnalystColorSet(
    val material: ColorScheme,
    val semantic: AnalystSemanticColors,
    val chartSeries: List<Color>,
)

private val WorkspaceColors = lightColorScheme(
    primary = Color(0xFF205DD7),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFE4EDFF),
    onPrimaryContainer = Color(0xFF153C89),
    inversePrimary = Color(0xFF9DB9FF),
    secondary = Color(0xFF086E7A),
    onSecondary = Color(0xFFFFFFFF),
    secondaryContainer = Color(0xFFDDF5F1),
    onSecondaryContainer = Color(0xFF07534E),
    tertiary = Color(0xFF7950B8),
    onTertiary = Color(0xFFFFFFFF),
    tertiaryContainer = Color(0xFFF0E6FF),
    onTertiaryContainer = Color(0xFF4B2878),
    background = Color(0xFFF5F7FB),
    onBackground = Color(0xFF17243A),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF17243A),
    surfaceVariant = Color(0xFFEDF1F7),
    onSurfaceVariant = Color(0xFF526176),
    surfaceTint = Color(0xFF205DD7),
    inverseSurface = Color(0xFF17243A),
    inverseOnSurface = Color(0xFFF5F7FB),
    error = Color(0xFFB42343),
    onError = Color(0xFFFFFFFF),
    errorContainer = Color(0xFFFFE8ED),
    onErrorContainer = Color(0xFF81132F),
    outline = Color(0xFF738196),
    outlineVariant = Color(0xFFE0E6EF),
    scrim = Color(0xFF101B30),
    surfaceBright = Color(0xFFFFFFFF),
    surfaceDim = Color(0xFFE9EEF5),
    surfaceContainer = Color(0xFFF0F3F8),
    surfaceContainerHigh = Color(0xFFEAF0F7),
    surfaceContainerHighest = Color(0xFFE5EDF7),
    surfaceContainerLow = Color(0xFFF7F9FC),
    surfaceContainerLowest = Color(0xFFFFFFFF),
    primaryFixed = Color(0xFFE5DEFF),
    primaryFixedDim = Color(0xFFC4B7FF),
    onPrimaryFixed = Color(0xFF1B0D45),
    onPrimaryFixedVariant = Color(0xFF3D286C),
    secondaryFixed = Color(0xFFCBF5FF),
    secondaryFixedDim = Color(0xFF8AE6FF),
    onSecondaryFixed = Color(0xFF022D3B),
    onSecondaryFixedVariant = Color(0xFF12465B),
    tertiaryFixed = Color(0xFFDFE8FF),
    tertiaryFixedDim = Color(0xFFB0C6FF),
    onTertiaryFixed = Color(0xFF132A58),
    onTertiaryFixedVariant = Color(0xFF284572),
)

private val WorkspaceSemantic = AnalystSemanticColors(
    success = Color(0xFF137950),
    onSuccess = Color(0xFFFFFFFF),
    successContainer = Color(0xFFE0F5EA),
    onSuccessContainer = Color(0xFF145538),
    warning = Color(0xFF946000),
    onWarning = Color(0xFFFFFFFF),
    warningContainer = Color(0xFFFFF2D5),
    onWarningContainer = Color(0xFF674200),
    info = Color(0xFF2463B8),
    onInfo = Color(0xFFFFFFFF),
    infoContainer = Color(0xFFE5F0FF),
    onInfoContainer = Color(0xFF163D78),
    disabledInk = Color(0xFF66758A),
    disabledContainer = Color(0xFFEDF1F6),
    chartGrid = Color(0xFFDDE4EE),
    chartAxis = Color(0xFF738196),
    chartSeparator = Color(0xFFFFFFFF),
    chartSelectedInner = Color(0xFFFFFFFF),
    chartSelectedOuter = Color(0xFF17243A),
)

private val GraphiteColors = darkColorScheme(
    primary = Color(0xFF9DB9FF), onPrimary = Color(0xFF102C63),
    inversePrimary = Color(0xFF205DD7),
    primaryFixed = WorkspaceColors.primaryFixed,
    primaryFixedDim = WorkspaceColors.primaryFixedDim,
    onPrimaryFixed = WorkspaceColors.onPrimaryFixed,
    onPrimaryFixedVariant = WorkspaceColors.onPrimaryFixedVariant,
    secondaryFixed = WorkspaceColors.secondaryFixed,
    secondaryFixedDim = WorkspaceColors.secondaryFixedDim,
    onSecondaryFixed = WorkspaceColors.onSecondaryFixed,
    onSecondaryFixedVariant = WorkspaceColors.onSecondaryFixedVariant,
    tertiaryFixed = WorkspaceColors.tertiaryFixed,
    tertiaryFixedDim = WorkspaceColors.tertiaryFixedDim,
    onTertiaryFixed = WorkspaceColors.onTertiaryFixed,
    onTertiaryFixedVariant = WorkspaceColors.onTertiaryFixedVariant,
    primaryContainer = Color(0xFF263A60), onPrimaryContainer = Color(0xFFDCE6FF),
    secondary = Color(0xFF87D5C5), onSecondary = Color(0xFF093B33),
    secondaryContainer = Color(0xFF233F3A), onSecondaryContainer = Color(0xFFC0F5E8),
    tertiary = Color(0xFFC9AFF0), onTertiary = Color(0xFF392351),
    tertiaryContainer = Color(0xFF40324E), onTertiaryContainer = Color(0xFFEEDCFF),
    inverseSurface = Color(0xFFE4E2E6), inverseOnSurface = Color(0xFF303136),
    scrim = Color(0xFF000000),
    background = Color(0xFF141517), onBackground = Color(0xFFF1F1F3),
    surface = Color(0xFF1D1E21), onSurface = Color(0xFFF1F1F3),
    surfaceVariant = Color(0xFF303136), onSurfaceVariant = Color(0xFFCACBD1),
    surfaceContainerLowest = Color(0xFF111214), surfaceContainerLow = Color(0xFF191A1D),
    surfaceContainer = Color(0xFF242529), surfaceContainerHigh = Color(0xFF2B2C31),
    surfaceContainerHighest = Color(0xFF35363C), surfaceBright = Color(0xFF3A3B40),
    surfaceDim = Color(0xFF141517), surfaceTint = Color(0xFF9DB9FF),
    outline = Color(0xFF9799A3), outlineVariant = Color(0xFF494B54),
    error = Color(0xFFFFB1BB), onError = Color(0xFF5F152A),
    errorContainer = Color(0xFF572332), onErrorContainer = Color(0xFFFFD9DF),
)
private val GraphiteSemantic = WorkspaceSemantic.copy(
    success = Color(0xFF8BD8AA), onSuccess = Color(0xFF073A21),
    successContainer = Color(0xFF223C2D), onSuccessContainer = Color(0xFFBBF2D0),
    warning = Color(0xFFF2CB7C), onWarning = Color(0xFF3C2B04),
    warningContainer = Color(0xFF45391E), onWarningContainer = Color(0xFFFFE4AC),
    info = Color(0xFF9DB9FF), onInfo = Color(0xFF102C63),
    infoContainer = Color(0xFF263A60), onInfoContainer = Color(0xFFDCE6FF),
    disabledInk = Color(0xFFA3A5AE), disabledContainer = Color(0xFF303136),
    chartGrid = Color(0xFF41434B), chartAxis = Color(0xFF9799A3),
    chartSeparator = Color(0xFF1D1E21), chartSelectedInner = Color(0xFF1D1E21), chartSelectedOuter = Color(0xFFF1F1F3),
)

@Suppress("UNUSED_PARAMETER")
fun analystColors(dark: Boolean = false, accent: AccentStyle = AccentStyle.AURORA): AnalystColorSet {
    val colors = if (dark) GraphiteColors else WorkspaceColors
    val semantic = if (dark) GraphiteSemantic else WorkspaceSemantic
    return AnalystColorSet(colors, semantic, listOf(colors.secondary, colors.primary,
        semantic.success, colors.tertiary, semantic.warning, colors.error))
}

/** Actual state-layer composition; callers retain the foreground paired to the fill. */
internal fun analystPressedColor(fill: Color, foreground: Color, opacity: Float = .08f): Color =
    foreground.copy(alpha = opacity).compositeOver(fill)


