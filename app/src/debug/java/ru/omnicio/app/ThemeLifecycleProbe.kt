package ru.omnicio.app

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.app.UiModeManager
import android.content.Context
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.os.Process
import android.provider.Settings
import android.view.WindowInsetsController
import androidx.activity.compose.LocalActivity
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalResources
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import androidx.compose.ui.zIndex
import ru.omnicio.app.ui.spectrum.LocalEditorRestorationOwner
import ru.omnicio.app.ui.spectrum.SpectrumPrimaryButton
import ru.omnicio.app.ui.spectrum.SpectrumTextField
import ru.omnicio.app.ui.theme.LocalSystemThemeObservation
import ru.omnicio.app.ui.theme.LocalThemePreference
import ru.omnicio.app.ui.theme.SystemThemeObservation
import ru.omnicio.app.ui.theme.ThemeMode
import ru.omnicio.app.ui.theme.syncSavedApplicationTheme
import ru.omnicio.app.ui.workspace.AppearanceScreen
import ru.omnicio.app.ui.workspace.LocalWorkspacePreferences
import ru.omnicio.app.ui.workspace.WorkspaceDetailPage
import java.security.MessageDigest
import java.util.UUID

/** Finite debug-only entry points. No account, arbitrary preference or color input. */
internal data class ThemeLifecycleRequest(val session: String, val phase: String, val run: String) {
    companion object {
        fun parse(session: String?, phase: String?, run: String): ThemeLifecycleRequest {
            require(session?.matches(Regex("[a-f0-9]{32}")) == true)
            require(phase in setOf("begin", "continue", "restore"))
            require(run.matches(Regex("[a-f0-9]{32}")))
            return ThemeLifecycleRequest(requireNotNull(session), requireNotNull(phase), run)
        }
    }
}

private data class LifecycleKey(val store: String, val name: String, val allowed: Set<String>, val boolean: Boolean = false) {
    val id: String get() = "$store/$name"
}

private val lifecycleKeys = listOf(
    LifecycleKey("analyst_ai_settings", "theme_mode", setOf("DARK", "LIGHT", "SYSTEM")),
    LifecycleKey("workspace_appearance", "accent", setOf("AURORA", "OCEAN", "IRIS")),
    LifecycleKey("workspace_appearance", "density", setOf("COMFORT", "COMPACT")),
    LifecycleKey("workspace_appearance", "depth", setOf("true", "false"), true),
    LifecycleKey("workspace_appearance", "hide_home_balance", setOf("true", "false"), true),
    LifecycleKey("workspace_appearance", "home_structure", setOf("true", "false"), true),
    LifecycleKey("workspace_appearance", "haptics", setOf("true", "false"), true),
    LifecycleKey("workspace_appearance", "motion", setOf("LIVE", "SUBDUED", "OFF")),
    LifecycleKey("workspace_appearance", "bright_light", setOf("true", "false"), true),
)

private fun lifecycleDigest(value: String): String = MessageDigest.getInstance("SHA-256")
    .digest(value.toByteArray(Charsets.UTF_8)).joinToString("") { (it.toInt() and 255).toString(16).padStart(2, '0') }

/** Preserve only the nine keys the real Appearance Apply path can change. */
internal class ThemeLifecycleSnapshot private constructor(val raw: String) {
    private val values: Map<String, String> = raw.split('\n').map { it.split('=', limit = 2) }
        .also { rows ->
            require(rows.size == lifecycleKeys.size)
            rows.zip(lifecycleKeys).forEach { (row, spec) ->
                require(row.size == 2 && row[0] == spec.id && (row[1] == "-" || row[1] in spec.allowed))
            }
        }.associate { it[0] to it[1] }
    val digest: String get() = lifecycleDigest(raw)
    val mode: ThemeMode get() = values.getValue("analyst_ai_settings/theme_mode")
        .let { if (it == "-") ThemeMode.DARK else ThemeMode.valueOf(it) }

    @SuppressLint("ApplySharedPref") // Finite debug cleanup needs an acknowledged disk write before cold start.
    fun restore(context: Context) {
        lifecycleKeys.groupBy { it.store }.forEach { (store, specs) ->
            val edit = context.getSharedPreferences(store, 0).edit()
            specs.forEach { spec ->
                val value = values.getValue(spec.id)
                when {
                    value == "-" -> edit.remove(spec.name)
                    spec.boolean -> edit.putBoolean(spec.name, value == "true")
                    else -> edit.putString(spec.name, value)
                }
            }
            check(edit.commit())
        }
        check(syncSavedApplicationTheme(context, mode))
        check(read(context).raw == raw)
    }

    companion object {
        fun parse(raw: String): ThemeLifecycleSnapshot {
            require(raw.length in 1..2048)
            return ThemeLifecycleSnapshot(raw)
        }
        fun read(context: Context): ThemeLifecycleSnapshot = parse(lifecycleKeys.joinToString("\n") { spec ->
            val all = context.getSharedPreferences(spec.store, 0).all
            val value = if (spec.name !in all) "-" else {
                val actual = all[spec.name]
                require(if (spec.boolean) actual is Boolean else actual is String)
                actual.toString().also { require(it in spec.allowed) }
            }
            "${spec.id}=$value"
        })
    }
}

private fun nativeNight(uiMode: Int): String = when (uiMode and Configuration.UI_MODE_NIGHT_MASK) {
    Configuration.UI_MODE_NIGHT_YES -> "yes"
    Configuration.UI_MODE_NIGHT_NO -> "no"
    else -> "undefined"
}
private fun colorHex(color: Int): String = color.toUInt().toString(16).padStart(8, '0')
private fun nativeThemeColor(context: Context, attribute: Int): String {
    val value = context.obtainStyledAttributes(intArrayOf(attribute))
    return try { if (value.hasValue(0)) colorHex(value.getColor(0, 0)) else "missing" } finally { value.recycle() }
}

/** Construct once in the real Activity.onCreate, before its AnalystTheme root. */
internal class ThemeLifecycleSession private constructor(
    val request: ThemeLifecycleRequest,
    val original: ThemeLifecycleSnapshot,
    val activityIdentity: String,
    val launchNight: String,
    val launchWindow: String,
    val launchSplash: String,
) {
    @SuppressLint("ApplySharedPref")
    fun complete(context: Context) {
        check(request.phase == "restore")
        check(ThemeLifecycleSnapshot.read(context).raw == original.raw)
        val store = context.getSharedPreferences("theme_lifecycle_probe_snapshot", 0)
        check(store.getString("session", null) == request.session)
        check(store.getString("snapshot", null) == original.raw)
        check(store.edit().clear().commit())
    }

    companion object {
        @SuppressLint("ApplySharedPref")
        fun open(activity: Activity, request: ThemeLifecycleRequest): ThemeLifecycleSession {
            require(BuildConfig.DEBUG && activity.packageName == "ru.omnicio.app.debug")
            val store = activity.getSharedPreferences("theme_lifecycle_probe_snapshot", 0)
            val original = if (request.phase == "begin") {
                check(store.all.isEmpty()) // Never replace a different run's incomplete restoration.
                ThemeLifecycleSnapshot.read(activity).also { snapshot ->
                    check(store.edit().putString("session", request.session).putString("snapshot", snapshot.raw).commit())
                }
            } else {
                check(store.all.keys == setOf("session", "snapshot"))
                check(store.getString("session", null) == request.session)
                ThemeLifecycleSnapshot.parse(requireNotNull(store.getString("snapshot", null)))
            }
            if (request.phase == "restore") original.restore(activity)
            return ThemeLifecycleSession(request, original, UUID.randomUUID().toString(),
                nativeNight(activity.resources.configuration.uiMode),
                nativeThemeColor(activity, android.R.attr.windowBackground),
                nativeThemeColor(activity, android.R.attr.windowSplashScreenBackground))
        }
    }
}

@Composable
internal fun ThemeLifecycleProbe(session: ThemeLifecycleSession) {
    val context = LocalContext.current
    val activity = requireNotNull(LocalActivity.current)
    val configuration = LocalConfiguration.current
    val theme = LocalThemePreference.current
    val system = LocalSystemThemeObservation.current // Observe the existing root; never create a second source.
    val workspace = LocalWorkspacePreferences.current.value
    val editorOwner = LocalEditorRestorationOwner.current
    val rememberedOwner = remember { UUID.randomUUID().toString() }
    // Deliberately not saveable: a uiMode recreation must fail the continuity gate.
    var draftText by remember { mutableStateOf("THEME") }
    var appearanceOpen by remember { mutableStateOf(false) }
    var preferenceRevision by remember { mutableIntStateOf(0) }
    DisposableEffect(context) {
        val listener = SharedPreferences.OnSharedPreferenceChangeListener { _, _ -> preferenceRevision++ }
        val stores = lifecycleKeys.map { it.store }.distinct().map { context.getSharedPreferences(it, 0) }
        stores.forEach { it.registerOnSharedPreferenceChangeListener(listener) }
        onDispose { stores.forEach { it.unregisterOnSharedPreferenceChangeListener(listener) } }
    }
    val saved = remember(context, preferenceRevision, theme.mode, workspace) { ThemeLifecycleSnapshot.read(context) }
    var barAppearance by remember { mutableIntStateOf(-1) }
    LaunchedEffect(theme.mode, system, configuration.uiMode, appearanceOpen, workspace) {
        // Read the actual controller after the production root's SideEffect has applied its bars.
        withFrameNanos { }
        barAppearance = activity.window.insetsController?.systemBarsAppearance ?: -1
    }
    val statusLight = if (barAppearance < 0) "unknown" else
        ((barAppearance and WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS) != 0).toString()
    val navigationLight = if (barAppearance < 0) "unknown" else
        ((barAppearance and WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS) != 0).toString()
    val observedSystem = when (system) {
        is SystemThemeObservation.Known -> if (system.dark) "yes" else "no"
        is SystemThemeObservation.Unknown -> "unknown-${system.reason.name}"
    }
    val policy = when (context.getSystemService(UiModeManager::class.java)?.nightMode) {
        UiModeManager.MODE_NIGHT_NO -> "no"
        UiModeManager.MODE_NIGHT_YES -> "yes"
        UiModeManager.MODE_NIGHT_AUTO -> "auto"
        UiModeManager.MODE_NIGHT_CUSTOM -> "custom"
        else -> "unknown"
    }
    val storedMode = context.getSharedPreferences("analyst_ai_settings", 0).getString("theme_mode", "absent")
    val storedAccent = context.getSharedPreferences("workspace_appearance", 0).getString("accent", "absent")
    val marker = "theme-lifecycle:production-v1;session:${session.request.session};run:${session.request.run};" +
        "phase:${session.request.phase};activity:${session.activityIdentity};owner:$rememberedOwner;editor-owner:$editorOwner;" +
        "pid:${Process.myPid()};uid:${Process.myUid()};page:${if (appearanceOpen) "appearance" else "home"};draft:$draftText;" +
        "mode:${theme.mode.name};saved-mode:${saved.mode.name};stored-mode:$storedMode;saved-hash:${saved.digest};" +
        "original-mode:${session.original.mode.name};original-hash:${session.original.digest};" +
        "app-night:${nativeNight(configuration.uiMode)};system-night:$observedSystem;policy:$policy;" +
        "background:${colorHex(MaterialTheme.colorScheme.background.toArgb())};foreground:${colorHex(MaterialTheme.colorScheme.onBackground.toArgb())};" +
        "native-background:${colorHex(LocalResources.current.getColor(R.color.analyst_background, null))};" +
        "native-window:${nativeThemeColor(context, android.R.attr.windowBackground)};native-splash:${nativeThemeColor(context, android.R.attr.windowSplashScreenBackground)};" +
        "launch-night:${session.launchNight};launch-window:${session.launchWindow};launch-splash:${session.launchSplash};" +
        "status-light:$statusLight;navigation-light:$navigationLight;" +
        "overlay-permission:${context.checkSelfPermission(Manifest.permission.SYSTEM_ALERT_WINDOW) == PackageManager.PERMISSION_GRANTED};" +
        "overlay-capability:${Settings.canDrawOverlays(context)};accent:${workspace.accent.name};saved-accent:$storedAccent;" +
        "font-scale:${LocalDensity.current.fontScale};density:${LocalDensity.current.density};" +
        "restored:${session.request.phase == "restore" && saved.raw == session.original.raw}"
    Box(Modifier.fillMaxSize().semantics { testTagsAsResourceId = true }) {
        if (appearanceOpen) {
            AppearanceScreen { appearanceOpen = false }
        } else {
            WorkspaceDetailPage("Проверка темы", "Только синтетический локальный черновик", onBack = { activity.finish() }, adaptToIme = true) { padding ->
                LazyColumn(Modifier.fillMaxSize().testTag("workspace-content").padding(padding).consumeWindowInsets(padding),
                    contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    item {
                        SpectrumTextField(draftText, { draftText = it },
                            Modifier.fillMaxWidth().testTag("theme-lifecycle-draft"),
                            label = { Text("Черновик темы") }, singleLine = true)
                    }
                    item {
                        SpectrumPrimaryButton("Открыть оформление", { appearanceOpen = true }, Modifier.fillMaxWidth())
                    }
                    if (session.request.phase == "restore") item {
                        SpectrumPrimaryButton("Закрыть проверку", { session.complete(context); activity.finish() }, Modifier.fillMaxWidth())
                    }
                }
            }
        }
        Box(Modifier.align(Alignment.TopStart).size(2.dp).zIndex(101f)
            .testTag("theme-lifecycle-state").clearAndSetSemantics { contentDescription = marker })
    }
}
