package ru.omnicio.app.ui.theme

import android.graphics.Color as AndroidColor
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.LocalActivity
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
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
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import ru.omnicio.app.ui.workspace.*
import ru.omnicio.app.ui.spectrum.DarkSpectrumPalette
import ru.omnicio.app.ui.spectrum.LightSpectrumPalette
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette
import ru.omnicio.app.ui.spectrum.LocalEditorRestorationOwner
import ru.omnicio.app.ui.spatial.SpatialSceneRoot
import ru.omnicio.app.ui.spatial.SpatialMotion
import java.util.UUID

enum class ThemeMode(val title: String) {
    SYSTEM("Как в системе"), LIGHT("Светлая"), DARK("Тёмная");
}

data class ThemePreference(val mode: ThemeMode, val preview: (ThemeMode) -> Unit = {},
    val cancelPreview: () -> Unit = {}, val applyPreview: () -> Unit = {}, val select: (ThemeMode) -> Unit)
val LocalThemePreference = staticCompositionLocalOf {
    ThemePreference(ThemeMode.DARK) { }
}

data class SpectrumMotionPreference(
    val enabled: Boolean,
    val select: (Boolean) -> Unit,
)

val LocalSpectrumMotionPreference = staticCompositionLocalOf {
    SpectrumMotionPreference(enabled = true) { }
}

private val LightColors = lightColorScheme(
    primary = Color(0xFF205FCF),
    onPrimary = Color.White,
    secondary = Color(0xFF6E43C8),
    onSecondary = Color.White,
    tertiary = Color(0xFF007D63),
    onTertiary = Color.White,
    background = Color(0xFFF5F8FF),
    onBackground = Color(0xFF101722),
    surface = Color.White,
    onSurface = Color(0xFF101722),
    surfaceVariant = Color(0xFFE6ECF7),
    onSurfaceVariant = Color(0xFF586274),
    surfaceContainer = Color(0xFFF0F4FB),
    surfaceContainerHigh = Color(0xFFE7EDF7),
    outline = Color(0xFF69758A),
    outlineVariant = Color(0xFFD5DEED),
    secondaryContainer = Color(0xFFE9E4FF),
    onSecondaryContainer = Color(0xFF2F1D60),
    error = Color(0xFFB42330),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF70E0D2),
    onPrimary = Color(0xFF001E29),
    secondary = Color(0xFFAF99FF),
    onSecondary = Color(0xFF1F0D50),
    tertiary = Color(0xFF19E6A2),
    onTertiary = Color(0xFF002B21),
    background = Color(0xFF090E18),
    onBackground = Color(0xFFF4F7FF),
    surface = Color(0xFF121D2B),
    onSurface = Color(0xFFF4F7FF),
    surfaceVariant = Color(0xFF10283C),
    onSurfaceVariant = Color(0xFFB8C2D2),
    surfaceContainer = Color(0xFF121D2B),
    surfaceContainerHigh = Color(0xFF192A3B),
    outline = Color(0xFF8FA1B8),
    outlineVariant = Color(0xFF254158),
    secondaryContainer = Color(0xFF201949),
    onSecondaryContainer = Color(0xFFECE8FF),
    error = Color(0xFFFF7D8D),
)

private val AnalystTypography = Typography(
    displayLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Bold,
        fontSize = 46.sp,
        lineHeight = 52.sp,
        letterSpacing = (-1.2).sp,
    ),
    headlineLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Bold,
        fontSize = 34.sp,
        lineHeight = 39.sp,
        letterSpacing = (-0.4).sp,
    ),
    headlineMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Bold,
        fontSize = 26.sp,
        lineHeight = 33.sp,
    ),
    titleLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.SemiBold,
        fontSize = 21.sp,
        lineHeight = 27.sp,
    ),
    titleMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.SemiBold,
        fontSize = 17.sp,
        lineHeight = 23.sp,
    ),
    bodyLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Normal,
        fontSize = 17.sp,
        lineHeight = 25.sp,
    ),
    bodyMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Normal,
        fontSize = 16.sp,
        lineHeight = 22.sp,
    ),
    bodySmall = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Normal,
        fontSize = 13.sp,
        lineHeight = 18.sp,
    ),
    labelLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.SemiBold,
        fontSize = 16.sp,
        lineHeight = 20.sp,
    ),
    labelMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.SemiBold,
        fontSize = 13.sp,
        lineHeight = 18.sp,
    ),
    labelSmall = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Medium,
        fontSize = 11.sp,
        lineHeight = 15.sp,
    ),
)

@Composable
fun AnalystTheme(content: @Composable () -> Unit) {
    WorkspacePreferencesProvider { AnalystThemeContent(content) }
}

@Composable
private fun AnalystThemeContent(content: @Composable () -> Unit) {
    val context = LocalContext.current
    val activity = LocalActivity.current
    val editorRestorationOwner = remember { UUID.randomUUID().toString() }
    val preferences = remember(context) {
        context.applicationContext.getSharedPreferences("analyst_ai_settings", 0)
    }
    var modeName by rememberSaveable {
        mutableStateOf(
            preferences.getString("theme_mode", ThemeMode.DARK.name)
                ?: ThemeMode.DARK.name,
        )
    }
    var previewMode by remember { mutableStateOf<ThemeMode?>(null) }
    val mode = previewMode ?: ThemeMode.entries.firstOrNull { it.name == modeName } ?: ThemeMode.DARK
    val workspace = LocalWorkspacePreferences.current
    val systemDark = isSystemInDarkTheme()
    val dark = when (mode) {
        ThemeMode.SYSTEM -> systemDark
        ThemeMode.LIGHT -> false
        ThemeMode.DARK -> true
    }
    SideEffect {
        (activity as? ComponentActivity)?.enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.auto(
                AndroidColor.TRANSPARENT,
                AndroidColor.TRANSPARENT,
            ) { dark },
            navigationBarStyle = SystemBarStyle.auto(
                AndroidColor.TRANSPARENT,
                AndroidColor.TRANSPARENT,
            ) { dark },
        )
        activity?.window?.isNavigationBarContrastEnforced = false
    }
    val saveTheme: (ThemeMode) -> Unit = { selected ->
        modeName = selected.name
        previewMode = null
        preferences.edit().putString("theme_mode", selected.name).apply()
    }
    val themePreference = ThemePreference(mode, preview = { previewMode = it }, cancelPreview = { previewMode = null },
        applyPreview = { previewMode?.let(saveTheme) }, select = saveTheme)
    val motionPreference = SpectrumMotionPreference(workspace.value.motion != MotionLevel.OFF) { enabled ->
        workspace.update(workspace.value.copy(motion = if (enabled) MotionLevel.LIVE else MotionLevel.OFF))
        preferences.edit().putBoolean("spectrum_motion", enabled).apply()
    }
    CompositionLocalProvider(
        LocalEditorRestorationOwner provides editorRestorationOwner,
        LocalThemePreference provides themePreference,
        LocalSpectrumMotionPreference provides motionPreference,
        LocalSpectrumPalette provides workspacePalette(if (dark) DarkSpectrumPalette else LightSpectrumPalette,
            LocalWorkspacePreferences.current.value.accent, dark),
    ) {
        MaterialTheme(
            colorScheme = if (dark) DarkColors else LightColors,
            typography = AnalystTypography,
        ) {
            // Transparent scaffolds and text outside cards must not inherit the
            // framework's default black LocalContentColor in the dark theme.
            CompositionLocalProvider(LocalContentColor provides MaterialTheme.colorScheme.onBackground) {
                SpatialSceneRoot(modifier = androidx.compose.ui.Modifier.fillMaxSize(),
                    motion = when (workspace.value.motion) { MotionLevel.LIVE -> SpatialMotion.Live; MotionLevel.SUBDUED -> SpatialMotion.Subdued; MotionLevel.OFF -> SpatialMotion.Off },
                    tactile = workspace.value.haptics, opaque = workspace.value.brightLight,
                    navigationProgress = LocalWorkspaceBackProgress.current) { content() }
            }
        }
    }
}


private fun workspacePalette(base: ru.omnicio.app.ui.spectrum.SpectrumPalette, accent: AccentStyle, dark: Boolean) = when (accent) {
    AccentStyle.AURORA -> base
    AccentStyle.OCEAN -> base.copy(cyan = if (dark) Color(0xFF69D8FF) else Color(0xFF006D8F),
        violet = if (dark) Color(0xFF68A6FF) else Color(0xFF345CB4))
    AccentStyle.IRIS -> base.copy(cyan = if (dark) Color(0xFFC4AEFF) else Color(0xFF6B43AD),
        violet = if (dark) Color(0xFFEF9CC6) else Color(0xFF9E3970))
}
