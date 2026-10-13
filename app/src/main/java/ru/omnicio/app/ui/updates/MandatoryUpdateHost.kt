package ru.omnicio.app.ui.updates

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.LocalActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import ru.omnicio.app.BuildConfig
import ru.omnicio.app.data.backend.AuthSessionStore
import ru.omnicio.app.data.updates.*
import ru.omnicio.app.ui.theme.AnalystTheme

/** A single gate owns both plain and Spectrum rendering. Blocked content is not composed. */
@Composable
fun MandatoryUpdateHost(
    blockedContent: @Composable (UpdateGateUi, UpdateGateActions) -> Unit = { state, actions -> DefaultUpdateScreen(state, actions) },
    content: @Composable () -> Unit,
) {
    val context = LocalContext.current
    val activity = LocalActivity.current as? ComponentActivity
    val active = rememberForeground(activity?.lifecycle)
    val client = remember { UpdateClient() }
    val scope = rememberCoroutineScope()
    var release by remember { mutableStateOf<ReleaseDescriptor?>(null) }
    var current by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var checking by remember { mutableStateOf(true) }
    var busy by remember { mutableStateOf(false) }
    var retry by remember { mutableIntStateOf(0) }
    var awaitingPermission by remember { mutableStateOf<ReleaseDescriptor?>(null) }
    val progressFlow = remember { MutableStateFlow(0) }
    val progress by progressFlow.collectAsState()
    val serverBlocked by ClientVersion.blocked.collectAsState()
    val approval by UpdateInstaller.approval.collectAsState()
    val installationStatus by UpdateInstaller.statusText.collectAsState()

    LaunchedEffect(active, retry, serverBlocked) {
        if (!active) return@LaunchedEffect
        while (isActive) {
            checking = true
            try {
                val latest = client.current()
                release = latest
                val matches = latest.decision(BuildConfig.APPLICATION_ID, BuildConfig.VERSION_CODE.toLong(), Build.VERSION.SDK_INT) == ReleaseDecision.CURRENT
                if (matches) {
                    val token = withContext(Dispatchers.IO) { AuthSessionStore(context).loadAccessToken() }
                    if (token != null) client.acknowledge(token)
                    ClientVersion.verifiedCurrent()
                }
                current = matches
                error = null
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (_: Exception) {
                current = false
                error = "Не удалось проверить актуальность версии. Проверьте интернет и повторите попытку."
            } finally { checking = false }
            delay(60_000)
        }
    }

    fun startUpdate(chosen: ReleaseDescriptor) {
        if (busy) return
        busy = true
        progressFlow.value = 0
        error = null
        UpdateInstaller.statusText.value = null
        scope.launch {
            try {
                val apk = client.download(context, chosen) { progressFlow.value = it }
                check(client.current() == chosen) { "Вышла более новая сборка. Повторите проверку." }
                UpdateInstaller.install(context, apk, chosen)
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (failure: Exception) { error = failure.message ?: "Не удалось установить обновление. Повторите попытку." }
            finally { busy = false }
        }
    }

    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        val chosen = awaitingPermission
        awaitingPermission = null
        if (chosen != null && context.packageManager.canRequestPackageInstalls()) startUpdate(chosen)
        else error = "Для обновления разрешите установку из Analyst AI. Доступ к старой версии пока приостановлен."
    }
    val confirmationLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { retry++ }
    LaunchedEffect(approval, active) {
        val confirmation = approval
        if (confirmation != null && active) {
            UpdateInstaller.approval.value = null
            try { confirmationLauncher.launch(confirmation) }
            catch (_: Exception) { error = "Откройте уведомление Android для подтверждения установки или повторите попытку." }
        }
    }

    if (current && !serverBlocked) {
        content()
        return
    }
    val close: () -> Unit = { activity?.moveTaskToBack(true); Unit }
    BackHandler(onBack = close)
    val chosen = release
    val decision = chosen?.decision(BuildConfig.APPLICATION_ID, BuildConfig.VERSION_CODE.toLong(), Build.VERSION.SDK_INT)
    val actions = UpdateGateActions(
        update = {
            if (chosen != null && decision == ReleaseDecision.UPDATE_REQUIRED && !busy && !checking) {
                if (context.packageManager.canRequestPackageInstalls()) startUpdate(chosen)
                else {
                    awaitingPermission = chosen
                    try { permissionLauncher.launch(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${context.packageName}"))) }
                    catch (_: Exception) { awaitingPermission = null; error = "Android не открыл разрешение установки. Проверьте настройки Analyst AI." }
                }
            }
        },
        retry = { if (!busy && !checking) retry++ },
        close = close,
    )
    AnalystTheme {
        blockedContent(UpdateGateUi(chosen, decision, BuildConfig.VERSION_NAME, checking, busy, progress, error, installationStatus), actions)
    }
}

@Composable
private fun rememberForeground(lifecycle: Lifecycle?): Boolean {
    var active by remember(lifecycle) { mutableStateOf(lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) ?: false) }
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, _ -> active = lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) ?: false }
        lifecycle?.addObserver(observer)
        onDispose { lifecycle?.removeObserver(observer) }
    }
    return active
}

@Composable
private fun DefaultUpdateScreen(state: UpdateGateUi, actions: UpdateGateActions) {
    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(Modifier.fillMaxSize().safeDrawingPadding().verticalScroll(rememberScrollState()).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.CenterVertically),
            horizontalAlignment = Alignment.CenterHorizontally) {
            Text("Analyst AI", style = MaterialTheme.typography.headlineLarge)
            Text(state.title, style = MaterialTheme.typography.headlineSmall)
            Text("Установлено: ${state.installedVersion}")
            state.release?.let { Text("На сервере: ${it.versionName}") }
            Text(state.explanation)
            state.release?.notes?.takeIf(String::isNotBlank)?.let { Text(it) }
            if (state.checking && !state.busy) CircularProgressIndicator()
            if (state.busy) {
                Text("Скачивание и проверка: ${state.progressPercent}%")
                LinearProgressIndicator(progress = { state.progressPercent / 100f }, modifier = Modifier.fillMaxWidth())
            }
            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            state.installationStatus?.let { Text(it) }
            if (state.decision == ReleaseDecision.UPDATE_REQUIRED) {
                Button(enabled = state.canUpdate, onClick = actions.update, modifier = Modifier.fillMaxWidth()) { Text("Обновить приложение") }
            }
            TextButton(enabled = state.canRetry, onClick = actions.retry) { Text("Повторить проверку") }
            TextButton(onClick = actions.close) { Text("Закрыть") }
        }
    }
}
