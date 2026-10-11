package ru.omnicio.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val ActionYellow = Color(0xFFFFDD2D)
private val Positive = Color(0xFF13A85B)
private val DarkBackground = Color(0xFF0A0B0D)
private val DarkSurface = Color(0xFF151619)
private val DarkRaised = Color(0xFF202126)
private val DarkText = Color(0xFFF7F7F8)
private val DarkMuted = Color(0xFFA7AAB2)
private val LightInk = Color(0xFF151619)
private val LightBackground = Color(0xFFF5F6F8)
private val LightSurface = Color(0xFFFFFFFF)
private val LightRaised = Color(0xFFEEF0F3)

private val DarkColors = darkColorScheme(
    primary = ActionYellow,
    onPrimary = Color(0xFF161300),
    primaryContainer = Color(0xFF3B3412),
    onPrimaryContainer = Color(0xFFFFE86D),
    secondary = Color(0xFFD7D9DE),
    onSecondary = DarkBackground,
    secondaryContainer = DarkRaised,
    onSecondaryContainer = DarkText,
    tertiary = Positive,
    onTertiary = Color.White,
    background = DarkBackground,
    onBackground = DarkText,
    surface = DarkSurface,
    onSurface = DarkText,
    surfaceVariant = DarkRaised,
    onSurfaceVariant = DarkMuted,
    outline = Color(0xFF3A3C43),
    error = Color(0xFFFF626A),
    onError = Color(0xFF260006),
)

private val LightColors = lightColorScheme(
    primary = Color(0xFF705900),
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

