package ru.omnicio.app.ui.theme

import android.graphics.Color as AndroidColor
import androidx.activity.ComponentActivity
import androidx.activity.compose.LocalActivity
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

enum class ThemeMode(val title: String) {
    SYSTEM("Как в системе"), LIGHT("Светлая"), DARK("Тёмная");
}

data class ThemePreference(val mode: ThemeMode, val select: (ThemeMode) -> Unit)
val LocalThemePreference = staticCompositionLocalOf {
    ThemePreference(ThemeMode.SYSTEM) { }
}

private val LightColors = lightColorScheme(
    primary = Color(0xFF326FC8), onPrimary = Color.White,
    background = Color(0xFFF5F6F8), onBackground = Color(0xFF191A1D),
    surface = Color.White, onSurface = Color(0xFF191A1D),
    surfaceVariant = Color(0xFFE9EBEF), onSurfaceVariant = Color(0xFF626974),
    surfaceContainer = Color(0xFFF0F1F4), surfaceContainerHigh = Color(0xFFE9EBEF),
    outline = Color(0xFF737A85), outlineVariant = Color(0xFFDDE0E5),
    secondaryContainer = Color(0xFFE5EDFA), onSecondaryContainer = Color(0xFF203650),
    error = Color(0xFFB42330),
)
private val DarkColors = darkColorScheme(
    primary = Color(0xFF76A9FA), onPrimary = Color(0xFF0C2344),
    background = Color(0xFF111111), onBackground = Color(0xFFF4F4F5),
    surface = Color(0xFF1E1E1E), onSurface = Color(0xFFF4F4F5),
    surfaceVariant = Color(0xFF2C2C2C), onSurfaceVariant = Color(0xFFA4A7AE),
    surfaceContainer = Color(0xFF242424), surfaceContainerHigh = Color(0xFF303030),
    outline = Color(0xFF8E9299), outlineVariant = Color(0xFF363636),
    secondaryContainer = Color(0xFF2C2C2C), onSecondaryContainer = Color(0xFFE6E8EC),
    error = Color(0xFFFF7784),
)

@Composable
fun AnalystTheme(content: @Composable () -> Unit) {
    val context = LocalContext.current
    val activity = LocalActivity.current
    val preferences = remember(context) {
        context.applicationContext.getSharedPreferences("analyst_ai_settings", 0)
    }
    var modeName by rememberSaveable {
        mutableStateOf(preferences.getString("theme_mode", ThemeMode.SYSTEM.name) ?: ThemeMode.SYSTEM.name)
    }
    val mode = ThemeMode.entries.firstOrNull { it.name == modeName } ?: ThemeMode.SYSTEM
    val systemDark = isSystemInDarkTheme()
    val dark = when (mode) {
        ThemeMode.SYSTEM -> systemDark
        ThemeMode.LIGHT -> false
        ThemeMode.DARK -> true
    }
    SideEffect {
        (activity as? ComponentActivity)?.enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.auto(AndroidColor.TRANSPARENT, AndroidColor.TRANSPARENT) { dark },
            navigationBarStyle = SystemBarStyle.auto(AndroidColor.TRANSPARENT, AndroidColor.TRANSPARENT) { dark },
        )
        activity?.window?.isNavigationBarContrastEnforced = false
    }
    val preference = ThemePreference(mode) { selected ->
        modeName = selected.name
        preferences.edit().putString("theme_mode", selected.name).apply()
    }
    CompositionLocalProvider(LocalThemePreference provides preference) {
        MaterialTheme(colorScheme = if (dark) DarkColors else LightColors, content = content)
    }
}
