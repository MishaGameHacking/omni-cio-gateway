package ru.omnicio.app.ui.workspace

import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.withContext

enum class AccentStyle(val title: String) { AURORA("Аврора"), OCEAN("Океан"), IRIS("Ирис") }
enum class InterfaceDensity(val title: String) { COMFORT("Свободно"), COMPACT("Компактно") }
enum class MotionLevel(val title: String) { LIVE("Живое"), SUBDUED("Сдержанное"), OFF("Без движения") }

/** Device presentation only. These values never claim to change investment rules. */
data class WorkspacePreferences(
    val accent: AccentStyle = AccentStyle.AURORA,
    val density: InterfaceDensity = InterfaceDensity.COMFORT,
    val depth: Boolean = true,
    val hideHomeBalance: Boolean = false,
    val homeStructure: Boolean = true,
    val haptics: Boolean = true,
    val motion: MotionLevel = MotionLevel.LIVE,
    val brightLight: Boolean = false,
)

data class WorkspacePreferenceController(
    val value: WorkspacePreferences = WorkspacePreferences(),
    val preview: (WorkspacePreferences) -> Unit = {},
    val cancelPreview: () -> Unit = {},
    val applyPreview: () -> Unit = {},
    val update: (WorkspacePreferences) -> Unit = {},
    val saveStatus: String = "Сохранено на устройстве",
    val saveFailed: Boolean = false,
    val retrySave: () -> Unit = {},
)

val LocalWorkspacePreferences = staticCompositionLocalOf { WorkspacePreferenceController() }

@Composable
fun WorkspacePreferencesProvider(content: @Composable () -> Unit) {
    val context = LocalContext.current
    val store = remember(context) { context.applicationContext.getSharedPreferences("workspace_appearance", 0) }
    var value by remember {
        mutableStateOf(WorkspacePreferences(
            accent = AccentStyle.entries.firstOrNull { it.name == store.getString("accent", null) } ?: AccentStyle.AURORA,
            density = InterfaceDensity.entries.firstOrNull { it.name == store.getString("density", null) } ?: InterfaceDensity.COMFORT,
            depth = store.getBoolean("depth", true),
            hideHomeBalance = store.getBoolean("hide_home_balance", false),
            homeStructure = store.getBoolean("home_structure", true),
            haptics = store.getBoolean("haptics", true),
            motion = MotionLevel.entries.firstOrNull { it.name == store.getString("motion", null) }
                ?: if (context.getSharedPreferences("analyst_ai_settings", 0).getBoolean("spectrum_motion", true)) MotionLevel.LIVE else MotionLevel.OFF,
            brightLight = store.getBoolean("bright_light", false),
        ))
    }
    var preview by remember { mutableStateOf<WorkspacePreferences?>(null) }
    var revision by remember { mutableLongStateOf(0L) }
    var status by remember { mutableStateOf("Сохранено на устройстве") }
    var failed by remember { mutableStateOf(false) }
    val changes = remember { Channel<Pair<Long, WorkspacePreferences>>(Channel.CONFLATED) }
    val save: (WorkspacePreferences) -> Unit = { next ->
        value = next; preview = null; revision++
        status = "Сохраняем…"; failed = false
        changes.trySend(revision to next)
    }
    LaunchedEffect(store) {
        for ((request, next) in changes) {
            val persisted = withContext(Dispatchers.IO) { runCatching {
                store.edit().putString("accent", next.accent.name).putString("density", next.density.name)
                    .putBoolean("depth", next.depth).putBoolean("hide_home_balance", next.hideHomeBalance)
                    .putBoolean("home_structure", next.homeStructure).putBoolean("haptics", next.haptics)
                    .putString("motion", next.motion.name).putBoolean("bright_light", next.brightLight).commit()
            }.getOrDefault(false) }
            if (request == revision) {
                failed = !persisted
                status = if (persisted) "Сохранено на устройстве" else "Не удалось сохранить на устройстве"
            }
        }
    }
    val controller = WorkspacePreferenceController(preview ?: value,
        preview = { preview = it }, cancelPreview = { preview = null },
        applyPreview = { preview?.let(save) }, update = save, saveStatus = status, saveFailed = failed, retrySave = { save(value) })
    CompositionLocalProvider(LocalWorkspacePreferences provides controller, content = content)
}
