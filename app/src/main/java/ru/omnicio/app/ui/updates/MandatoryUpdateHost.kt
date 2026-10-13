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

/** Content is not composed when blocked: no portfolio polling or AI screen tasks. */
@Composable
fun MandatoryUpdateHost(content: @Composable () -> Unit) {
    val context = LocalContext.current
    val activity = LocalActivity.current as? ComponentActivity
    val lifecycle = activity?.lifecycle
    var active by remember(lifecycle) { mutableStateOf(lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) ?: false) }
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, _ -> active = lifecycle?.currentState?.isAtLeast(Lifecycle.State.STARTED) ?: false }
        lifecycle?.addObserver(observer)
        onDispose { lifecycle?.removeObserver(observer) }
    }
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
    } else {
        BackHandler { activity?.moveTaskToBack(true) }
        AnalystTheme {
            Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                Column(Modifier.fillMaxSize().safeDrawingPadding().verticalScroll(rememberScrollState()).padding(24.dp),
                    verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("Analyst AI", style = MaterialTheme.typography.headlineLarge)
                    Spacer(Modifier.height(20.dp))
                    val chosen = release
                    val decision = chosen?.decision(BuildConfig.APPLICATION_ID, BuildConfig.VERSION_CODE.toLong(), Build.VERSION.SDK_INT)
                    Text(if (decision == ReleaseDecision.UPDATE_REQUIRED) "Требуется обновление" else "Проверка версии",
                        style = MaterialTheme.typography.headlineSmall)
                    Spacer(Modifier.height(12.dp))
                    Text("Установлено: ${BuildConfig.VERSION_NAME}")
                    if (chosen != null) Text("На сервере: ${chosen.versionName}")
                    Spacer(Modifier.height(12.dp))
                    Text(when (decision) {
                        ReleaseDecision.UNSUPPORTED_ANDROID -> "Для этой версии нужен более новый Android. Старую версию нельзя использовать."
                        ReleaseDecision.SERVER_NOT_READY -> "Сервер ещё не подтвердил эту сборку. Устанавливать более старый APK не нужно."
                        ReleaseDecision.WRONG_CHANNEL -> "Сервер вернул другую линию приложения. Установка остановлена."
                        else -> "Для работы нужна актуальная версия. Ваши данные сохранены. APK скачивается с сервера Analyst AI; Android может попросить разрешение и подтверждение установки."
                    })
                    if (!chosen?.notes.isNullOrBlank()) { Spacer(Modifier.height(12.dp)); Text(chosen!!.notes) }
                    if (checking && !busy) { Spacer(Modifier.height(16.dp)); CircularProgressIndicator() }
                    if (busy) { Spacer(Modifier.height(16.dp)); Text("Скачивание и проверка: $progress%"); LinearProgressIndicator(progress = { progress / 100f }, modifier = Modifier.fillMaxWidth()) }
                    error?.let { Spacer(Modifier.height(12.dp)); Text(it, color = MaterialTheme.colorScheme.error) }
                    installationStatus?.let { Spacer(Modifier.height(12.dp)); Text(it) }
                    Spacer(Modifier.height(20.dp))
                    if (chosen != null && decision == ReleaseDecision.UPDATE_REQUIRED) {
                        Button(enabled = !busy && !checking, onClick = {
                            if (context.packageManager.canRequestPackageInstalls()) startUpdate(chosen)
                            else {
                                awaitingPermission = chosen
                                try { permissionLauncher.launch(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${context.packageName}"))) }
                                catch (_: Exception) { awaitingPermission = null; error = "Android не открыл разрешение установки. Проверьте настройки Analyst AI." }
                            }
                        }, modifier = Modifier.fillMaxWidth()) { Text("Обновить приложение") }
                    }
                    TextButton(enabled = !busy && !checking, onClick = { retry++ }) { Text("Повторить проверку") }
                    TextButton(onClick = { activity?.moveTaskToBack(true) }) { Text("Закрыть") }
                }
            }
        }
    }
}
