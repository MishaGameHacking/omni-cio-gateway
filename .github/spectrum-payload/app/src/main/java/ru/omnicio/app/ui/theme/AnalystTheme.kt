package ru.omnicio.app.ui.theme

import android.graphics.Color as AndroidColor
import androidx.activity.ComponentActivity
import androidx.activity.compose.LocalActivity
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import ru.omnicio.app.ui.spectrum.DarkSpectrumPalette
import ru.omnicio.app.ui.spectrum.LightSpectrumPalette
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette

enum class ThemeMode(val title: String) { SYSTEM("Как в системе"), LIGHT("Светлая"), DARK("Тёмная") }
data class ThemePreference(val mode: ThemeMode, val select: (ThemeMode) -> Unit)
val LocalThemePreference = staticCompositionLocalOf { ThemePreference(ThemeMode.DARK) {} }
data class SpectrumMotionPreference(val enabled: Boolean, val select: (Boolean) -> Unit)
val LocalSpectrumMotionPreference = staticCompositionLocalOf { SpectrumMotionPreference(true) {} }

internal val LightColors = lightColorScheme(
    primary = Color(0xFF3154DE), onPrimary = Color.White,
    primaryContainer = Color(0xFFE6EAFF), onPrimaryContainer = Color(0xFF24385F),
    secondary = Color(0xFF663BC1), onSecondary = Color.White,
    secondaryContainer = Color(0xFFE8EEFF), onSecondaryContainer = Color(0xFF24395C),
    tertiary = Color(0xFF006C50), onTertiary = Color.White,
    tertiaryContainer = Color(0xFFD5F4E9), onTertiaryContainer = Color(0xFF004734),
    background = Color(0xFFF3F7FF), onBackground = Color(0xFF142239),
    surface = Color(0xFFFDFEFF), onSurface = Color(0xFF142239),
    surfaceVariant = Color(0xFFE4ECF7), onSurfaceVariant = Color(0xFF4D617A),
    surfaceContainerLowest = Color.White, surfaceContainerLow = Color(0xFFF1F6FF),
    surfaceContainer = Color(0xFFECF2FC), surfaceContainerHigh = Color(0xFFE5EDFA),
    surfaceContainerHighest = Color(0xFFDDE7F5),
    outline = Color(0xFF637894), outlineVariant = Color(0xFFCBDAEC),
    error = Color(0xFFAD243D), onError = Color.White,
    errorContainer = Color(0xFFFFE2E9), onErrorContainer = Color(0xFF71162C),
    surfaceTint = Color(0xFF3154DE),
)
internal val DarkColors = darkColorScheme(
    primary = Color(0xFF70DEFF), onPrimary = Color(0xFF002B3A),
    primaryContainer = Color(0xFF153870), onPrimaryContainer = Color(0xFFE5F1FF),
    secondary = Color(0xFFB7A2FF), onSecondary = Color(0xFF281453),
    secondaryContainer = Color(0xFF102E47), onSecondaryContainer = Color(0xFFE1F3FF),
    tertiary = Color(0xFF18E2AC), onTertiary = Color(0xFF003B2C),
    tertiaryContainer = Color(0xFF074C42), onTertiaryContainer = Color(0xFFB7FFE7),
    background = Color(0xFF030C17), onBackground = Color(0xFFF0F6FF),
    surface = Color(0xFF071725), onSurface = Color(0xFFF0F6FF),
    surfaceVariant = Color(0xFF15334B), onSurfaceVariant = Color(0xFFA9BED5),
    surfaceContainerLowest = Color(0xFF030C17), surfaceContainerLow = Color(0xFF061523),
    surfaceContainer = Color(0xFF091E30), surfaceContainerHigh = Color(0xFF0D273B),
    surfaceContainerHighest = Color(0xFF13324A),
    outline = Color(0xFF6C89A5), outlineVariant = Color(0xFF21435C),
    error = Color(0xFFFF94AA), onError = Color(0xFF560D23),
    errorContainer = Color(0xFF511D35), onErrorContainer = Color(0xFFFFDFE5),
    surfaceTint = Color(0xFF70DEFF),
)

@Composable
fun AnalystTheme(content: @Composable () -> Unit) {
    val context = LocalContext.current
    val activity = LocalActivity.current
    val preferences = remember(context) { context.applicationContext.getSharedPreferences("analyst_ai_settings", 0) }
    // An explicit existing choice is preserved. New installations open in the reference's midnight theme.
    var modeName by rememberSaveable { mutableStateOf(preferences.getString("theme_mode", ThemeMode.DARK.name) ?: ThemeMode.DARK.name) }
    var motionEnabled by rememberSaveable { mutableStateOf(preferences.getBoolean("spectrum_motion", true)) }
    val mode = ThemeMode.entries.firstOrNull { it.name == modeName } ?: ThemeMode.DARK
    val systemDark = isSystemInDarkTheme()
    val dark = when (mode) { ThemeMode.SYSTEM -> systemDark; ThemeMode.LIGHT -> false; ThemeMode.DARK -> true }
    SideEffect {
        (activity as? ComponentActivity)?.enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.auto(AndroidColor.TRANSPARENT, AndroidColor.TRANSPARENT) { dark },
            navigationBarStyle = SystemBarStyle.auto(AndroidColor.TRANSPARENT, AndroidColor.TRANSPARENT) { dark },
        )
        activity?.window?.isNavigationBarContrastEnforced = false
    }
    val theme = ThemePreference(mode) { selected -> modeName = selected.name; preferences.edit().putString("theme_mode", selected.name).apply() }
    val motion = SpectrumMotionPreference(motionEnabled) { enabled -> motionEnabled = enabled; preferences.edit().putBoolean("spectrum_motion", enabled).apply() }
    CompositionLocalProvider(LocalThemePreference provides theme, LocalSpectrumMotionPreference provides motion,
        LocalSpectrumPalette provides if (dark) DarkSpectrumPalette else LightSpectrumPalette) {
        MaterialTheme(colorScheme = if (dark) DarkColors else LightColors, typography = SpectrumTypography, shapes = SpectrumShapes) {
            // MaterialTheme does not set a content colour for arbitrary Box/Canvas roots.
            // Explicitly pair every custom background with its readable foreground.
            CompositionLocalProvider(LocalContentColor provides MaterialTheme.colorScheme.onBackground, content = content)
        }
    }
}
