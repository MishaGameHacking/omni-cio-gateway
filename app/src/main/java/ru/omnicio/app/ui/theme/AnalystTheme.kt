package ru.omnicio.app.ui.theme

import android.graphics.Color as AndroidColor
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.LocalActivity
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.text.selection.LocalTextSelectionColors
import androidx.compose.foundation.text.selection.TextSelectionColors
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.runtime.*
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.remember
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import ru.omnicio.app.ui.workspace.*
import ru.omnicio.app.ui.spectrum.LocalSpectrumPalette
import ru.omnicio.app.ui.spectrum.spectrumPalette
import ru.omnicio.app.ui.spectrum.LocalEditorRestorationOwner
import ru.omnicio.app.ui.spatial.SpatialSceneRoot
import ru.omnicio.app.ui.spatial.SpatialMotion
import java.util.UUID

enum class ThemeMode(val title: String) {
    SYSTEM("Как в системе"), LIGHT("Светлая"), DARK("Тёмная");
}

data class ThemePreference(val mode: ThemeMode, val preview: (ThemeMode) -> Unit = {},
    val cancelPreview: () -> Unit = {}, val applyPreview: () -> Unit = {},
    val systemThemeUnavailable: Boolean = false, val select: (ThemeMode) -> Unit)
val LocalThemePreference = staticCompositionLocalOf {
    ThemePreference(ThemeMode.LIGHT) { }
}

data class SpectrumMotionPreference(
    val enabled: Boolean,
    val select: (Boolean) -> Unit,
)

val LocalSpectrumMotionPreference = staticCompositionLocalOf {
    SpectrumMotionPreference(enabled = true) { }
}

/** Resolve an explicit theme, with the last known/system appearance as fallback. */
@Suppress("UNUSED_PARAMETER")
internal fun displayedThemeDark(mode: ThemeMode, system: SystemThemeObservation,
    lastDisplayed: Boolean?, appConfigurationDark: Boolean): Boolean = when (mode) {
    ThemeMode.LIGHT -> false
    ThemeMode.DARK -> true
    ThemeMode.SYSTEM -> (system as? SystemThemeObservation.Known)?.dark ?: lastDisplayed ?: appConfigurationDark
}

private val AnalystTypography = Typography(
    displayLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Bold,
        fontSize = 38.sp,
        lineHeight = 44.sp,
        letterSpacing = (-1.2).sp,
    ),
    headlineLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Bold,
        fontSize = 28.sp,
        lineHeight = 34.sp,
        letterSpacing = (-0.4).sp,
    ),
    headlineMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Bold,
        fontSize = 24.sp,
        lineHeight = 30.sp,
    ),
    titleLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.SemiBold,
        fontSize = 20.sp,
        lineHeight = 27.sp,
    ),
    titleMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.SemiBold,
        fontSize = 16.sp,
        lineHeight = 23.sp,
    ),
    bodyLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Normal,
        fontSize = 16.sp,
        lineHeight = 25.sp,
    ),
    bodyMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Normal,
        fontSize = 14.sp,
        lineHeight = 20.sp,
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
        fontSize = 14.sp,
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
    val workspace = LocalWorkspacePreferences.current
    var mode by remember(context) { mutableStateOf(if (inspection) ThemeMode.SYSTEM else storedApplicationTheme(context)) }
    val system = if (inspection) SystemThemeObservation.Known(androidx.compose.foundation.isSystemInDarkTheme()) else rememberSystemThemeObservation()
    val dark = displayedThemeDark(mode, system, null, androidx.compose.foundation.isSystemInDarkTheme())
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
    // Persist the selected light/graphite mode across Activity and process restarts.
    val themePreference = ThemePreference(mode) { selected ->
        mode = selected
        preferences?.edit()?.putString("theme_mode", selected.name)?.apply()
        if (!inspection) syncSavedApplicationTheme(context, selected)
    }
    val motionPreference = SpectrumMotionPreference(workspace.value.motion != MotionLevel.OFF) { enabled ->
        workspace.update(workspace.value.copy(motion = if (enabled) MotionLevel.LIVE else MotionLevel.OFF))
        preferences?.edit()?.putBoolean("spectrum_motion", enabled)?.apply()
    }
    val palette = remember(dark) { spectrumPalette(dark = dark) }
    val colors = palette.colors
    CompositionLocalProvider(
        LocalEditorRestorationOwner provides editorRestorationOwner,
        LocalSystemThemeObservation provides system,
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
            CompositionLocalProvider(
                LocalContentColor provides MaterialTheme.colorScheme.onBackground,
                LocalTextSelectionColors provides TextSelectionColors(
                    handleColor = colors.primary, backgroundColor = colors.primaryContainer),
            ) {
                SpatialSceneRoot(modifier = androidx.compose.ui.Modifier.fillMaxSize(),
                    motion = when (workspace.value.motion) { MotionLevel.LIVE -> SpatialMotion.Live; MotionLevel.SUBDUED -> SpatialMotion.Subdued; MotionLevel.OFF -> SpatialMotion.Off },
                    tactile = workspace.value.haptics, opaque = workspace.value.brightLight,
                    navigationProgress = LocalWorkspaceBackProgress.current) { content() }
            }
        }
    }
}


