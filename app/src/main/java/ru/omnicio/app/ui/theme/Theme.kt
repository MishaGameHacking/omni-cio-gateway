package ru.omnicio.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val ActionYellow = Color(0xFFFFDD2D)
private val Graphite = Color(0xFF0F1012)
private val GraphiteSurface = Color(0xFF18191C)
private val GraphiteRaised = Color(0xFF23252A)
private val DarkText = Color(0xFFF5F5F6)
private val DarkMuted = Color(0xFFA6A9B0)
private val LightInk = Color(0xFF17181A)
private val LightBackground = Color(0xFFF4F5F6)
private val LightSurface = Color(0xFFFFFFFF)
private val LightRaised = Color(0xFFE9EBEE)

private val DarkColors = darkColorScheme(
    primary = ActionYellow,
    onPrimary = Graphite,
    primaryContainer = Color(0xFF3A3516),
    onPrimaryContainer = ActionYellow,
    secondary = Color(0xFFD7D9DE),
    onSecondary = Graphite,
    secondaryContainer = GraphiteRaised,
    onSecondaryContainer = DarkText,
    background = Graphite,
    onBackground = DarkText,
    surface = GraphiteSurface,
    onSurface = DarkText,
    surfaceVariant = GraphiteRaised,
    onSurfaceVariant = DarkMuted,
    outline = Color(0xFF3A3C42),
    error = Color(0xFFFF626A),
    onError = Color(0xFF260006),
)

private val LightColors = lightColorScheme(
    primary = ActionYellow,
    onPrimary = LightInk,
    primaryContainer = Color(0xFFFFF2A3),
    onPrimaryContainer = Color(0xFF342D00),
    secondary = Color(0xFF55585E),
    onSecondary = Color.White,
    secondaryContainer = LightRaised,
    onSecondaryContainer = LightInk,
    background = LightBackground,
    onBackground = LightInk,
    surface = LightSurface,
    onSurface = LightInk,
    surfaceVariant = LightRaised,
    onSurfaceVariant = Color(0xFF676B72),
    outline = Color(0xFFD1D4D9),
    error = Color(0xFFC62836),
    onError = Color.White,
)

@Composable
fun OmnicioTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        typography = OmniTypography,
        shapes = OmniShapes,
        content = content,
    )
}
