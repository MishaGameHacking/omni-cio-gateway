package ru.omnicio.app.ui.theme

import androidx.compose.material3.ColorScheme
import androidx.compose.material3.lightColorScheme
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
    primary = Color(0xFF2463EB),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFE4EDFF),
    onPrimaryContainer = Color(0xFF153C89),
    inversePrimary = Color(0xFF2463EB),
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
    surfaceTint = Color(0xFF2463EB),
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

/** One style for every saved legacy mode/accent and every system configuration. */
@Suppress("UNUSED_PARAMETER")
fun analystColors(dark: Boolean = true, accent: AccentStyle = AccentStyle.AURORA): AnalystColorSet =
    AnalystColorSet(WorkspaceColors, WorkspaceSemantic, listOf(WorkspaceColors.secondary, WorkspaceColors.primary,
        WorkspaceSemantic.success, WorkspaceColors.tertiary, WorkspaceSemantic.warning, WorkspaceColors.error))

/** Actual state-layer composition; callers retain the foreground paired to the fill. */
internal fun analystPressedColor(fill: Color, foreground: Color, opacity: Float = .08f): Color =
    foreground.copy(alpha = opacity).compositeOver(fill)

