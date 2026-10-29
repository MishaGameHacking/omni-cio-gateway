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
    primary = Color(0xFF68DDF2), onPrimary = Color(0xFF042C35),
    primaryContainer = Color(0xFF123845), onPrimaryContainer = Color(0xFFC7F6FF),
    inversePrimary = Color(0xFF006778),
    secondary = Color(0xFFB7A2FF), onSecondary = Color(0xFF291656),
    secondaryContainer = Color(0xFF30234F), onSecondaryContainer = Color(0xFFE8DDFF),
    tertiary = Color(0xFFD1ABFF), onTertiary = Color(0xFF3B165B),
    tertiaryContainer = Color(0xFF362448), onTertiaryContainer = Color(0xFFF0DCFF),
    background = Color(0xFF080D17), onBackground = Color(0xFFF2F5FC),
    surface = Color(0xFF101927), onSurface = Color(0xFFF2F5FC),
    surfaceVariant = Color(0xFF1D2B3D), onSurfaceVariant = Color(0xFFB6C3D8),
    surfaceContainerLowest = Color(0xFF070B13), surfaceContainerLow = Color(0xFF0C1421),
    surfaceContainer = Color(0xFF142031), surfaceContainerHigh = Color(0xFF19283B),
    surfaceContainerHighest = Color(0xFF21334A), surfaceBright = Color(0xFF2C3E55),
    surfaceDim = Color(0xFF080D17), surfaceTint = Color(0xFF68DDF2),
    inverseSurface = Color(0xFFE3EAF4), inverseOnSurface = Color(0xFF152031),
    outline = Color(0xFF8394AE), outlineVariant = Color(0xFF30425B),
    error = Color(0xFFFFA7B5), onError = Color(0xFF5D1328),
    errorContainer = Color(0xFF4D2031), onErrorContainer = Color(0xFFFFDCE3),
    scrim = Color(0xFF000000),
)
private val GraphiteSemantic = WorkspaceSemantic.copy(
    success = Color(0xFF74E3B7), onSuccess = Color(0xFF003825),
    successContainer = Color(0xFF123D30), onSuccessContainer = Color(0xFFB4F5D9),
    warning = Color(0xFFF5CB78), onWarning = Color(0xFF3E2C03),
    warningContainer = Color(0xFF41341D), onWarningContainer = Color(0xFFFFE5B1),
    info = Color(0xFF97C8FF), onInfo = Color(0xFF082C51),
    infoContainer = Color(0xFF18354F), onInfoContainer = Color(0xFFD0E7FF),
    disabledInk = Color(0xFF9AAAC1), disabledContainer = Color(0xFF1D2B3D),
    chartGrid = Color(0xFF2B3B52), chartAxis = Color(0xFF9AAAC1),
    chartSeparator = Color(0xFF101927), chartSelectedInner = Color(0xFF101927),
    chartSelectedOuter = Color(0xFFF2F5FC),
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



