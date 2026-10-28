package ru.omnicio.app.ui.theme

import android.app.Activity
import android.app.UiModeManager
import android.content.ComponentCallbacks
import android.content.Context
import android.content.res.Configuration
import android.view.Display
import android.view.WindowManager
import androidx.activity.compose.LocalActivity
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext

enum class SystemThemeUnavailableReason {
    INITIALIZING, NO_DISPLAY, DISPLAY_UNAVAILABLE, CONTEXT_UNAVAILABLE, UNDEFINED_CONFIGURATION,
}

/** An app-forced configuration is never reported as a known system theme. */
sealed interface SystemThemeObservation {
    data class Known(val dark: Boolean) : SystemThemeObservation
    data class Unknown(val reason: SystemThemeUnavailableReason) : SystemThemeObservation
}

/** Share the root's single observation with UI and debug-only native evidence. */
val LocalSystemThemeObservation = staticCompositionLocalOf<SystemThemeObservation> {
    SystemThemeObservation.Unknown(SystemThemeUnavailableReason.INITIALIZING)
}

/** App-local override only. Saved LIGHT/SYSTEM values migrate to the single style. */
@Suppress("UNUSED_PARAMETER")
internal fun applicationNightMode(mode: ThemeMode): Int = UiModeManager.MODE_NIGHT_NO

internal fun storedApplicationTheme(context: Context): ThemeMode {
    val name = context.getSharedPreferences("analyst_ai_settings", Context.MODE_PRIVATE)
        .getString("theme_mode", ThemeMode.DARK.name)
    return ThemeMode.entries.firstOrNull { it.name == name } ?: ThemeMode.DARK
}

/** Only startup and the committed save path call this; previews are in memory. */
fun syncSavedApplicationTheme(context: Context, mode: ThemeMode): Boolean = try {
    val manager = platformThemeCall { context.applicationContext.getSystemService(UiModeManager::class.java) }
    if (manager == null) false else {
        platformThemeCall { manager.setApplicationNightMode(applicationNightMode(mode)) }
        true
    }
} catch (_: SystemThemePlatformFailure) {
    // The saved Compose preference remains usable on a temporarily unavailable
    // platform service. A native cold-start gate must still verify splash sync.
    false
}

internal fun systemThemeObservation(uiMode: Int): SystemThemeObservation = when (uiMode and Configuration.UI_MODE_NIGHT_MASK) {
    Configuration.UI_MODE_NIGHT_YES -> SystemThemeObservation.Known(dark = true)
    Configuration.UI_MODE_NIGHT_NO -> SystemThemeObservation.Known(dark = false)
    else -> SystemThemeObservation.Unknown(SystemThemeUnavailableReason.UNDEFINED_CONFIGURATION)
}

internal class SystemThemePlatformFailure(
    val reason: SystemThemeUnavailableReason,
    cause: RuntimeException? = null,
) : RuntimeException(cause)

private inline fun <T> platformThemeCall(block: () -> T): T = try {
    block()
} catch (error: WindowManager.InvalidDisplayException) {
    throw SystemThemePlatformFailure(SystemThemeUnavailableReason.DISPLAY_UNAVAILABLE, error)
} catch (error: SecurityException) {
    throw SystemThemePlatformFailure(SystemThemeUnavailableReason.CONTEXT_UNAVAILABLE, error)
} catch (error: UnsupportedOperationException) {
    throw SystemThemePlatformFailure(SystemThemeUnavailableReason.CONTEXT_UNAVAILABLE, error)
} catch (error: IllegalArgumentException) {
    throw SystemThemePlatformFailure(SystemThemeUnavailableReason.CONTEXT_UNAVAILABLE, error)
} catch (error: IllegalStateException) {
    throw SystemThemePlatformFailure(SystemThemeUnavailableReason.CONTEXT_UNAVAILABLE, error)
}

internal interface SystemThemeSource {
    fun current(): SystemThemeObservation
    fun register(listener: (SystemThemeObservation) -> Unit)
    fun unregister(listener: (SystemThemeObservation) -> Unit)
}

/** The same subscribe/read/dispose behavior is exercised by the JVM tests. */
internal class SystemThemeObservationSession(
    private val source: SystemThemeSource,
    private val publish: (SystemThemeObservation) -> Unit,
) : AutoCloseable {
    private var closed = false
    private var registered = false
    private val listener: (SystemThemeObservation) -> Unit = { if (!closed) publish(it) }

    init {
        var initialized = false
        try {
            // A registration can partially succeed before a platform failure.
            registered = true
            source.register(listener)
            listener(source.current())
            initialized = true
        } catch (error: SystemThemePlatformFailure) {
            listener(SystemThemeObservation.Unknown(error.reason))
        } finally {
            // Unexpected programming failures propagate, but still release a
            // registration that may already have succeeded.
            if (!initialized) close()
        }
    }

    override fun close() {
        if (closed) return
        closed = true // Disarm any already queued callback before unregistering.
        if (registered) {
            registered = false
            try {
                source.unregister(listener)
            } catch (_: SystemThemePlatformFailure) {
                // The display/context may already have been removed. The
                // callback is disarmed and the context is no longer retained.
            }
        }
    }
}

private class DisplayAreaThemeSource(private val context: Context) : SystemThemeSource {
    private var callback: ComponentCallbacks? = null

    override fun current(): SystemThemeObservation = platformThemeCall {
        systemThemeObservation(context.resources.configuration.uiMode)
    }

    override fun register(listener: (SystemThemeObservation) -> Unit) {
        check(callback == null)
        val next = object : ComponentCallbacks {
            override fun onConfigurationChanged(newConfig: Configuration) {
                listener(systemThemeObservation(newConfig.uiMode))
            }
            override fun onLowMemory() = Unit
        }
        callback = next
        platformThemeCall { context.registerComponentCallbacks(next) }
    }

    override fun unregister(listener: (SystemThemeObservation) -> Unit) {
        val previous = callback ?: return
        callback = null
        platformThemeCall { context.unregisterComponentCallbacks(previous) }
    }
}

private data class DisplayLookup(val display: Display?, val failure: SystemThemeUnavailableReason?)

private fun activityDisplay(activity: Activity?): DisplayLookup = try {
    val display = platformThemeCall { activity?.display }
    when {
        display == null -> DisplayLookup(null, SystemThemeUnavailableReason.NO_DISPLAY)
        !platformThemeCall { display.isValid } -> DisplayLookup(null, SystemThemeUnavailableReason.DISPLAY_UNAVAILABLE)
        else -> DisplayLookup(display, null)
    }
} catch (error: SystemThemePlatformFailure) {
    DisplayLookup(null, error.reason)
}

/** Observe the display area independently of the app's persisted night override. */
@Composable
fun rememberSystemThemeObservation(): SystemThemeObservation {
    val application = LocalContext.current.applicationContext
    val activity = LocalActivity.current
    val configuration = LocalConfiguration.current
    // Configuration changes also cover moving the activity to another display;
    // only a changed display identity replaces the expensive window context.
    val lookup = remember(activity, configuration) { activityDisplay(activity) }
    val displayId = lookup.display?.displayId
    var observation by remember(activity, displayId, lookup.failure) {
        mutableStateOf<SystemThemeObservation>(
            SystemThemeObservation.Unknown(SystemThemeUnavailableReason.INITIALIZING),
        )
    }
    DisposableEffect(application, activity, displayId, lookup.failure) {
        val display = lookup.display
        val session = if (display == null) {
            observation = SystemThemeObservation.Unknown(lookup.failure ?: SystemThemeUnavailableReason.NO_DISPLAY)
            null
        } else {
            try {
                // Only create a configuration context. No window is added, no
                // activity token is attached, and no overlay permission is used.
                val context = platformThemeCall {
                    application.createWindowContext(display, WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY, null)
                }
                SystemThemeObservationSession(DisplayAreaThemeSource(context)) { observation = it }
            } catch (error: SystemThemePlatformFailure) {
                observation = SystemThemeObservation.Unknown(error.reason)
                null
            }
        }
        onDispose { session?.close() }
    }
    return observation
}

