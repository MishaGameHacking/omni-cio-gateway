package ru.omnicio.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val DarkColors = darkColorScheme(
    primary = Color(0xFF2369E8),
    onPrimary = Color.White,
    secondary = Color(0xFF6BAFFF),
    tertiary = Color(0xFFB873FA),
    background = Color(0xFF07121E),
    onBackground = Color(0xFFF2F6FD),
    surface = Color(0xFF0D1C29),
    onSurface = Color(0xFFF2F6FD),
    surfaceVariant = Color(0xFF12283C),
    onSurfaceVariant = Color(0xFF9AACBF),
    error = Color(0xFFFF6476),
)
private val LightColors = lightColorScheme(
    primary = Color(0xFF1863EC),
    onPrimary = Color.White,
    secondary = Color(0xFF1D63BB),
    tertiary = Color(0xFF8544D1),
    background = Color(0xFFEFF4FA),
    onBackground = Color(0xFF142638),
    surface = Color(0xFFF5F8FC),
    onSurface = Color(0xFF142638),
    surfaceVariant = Color(0xFFEAF2FC),
    onSurfaceVariant = Color(0xFF536A81),
    error = Color(0xFFC83149),
)
@Composable
fun OmnicioTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        content = content,
    )
}
