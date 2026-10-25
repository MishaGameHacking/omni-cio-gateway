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
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalInspectionMode
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
    primary = Color(0xFF0F766E), onPrimary = Color.White,
    primaryContainer = Color(0xFFCCFBF1), onPrimaryContainer = Color(0xFF134E4A),
    secondary = Color(0xFF0F766E), onSecondary = Color.White,
    secondaryContainer = Color(0xFFCCFBF1), onSecondaryContainer = Color(0xFF134E4A),
    tertiary = Color(0xFF047857), onTertiary = Color.White,
    background = Color(0xFFF8FAFC), onBackground = Color(0xFF0F172A),
    surface = Color.White, onSurface = Color(0xFF0F172A),
    surfaceVariant = Color(0xFFE2E8F0), onSurfaceVariant = Color(0xFF475569),
    surfaceContainer = Color(0xFFF1F5F9), surfaceContainerHigh = Color(0xFFE2E8F0),
    outline = Color(0xFF475569), outlineVariant = Color(0xFF94A3B8),
    error = Color(0xFFB91C1C), onError = Color.White,
    errorContainer = Color(0xFFFEE2E2), onErrorContainer = Color(0xFF7F1D1D),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF5EEAD4), onPrimary = Color(0xFF0F172A),
    primaryContainer = Color(0xFF134E4A), onPrimaryContainer = Color(0xFFF0FDFA),
    secondary = Color(0xFF5EEAD4), onSecondary = Color(0xFF0F172A),
    secondaryContainer = Color(0xFF134E4A), onSecondaryContainer = Color(0xFFF0FDFA),
    tertiary = Color(0xFF6EE7B7), onTertiary = Color(0xFF0F172A),
    background = Color(0xFF0F172A), onBackground = Color(0xFFF8FAFC),
    surface = Color(0xFF1E293B), onSurface = Color(0xFFF8FAFC),
    surfaceVariant = Color(0xFF334155), onSurfaceVariant = Color(0xFFCBD5E1),
    surfaceContainer = Color(0xFF1E293B), surfaceContainerHigh = Color(0xFF334155),
    outline = Color(0xFF94A3B8), outlineVariant = Color(0xFF64748B),
    error = Color(0xFFFDA4AF), onError = Color(0xFF450A0A),
    errorContainer = Color(0xFF7F1D1D), onErrorContainer = Color(0xFFFEE2E2),
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
    if (LocalInspectionMode.current) {
        // The caller supplies in-memory appearance values for an explicit host preview.
        AnalystThemeContent(content)
    } else WorkspacePreferencesProvider { AnalystThemeContent(content) }
}

@Composable
private fun AnalystThemeContent(content: @Composable () -> Unit) {
    val context = LocalContext.current
    val inspection = LocalInspectionMode.current
    val activity = if (inspection) null else LocalActivity.current
    val editorRestorationOwner = remember { UUID.randomUUID().toString() }
    val preferences = remember(context, inspection) {
        if (inspection) null else context.applicationContext.getSharedPreferences("analyst_ai_settings", 0)
    }
    val defaultMode = if (inspection) ThemeMode.SYSTEM else ThemeMode.DARK
    var modeName by rememberSaveable {
        mutableStateOf(
            preferences?.getString("theme_mode", defaultMode.name) ?: defaultMode.name,
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
        preferences?.edit()?.putString("theme_mode", selected.name)?.apply()
    }
    val themePreference = ThemePreference(mode, preview = { previewMode = it }, cancelPreview = { previewMode = null },
        applyPreview = { previewMode?.let(saveTheme) }, select = saveTheme)
    val motionPreference = SpectrumMotionPreference(workspace.value.motion != MotionLevel.OFF) { enabled ->
        workspace.update(workspace.value.copy(motion = if (enabled) MotionLevel.LIVE else MotionLevel.OFF))
        preferences?.edit()?.putBoolean("spectrum_motion", enabled)?.apply()
    }
    val palette = workspacePalette(if (dark) DarkSpectrumPalette else LightSpectrumPalette,
        workspace.value.accent, dark)
    val baseColors = if (dark) DarkColors else LightColors
    val accentContainer = lerp(palette.card, palette.cyan, .14f)
    val colors = baseColors.copy(
        primary = palette.cyan, onPrimary = if (dark) Color(0xFF0F172A) else Color.White,
        primaryContainer = accentContainer, onPrimaryContainer = baseColors.onSurface,
        secondary = palette.cyan, onSecondary = if (dark) Color(0xFF0F172A) else Color.White,
        secondaryContainer = accentContainer, onSecondaryContainer = baseColors.onSurface,
        tertiary = palette.emerald, surfaceTint = palette.cyan,
    )
    CompositionLocalProvider(
        LocalEditorRestorationOwner provides editorRestorationOwner,
        LocalThemePreference provides themePreference,
        LocalSpectrumMotionPreference provides motionPreference,
        LocalSpectrumPalette provides palette,
    ) {
        MaterialTheme(
            colorScheme = colors,
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


private fun workspacePalette(base: ru.omnicio.app.ui.spectrum.SpectrumPalette, accent: AccentStyle, dark: Boolean): ru.omnicio.app.ui.spectrum.SpectrumPalette {
    val color = when (accent) {
        AccentStyle.AURORA -> base.cyan
        AccentStyle.OCEAN -> if (dark) Color(0xFF93C5FD) else Color(0xFF1D4ED8)
        AccentStyle.IRIS -> if (dark) Color(0xFFC4B5FD) else Color(0xFF6D28D9)
    }
    return base.copy(cyan = color, blue = color, violet = color)
}
