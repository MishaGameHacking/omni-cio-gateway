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
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
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
    val contentState = rememberSaveableStateHolder()
    val scope = rememberCoroutineScope()
    var release by remember { mutableStateOf<ReleaseDescriptor?>(null) }
    var current by remember { mutableStateOf(false) }
    var feedback by remember { mutableStateOf(UpdateGateFeedback()) }
    var checking by remember { mutableStateOf(true) }
    var busy by remember { mutableStateOf(false) }
    var retry by remember { mutableIntStateOf(0) }
    var awaitingPermission by remember { mutableStateOf<ReleaseDescriptor?>(null) }
    val progressFlow = remember { MutableStateFlow(0) }
    val progress by progressFlow.collectAsState()
    val serverBlocked by ClientVersion.blocked.collectAsState()
    val approval by UpdateInstaller.approval.collectAsState()
    val installationStatus by UpdateInstaller.statusText.collectAsState()
    val installationPending by UpdateInstaller.pending.collectAsState()

    LaunchedEffect(active) {
        if (active) withContext(Dispatchers.IO) { UpdateInstaller.refreshPending(context) }
    }

    LaunchedEffect(active, retry, serverBlocked) {
        if (!active) return@LaunchedEffect
        while (isActive) {
            checking = true
            try {
                val verification = ClientVersion.beginVerification()
                val latest = client.current()
                release = latest
                val matches = latest.decision(BuildConfig.APPLICATION_ID, BuildConfig.VERSION_CODE.toLong(), Build.VERSION.SDK_INT) == ReleaseDecision.CURRENT
                if (matches) {
                    val token = withContext(Dispatchers.IO) { AuthSessionStore(context).loadAccessToken() }
                    if (token != null) client.acknowledge(token)
                    check(ClientVersion.verifiedCurrent(verification)) { "Сервер сообщил о новой версии во время проверки." }
                }
                current = matches
                feedback = feedback.policyChecked()
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (_: Exception) {
                current = false
                feedback = feedback.policyChecked("Не удалось проверить актуальность версии. Проверьте интернет и повторите попытку.")
            } finally { checking = false }
            delay(60_000)
        }
    }

    fun startUpdate(chosen: ReleaseDescriptor) {
        if (busy || installationPending) return
        busy = true
        progressFlow.value = 0
        feedback = feedback.operationStarted()
        UpdateInstaller.statusText.value = null
        scope.launch {
            try {
                val apk = client.download(context, chosen) { progressFlow.value = it }
                check(client.current() == chosen) { "Вышла более новая сборка. Повторите проверку." }
                UpdateInstaller.install(context, apk, chosen)
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (failure: Exception) { feedback = feedback.operationFailed(failure.message ?: "Не удалось установить обновление. Повторите попытку.") }
            finally { busy = false }
        }
    }

    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        val chosen = awaitingPermission
        awaitingPermission = null
        if (chosen != null && context.packageManager.canRequestPackageInstalls()) startUpdate(chosen)
        else feedback = feedback.operationFailed("Для обновления разрешите установку из Analyst AI. Доступ к старой версии пока приостановлен.")
    }
    InstallConfirmation(
        approval = approval, active = active,
        onResult = { retry++ },
        onFailure = { feedback = feedback.operationFailed(it) },
    )

    if (current && !serverBlocked && !installationPending) {
        contentState.SaveableStateProvider("verified-client-content") { content() }
        return
    }
    val close: () -> Unit = { activity?.moveTaskToBack(true) }
    BackHandler(onBack = close)
    val chosen = release
    val decision = chosen?.decision(BuildConfig.APPLICATION_ID, BuildConfig.VERSION_CODE.toLong(), Build.VERSION.SDK_INT)
    val actions = UpdateGateActions(
        update = {
            if (chosen != null && decision == ReleaseDecision.UPDATE_REQUIRED && !busy && !checking && !installationPending) {
                if (context.packageManager.canRequestPackageInstalls()) startUpdate(chosen)
                else {
                    awaitingPermission = chosen
                    try { permissionLauncher.launch(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${context.packageName}"))) }
                    catch (_: Exception) { awaitingPermission = null; feedback = feedback.operationFailed("Android не открыл разрешение установки. Проверьте настройки Analyst AI.") }
                }
            }
        },
        retry = { if (!busy && !checking && !installationPending) retry++ },
        close = close,
    )
    AnalystTheme {
        blockedContent(
            UpdateGateUi(
                chosen, decision, BuildConfig.VERSION_NAME, checking, busy, progress,
                feedback.message, installationStatus, installationPending,
            ),
            actions,
        )
    }
}

/** OS consent is separate from policy and never declares the installed version current. */
@Composable
private fun InstallConfirmation(approval: Intent?, active: Boolean, onResult: () -> Unit, onFailure: (String) -> Unit) {
    val finished by rememberUpdatedState(onResult)
    val failed by rememberUpdatedState(onFailure)
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { finished() }
    LaunchedEffect(approval, active) {
        if (approval == null || !active) return@LaunchedEffect
        UpdateInstaller.approval.value = null
        try { launcher.launch(approval) }
        catch (cancelled: CancellationException) { throw cancelled }
        catch (_: Exception) { failed("Откройте уведомление Android для подтверждения установки или повторите попытку.") }
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
            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error,
                modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }) }
            state.installationStatus?.let { Text(it) }
            if (state.decision == ReleaseDecision.UPDATE_REQUIRED) {
                Button(enabled = state.canUpdate, onClick = actions.update, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Обновить приложение") }
            }
            TextButton(enabled = state.canRetry, onClick = actions.retry, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Повторить проверку") }
            TextButton(onClick = actions.close, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Закрыть") }
        }
    }
}
