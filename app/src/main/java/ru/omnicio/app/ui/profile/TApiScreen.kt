package ru.omnicio.app.ui.profile

import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.workspace.*
import ru.omnicio.app.ui.spectrum.SpectrumAlertDialog as AlertDialog
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.size
import ru.omnicio.app.ui.spatial.SpatialBackHandler as BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import ru.omnicio.app.data.backend.AnalystBackendClient
import ru.omnicio.app.data.backend.BackendResult
import ru.omnicio.app.ui.spatial.SpatialIcon
import ru.omnicio.app.ui.spatial.SpatialState
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.LiveRegionMode

private sealed interface TokenUiStatus {
    data object Missing : TokenUiStatus
    data object Connected : TokenUiStatus
    data object Checking : TokenUiStatus
    data object Saving : TokenUiStatus
    data object Removing : TokenUiStatus
    data class Error(val message: String) : TokenUiStatus
}

private fun TokenUiStatus.isBusy(): Boolean = this == TokenUiStatus.Checking || this == TokenUiStatus.Saving || this == TokenUiStatus.Removing

private val TApiCard: Color
    @Composable get() = MaterialTheme.colorScheme.surface
private val TApiMuted: Color
    @Composable get() = MaterialTheme.colorScheme.onSurfaceVariant
private val TApiBlue: Color
    @Composable get() = MaterialTheme.colorScheme.primary
private val TApiGreen: Color
    @Composable get() = LocalSpectrumPalette.current.emerald
private val TApiRed: Color
    @Composable get() = MaterialTheme.colorScheme.error

@Composable
fun TApiScreen(
    accessToken: String,
    tApiConfigured: Boolean,
    onBack: () -> Unit,
    onConnectionChanged: (Boolean) -> Unit,
    modifier: Modifier = Modifier,
    onOpenPortfolio: () -> Unit = onBack,
) {
    BackHandler(onBack = onBack)

    val connection = LocalBrokerConnection.current
    val uriHandler = LocalUriHandler.current
    val backend = remember { AnalystBackendClient() }
    val scope = rememberCoroutineScope()

    var tokenInput by remember(accessToken) { mutableStateOf("") }
    var showToken by remember(accessToken) { mutableStateOf(false) }
    val foreground = workspaceForeground()
    val reauthenticate = LocalReauthenticate.current
    LaunchedEffect(foreground) { if (!foreground) showToken = false }
    var docsError by remember { mutableStateOf<String?>(null) }
    var status by remember(tApiConfigured, connection) {
        mutableStateOf<TokenUiStatus>(
            when {
                connection == BrokerConnectionState.Checking -> TokenUiStatus.Checking
                connection == BrokerConnectionState.Unknown -> TokenUiStatus.Error("Статус не получен. Проверьте сеть или повторно подключите read-only токен.")
                connection == BrokerConnectionState.Missing -> TokenUiStatus.Missing
                connection == BrokerConnectionState.Connected || tApiConfigured -> TokenUiStatus.Connected
                else -> TokenUiStatus.Missing
            },
        )
    }

    val verify = {
        if (!status.isBusy() && tokenInput.isNotBlank()) {
            status = TokenUiStatus.Saving
            showToken = false
            scope.launch {
                when (val result = withContext(Dispatchers.IO) {
                    backend.saveTInvestToken(
                        accessToken = accessToken,
                        token = tokenInput,
                    )
                }) {
                    is BackendResult.Success -> {
                        tokenInput = ""
                        status = TokenUiStatus.Connected
                        onConnectionChanged(true)
                    }
                    is BackendResult.Failure -> {
                        status = TokenUiStatus.Error(result.message)
                        if (result.statusCode in listOf(401, 403)) reauthenticate()
                    }
                }
            }
        }
    }

    TApiContent(
        modifier = modifier,
        onOpenPortfolio = onOpenPortfolio,
        status = status,
        tokenInput = tokenInput,
        showToken = showToken,
        docsError = docsError,
        tApiConfigured = tApiConfigured || status == TokenUiStatus.Connected,
        onBack = onBack,
        onTokenInputChange = { value ->
            tokenInput = value
            if (!status.isBusy()) {
                status = if (tApiConfigured) {
                    TokenUiStatus.Connected
                } else {
                    TokenUiStatus.Missing
                }
            }
        },
        onToggleTokenVisibility = {
            showToken = !showToken
        },
        onVerify = verify,
        onRemove = {
            if (!status.isBusy()) {
                status = TokenUiStatus.Removing
                showToken = false
                scope.launch {
                    when (val result = withContext(Dispatchers.IO) {
                        backend.deleteTInvestToken(accessToken)
                    }) {
                        is BackendResult.Success -> {
                            tokenInput = ""
                            status = TokenUiStatus.Missing
                            onConnectionChanged(false)
                        }
                        is BackendResult.Failure -> {
                            status = TokenUiStatus.Error(result.message)
                            if (result.statusCode in listOf(401, 403)) reauthenticate()
                        }
                    }
                }
            }
        },
        onOpenDocs = {
            docsError = null
            runCatching { uriHandler.openUri(TOKEN_DOCS_URL) }
                .onFailure {
                    docsError = "Не удалось открыть официальную инструкцию. Проверьте браузер или подключение."
                }
        },
    )
}

@Composable
private fun TApiContent(
    onOpenPortfolio: () -> Unit,
    status: TokenUiStatus,
    tokenInput: String,
    showToken: Boolean,
    docsError: String?,
    tApiConfigured: Boolean,
    onBack: () -> Unit,
    onTokenInputChange: (String) -> Unit,
    onToggleTokenVisibility: () -> Unit,
    onVerify: () -> Unit,
    onRemove: () -> Unit,
    onOpenDocs: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var confirmDisconnect by remember { mutableStateOf(false) }
    SpectrumBackground(modifier.fillMaxSize()) {
    Scaffold(
        modifier = Modifier.fillMaxSize().imePadding(),
        containerColor = Color.Transparent,
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding).consumeWindowInsets(innerPadding),
            contentPadding = PaddingValues(
                start = 20.dp,
                top = 18.dp,
                end = 20.dp,
                bottom = 32.dp,
            ),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            item { TApiHeader(onBack = onBack) }
            item { ConnectionStages(status) }
            item { StatusCard(status = status) }
            if (tApiConfigured) item { SpectrumPrimaryButton("Открыть портфель", onOpenPortfolio, Modifier.fillMaxWidth()) }
            item {
                DetailFold(if (tApiConfigured) "Управление подключением" else "Токен доступа", initiallyOpen = !tApiConfigured) {
                TokenInputCard(
                    status = status,
                    tokenInput = tokenInput,
                    showToken = showToken,
                    tApiConfigured = tApiConfigured,
                    onTokenInputChange = onTokenInputChange,
                    onToggleTokenVisibility = onToggleTokenVisibility,
                    onVerify = onVerify,
                    onRemove = { confirmDisconnect = true },
                )
            }
            }
            if (!tApiConfigured) item { TokenDocsCard(onOpenDocs = onOpenDocs) }
            docsError?.let { message ->
                item { DocsErrorCard(message) }
            }
            item { DetailFold("О безопасности подключения") { TokenSecurityCard() } }
        }
    }
    }
    if (confirmDisconnect) AlertDialog(onDismissRequest = { confirmDisconnect = false }, title = { Text("Отключить счёт?") },
        text = { Text("Новые данные и наблюдение за портфелем перестанут поступать. Доступ к аккаунту приложения сохранится.") },
        confirmButton = { TextButton(onClick = { confirmDisconnect = false; onRemove() }) { Text("Отключить") } },
        dismissButton = { TextButton(onClick = { confirmDisconnect = false }) { Text("Оставить подключённым") } })
}

@Composable
private fun TApiHeader(onBack: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        SpectrumTextButton("Назад", onBack, symbol = SpectrumSymbol.Back)
        Column(Modifier.weight(1f)) {
            Text(
                text = "Подключение",
                fontSize = 26.sp,
                lineHeight = 32.sp,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = "Счёт Т-Инвестиций",
                color = TApiMuted,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

@Composable
private fun TokenInputCard(
    status: TokenUiStatus,
    tokenInput: String,
    showToken: Boolean,
    tApiConfigured: Boolean,
    onTokenInputChange: (String) -> Unit,
    onToggleTokenVisibility: () -> Unit,
    onVerify: () -> Unit,
    onRemove: () -> Unit,
) {
    val checking = status.isBusy()
    SpectrumCard(Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(22.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Text(
                text = if (tApiConfigured) "Заменить токен" else "Токен доступа",
                fontSize = 22.sp,
                lineHeight = 28.sp,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = "Вставьте токен только для чтения. Торговый доступ не нужен.",
                color = TApiMuted,
                style = MaterialTheme.typography.bodyMedium,
            )
            SpectrumTextField(
                modifier = Modifier.fillMaxWidth(),
                value = tokenInput,
                onValueChange = onTokenInputChange,
                enabled = !checking,
                singleLine = true,
                label = {
                    Text(if (tApiConfigured) "Новый токен" else "Вставьте токен")
                },
                visualTransformation = if (showToken) {
                    VisualTransformation.None
                } else {
                    PasswordVisualTransformation()
                },
                trailingIcon = {
                    TextButton(
                        onClick = onToggleTokenVisibility,
                        enabled = tokenInput.isNotEmpty(),
                    ) {
                        Text(if (showToken) "Скрыть" else "Показать")
                    }
                },
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done, keyboardType = KeyboardType.Password),
                keyboardActions = KeyboardActions(onDone = { onVerify() }),
            )
            SpectrumPrimaryButton(if (checking) "Ждём ответ сервера…" else if (tApiConfigured) "Проверить и заменить" else "Проверить и подключить",
                onVerify, Modifier.fillMaxWidth(), enabled = !checking && tokenInput.isNotBlank())
            if (tApiConfigured) {
                SpectrumSecondaryButton("Отключить T‑API", onRemove, Modifier.fillMaxWidth(), enabled = !checking)
            }
        }
    }
}

@Composable
private fun TokenDocsCard(onOpenDocs: () -> Unit) {
    SpectrumCard(Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(22.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = "Как получить токен",
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = "Выпустите read-only токен в настройках T‑Инвестиций. Токен показывается только один раз — скопируйте его и вставьте выше.",
                color = TApiMuted,
                style = MaterialTheme.typography.bodyMedium,
            )
            TextButton(onClick = onOpenDocs) {
                Text(
                    text = "Открыть официальную инструкцию T‑Invest",
                    color = TApiBlue,
                )
            }
        }
    }
}

@Composable
private fun DocsErrorCard(message: String) {
    SpectrumCard(Modifier.fillMaxWidth()) {
        Text(
            text = message,
            modifier = Modifier.padding(18.dp),
            color = MaterialTheme.colorScheme.error,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun TokenSecurityCard() {
    SpectrumCard(Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(22.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                text = "Безопасность",
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = "Токен передаётся по HTTPS на ваш Lenovo, проверяется запросом T‑Invest только для чтения и хранится на ноутбуке в зашифрованном виде, привязанном к вашему Telegram ID.",
                color = TApiMuted,
                style = MaterialTheme.typography.bodyMedium,
            )
            Text(
                text = "Скриншоты разрешены по умолчанию. При необходимости включите запрет в «Профиль → Настройки».",
                color = TApiMuted,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

@Composable
private fun ConnectionStages(status: TokenUiStatus) {
    val snapshot = LocalPortfolioSnapshot.current
    val connected = status == TokenUiStatus.Connected
    SpectrumCard {
        listOf(
            Triple("Вход в Analyst AI подтверждён", "Ваш сеанс Telegram", SpatialState.Success),
            Triple(if (connected) "Доступ к брокеру подтверждён" else if (status.isBusy()) "Проверяем доступ к брокеру" else "Подключите счёт",
                if (status == TokenUiStatus.Saving) "Проверка и сохранение завершаются одним ответом сервера" else "Доступ только к чтению данных",
                when { connected -> SpatialState.Success; status.isBusy() -> SpatialState.Loading; status is TokenUiStatus.Error -> SpatialState.Attention; else -> SpatialState.Idle }),
            Triple(if (connected && snapshot != null) "Снимок портфеля получен" else "Первая загрузка портфеля",
                if (connected && snapshot != null) "${snapshot.accounts.size} счетов · ${snapshot.asOf ?: "время источника не получено"}" else "Будет подтверждена после получения счетов и позиций",
                if (connected && snapshot != null) SpatialState.Success else SpatialState.Idle),
        ).forEachIndexed { index, (title, detail, state) ->
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                SpatialIcon(when { state == SpatialState.Success -> "check"; index == 0 -> "profile"; index == 1 -> "sources"; else -> "portfolio" }, Modifier.size(30.dp), state = state)
                Column(Modifier.weight(1f)) {
                    Text("${index + 1}. $title", style = MaterialTheme.typography.titleSmall)
                    Text(detail, style = MaterialTheme.typography.bodySmall, color = TApiMuted)
                }
            }
        }
    }
}

@Composable
private fun StatusCard(status: TokenUiStatus) {
    val (title, subtitle, color) = when (status) {
        TokenUiStatus.Missing -> Triple(
            "T‑API не подключён",
            "Вставьте read-only токен пользователя.",
            TApiMuted,
        )
        TokenUiStatus.Connected -> Triple(
            "T‑API подключён",
            "Токен хранится на сервере Analyst AI и привязан к аккаунту.",
            TApiGreen,
        )
        TokenUiStatus.Checking -> Triple(
            "Проверяем состояние подключения",
            "Ожидаем ответ сервера о сохранённом подключении.",
            TApiBlue,
        )
        TokenUiStatus.Saving -> Triple("Проверка и сохранение токена", "Сервер выполняет запрос к брокеру и сохраняет подключение. Завершение появится только после подтверждения.", TApiBlue)
        TokenUiStatus.Removing -> Triple("Отключаем доступ к данным", "Ожидаем подтверждение удаления токена на сервере.", TApiBlue)
        is TokenUiStatus.Error -> Triple(
            "Подключение не завершено",
            status.message,
            TApiRed,
        )
    }

    SpectrumCard(Modifier.fillMaxWidth(), emphasized = true) {
        Column(
            modifier = Modifier.padding(22.dp),
            verticalArrangement = Arrangement.spacedBy(5.dp),
        ) {
            SpatialIcon(when (status) { TokenUiStatus.Connected -> "check"; is TokenUiStatus.Error -> "error"; else -> "sources" }, Modifier.size(52.dp),
                tint = color, state = when { status.isBusy() -> SpatialState.Loading; status == TokenUiStatus.Connected -> SpatialState.Success; status is TokenUiStatus.Error -> SpatialState.Attention; else -> SpatialState.Idle })
            Text(
                text = title,
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
                color = color, modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
            )
            Text(
                text = subtitle,
                color = TApiMuted,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

private const val TOKEN_DOCS_URL =
    "https://developer.tbank.ru/invest/intro/intro/token"

