package ru.omnicio.app.ui.theme

import androidx.compose.material3.ColorScheme
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

private val DarkColors = darkColorScheme(
    primary = Color(0xFFA99AFF),
    onPrimary = Color(0xFF1B0D45),
    primaryContainer = Color(0xFF403199),
    onPrimaryContainer = Color(0xFFFFFFFF),
    inversePrimary = Color(0xFFA99AFF),
    secondary = Color(0xFF69DFFF),
    onSecondary = Color(0xFF023343),
    secondaryContainer = Color(0xFF07384B),
    onSecondaryContainer = Color(0xFFD7F6FF),
    tertiary = Color(0xFF8FADFF),
    onTertiary = Color(0xFF09265C),
    tertiaryContainer = Color(0xFF233C75),
    onTertiaryContainer = Color(0xFFE1EBFF),
    background = Color(0xFF050E1C),
    onBackground = Color(0xFFEDF5FF),
    surface = Color(0xFF0A1A2C),
    onSurface = Color(0xFFEDF5FF),
    surfaceVariant = Color(0xFF132C43),
    onSurfaceVariant = Color(0xFFACC3DC),
    surfaceTint = Color(0xFFA99AFF),
    inverseSurface = Color(0xFFE3EDFA),
    inverseOnSurface = Color(0xFF15253C),
    error = Color(0xFFFF99B2),
    onError = Color(0xFF510D29),
    errorContainer = Color(0xFF542136),
    onErrorContainer = Color(0xFFFFE1EB),
    outline = Color(0xFF88A4C5),
    outlineVariant = Color(0xFF294763),
    scrim = Color(0xFF01060D),
    surfaceBright = Color(0xFF1A334D),
    surfaceDim = Color(0xFF050E1C),
    surfaceContainer = Color(0xFF0D2136),
    surfaceContainerHigh = Color(0xFF10273E),
    surfaceContainerHighest = Color(0xFF132C43),
    surfaceContainerLow = Color(0xFF0A1B2E),
    surfaceContainerLowest = Color(0xFF030B16),
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

private val DarkSemantic = AnalystSemanticColors(
    success = Color(0xFF55E8B2),
    onSuccess = Color(0xFF063B2B),
    successContainer = Color(0xFF0B3C32),
    onSuccessContainer = Color(0xFFC5FFE7),
    warning = Color(0xFFFFD177),
    onWarning = Color(0xFF412B05),
    warningContainer = Color(0xFF4D3615),
    onWarningContainer = Color(0xFFFFE7B6),
    info = Color(0xFF73C7FF),
    onInfo = Color(0xFF052D4B),
    infoContainer = Color(0xFF123451),
    onInfoContainer = Color(0xFFD5EEFF),
    disabledInk = Color(0xFF99AEC7),
    disabledContainer = Color(0xFF152B41),
    chartGrid = Color(0xFF294763),
    chartAxis = Color(0xFF88A4C5),
    chartSeparator = Color(0xFF0A1A2C),
    chartSelectedInner = Color(0xFF050E1C),
    chartSelectedOuter = Color(0xFFEDF5FF),
)

/** One style for every saved legacy mode/accent and every system configuration. */
@Suppress("UNUSED_PARAMETER")
fun analystColors(dark: Boolean = true, accent: AccentStyle = AccentStyle.AURORA): AnalystColorSet =
    AnalystColorSet(DarkColors, DarkSemantic, listOf(DarkColors.secondary, DarkColors.primary,
        DarkSemantic.success, DarkColors.tertiary, DarkSemantic.warning, DarkColors.error))

/** Actual state-layer composition; callers retain the foreground paired to the fill. */
internal fun analystPressedColor(fill: Color, foreground: Color, opacity: Float = .08f): Color =
    foreground.copy(alpha = opacity).compositeOver(fill)
