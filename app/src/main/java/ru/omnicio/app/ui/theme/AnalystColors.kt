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
    inversePrimary = Color(0xFFA869FF),
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
    primaryFixed = Color(0xFFC7F6FF),
    primaryFixedDim = Color(0xFF68DDF2),
    onPrimaryFixed = Color(0xFF042C35),
    onPrimaryFixedVariant = Color(0xFF123845),
    secondaryFixed = Color(0xFFE8DDFF),
    secondaryFixedDim = Color(0xFFB7A2FF),
    onSecondaryFixed = Color(0xFF291656),
    onSecondaryFixedVariant = Color(0xFF30234F),
    tertiaryFixed = Color(0xFFF0DCFF),
    tertiaryFixedDim = Color(0xFFD1ABFF),
    onTertiaryFixed = Color(0xFF3B165B),
    onTertiaryFixedVariant = Color(0xFF362448),
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
    primary = Color(0xFFA869FF), onPrimary = Color(0xFF130720),
    primaryContainer = Color(0xFF241039), onPrimaryContainer = Color(0xFFEEDFFF),
    inversePrimary = Color(0xFF205DD7),
    secondary = Color(0xFF56D3E5), onSecondary = Color(0xFF032C32),
    secondaryContainer = Color(0xFF102B31), onSecondaryContainer = Color(0xFFC7F5FA),
    tertiary = Color(0xFFC9AEFF), onTertiary = Color(0xFF241034),
    tertiaryContainer = Color(0xFF2B203A), onTertiaryContainer = Color(0xFFF1E7FF),
    background = Color(0xFF050508), onBackground = Color(0xFFF4F3F7),
    surface = Color(0xFF0B0B10), onSurface = Color(0xFFF4F3F7),
    surfaceVariant = Color(0xFF19191F), onSurfaceVariant = Color(0xFFAFACBA),
    surfaceContainerLowest = Color(0xFF030305), surfaceContainerLow = Color(0xFF08080D),
    surfaceContainer = Color(0xFF111117), surfaceContainerHigh = Color(0xFF18181F),
    surfaceContainerHighest = Color(0xFF202028), surfaceBright = Color(0xFF24242E),
    surfaceDim = Color(0xFF050508), surfaceTint = Color(0xFFA869FF),
    inverseSurface = Color(0xFFE8E6ED), inverseOnSurface = Color(0xFF16151D),
    outline = Color(0xFF8E8A9B), outlineVariant = Color(0xFF25242E),
    error = Color(0xFFFF7387), onError = Color(0xFF330913),
    errorContainer = Color(0xFF38151F), onErrorContainer = Color(0xFFFFDCE3),
    scrim = Color(0xFF000000),
    primaryFixed = Color(0xFFC7F6FF), primaryFixedDim = Color(0xFF68DDF2),
    onPrimaryFixed = Color(0xFF042C35), onPrimaryFixedVariant = Color(0xFF123845),
    secondaryFixed = Color(0xFFE8DDFF), secondaryFixedDim = Color(0xFFB7A2FF),
    onSecondaryFixed = Color(0xFF291656), onSecondaryFixedVariant = Color(0xFF30234F),
    tertiaryFixed = Color(0xFFF0DCFF), tertiaryFixedDim = Color(0xFFD1ABFF),
    onTertiaryFixed = Color(0xFF3B165B), onTertiaryFixedVariant = Color(0xFF362448),
)
private val GraphiteSemantic = WorkspaceSemantic.copy(
    success = Color(0xFFA9E34B), onSuccess = Color(0xFF152200),
    successContainer = Color(0xFF1C2A12), onSuccessContainer = Color(0xFFDEFFC1),
    warning = Color(0xFFF2C66D), onWarning = Color(0xFF3E2C03),
    warningContainer = Color(0xFF41341D), onWarningContainer = Color(0xFFFFE5B1),
    info = Color(0xFF56D3E5), onInfo = Color(0xFF082C51),
    infoContainer = Color(0xFF18354F), onInfoContainer = Color(0xFFD0E7FF),
    disabledInk = Color(0xFFAFACBA), disabledContainer = Color(0xFF19191F),
    chartGrid = Color(0xFF25242E), chartAxis = Color(0xFFAFACBA),
    chartSeparator = Color(0xFF0B0B10), chartSelectedInner = Color(0xFF0B0B10),
    chartSelectedOuter = Color(0xFFF4F3F7),
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




