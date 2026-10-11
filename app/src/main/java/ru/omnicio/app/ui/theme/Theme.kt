package ru.omnicio.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val ActionYellow = Color(0xFFFFDD2D)
private val Positive = Color(0xFF13A85B)
private val DarkBackground = Color(0xFF111111)
private val DarkSurface = Color(0xFF1E1E1E)
private val DarkRaised = Color(0xFF2B2B2B)
private val DarkText = Color(0xFFF7F7F8)
private val DarkMuted = Color(0xFFA1A1A6)
private val LightInk = Color(0xFF1E1E1E)
private val LightBackground = Color(0xFFF5F6F8)
private val LightSurface = Color(0xFFFFFFFF)
private val LightRaised = Color(0xFFEEF0F3)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF79AAFF),
    onPrimary = Color(0xFF101E34),
    primaryContainer = DarkRaised,
    onPrimaryContainer = DarkText,
    secondary = Color(0xFFD7D9DE),
    onSecondary = DarkBackground,
    secondaryContainer = DarkRaised,
    onSecondaryContainer = DarkText,
    tertiary = Positive,
    onTertiary = Color.White,
    background = DarkBackground,
    onBackground = DarkText,
    surface = DarkSurface,
    surfaceContainer = DarkSurface,
    surfaceContainerLow = DarkSurface,
    surfaceContainerHigh = DarkRaised,
    surfaceContainerHighest = DarkRaised,
    outlineVariant = Color(0xFF343434),
    onSurface = DarkText,
    surfaceVariant = DarkRaised,
    onSurfaceVariant = DarkMuted,
    outline = Color(0xFF3A3C43),
    error = Color(0xFFFF626A),
    onError = Color(0xFF260006),
)

private val LightColors = lightColorScheme(
    primary = Color(0xFF2367C4),
    onPrimary = Color.White,
    primaryContainer = ActionYellow,
    onPrimaryContainer = Color(0xFF342D00),
    secondary = Color(0xFF55585E),
    onSecondary = Color.White,
    secondaryContainer = LightRaised,
    onSecondaryContainer = LightInk,
    tertiary = Positive,
    onTertiary = Color.White,
    background = LightBackground,
    onBackground = LightInk,
    surface = LightSurface,
    surfaceContainer = LightSurface,
    surfaceContainerLow = LightSurface,
    surfaceContainerHigh = LightRaised,
    surfaceContainerHighest = LightRaised,
    outlineVariant = Color(0xFFDADDE2),
    onSurface = LightInk,
    surfaceVariant = LightRaised,
    onSurfaceVariant = Color(0xFF606570),
    outline = Color(0xFF747982),
    error = Color(0xFFD92D3A),
    onError = Color.White,
)

@Composable
fun OmnicioTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        typography = OmniTypography,
        shapes = OmniShapes,
        content = content,
    )
}


