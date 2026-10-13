package ru.omnicio.app.ui.profile

import androidx.activity.compose.BackHandler
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
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
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
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import ru.omnicio.app.data.backend.AnalystBackendClient
import ru.omnicio.app.data.backend.BackendResult

private sealed interface TokenUiStatus {
    data object Missing : TokenUiStatus
    data object Connected : TokenUiStatus
    data object Checking : TokenUiStatus
    data class Error(val message: String) : TokenUiStatus
}

private val TApiBackground: Color
    @Composable get() = MaterialTheme.colorScheme.background
private val TApiCard: Color
    @Composable get() = MaterialTheme.colorScheme.surface
private val TApiMuted: Color
    @Composable get() = MaterialTheme.colorScheme.onSurfaceVariant
private val TApiBlue: Color
    @Composable get() = MaterialTheme.colorScheme.primary
private val TApiGreen = Color(0xFF178B4D)
private val TApiRed: Color
    @Composable get() = MaterialTheme.colorScheme.error

@Composable
fun TApiScreen(
    accessToken: String,
    tApiConfigured: Boolean,
    onBack: () -> Unit,
    onConnectionChanged: (Boolean) -> Unit,
    modifier: Modifier = Modifier,
) {
    BackHandler(onBack = onBack)

    val uriHandler = LocalUriHandler.current
    val backend = remember { AnalystBackendClient() }
    val scope = rememberCoroutineScope()

    var tokenInput by remember { mutableStateOf("") }
    var showToken by remember { mutableStateOf(false) }
    var docsError by remember { mutableStateOf<String?>(null) }
    var status by remember(tApiConfigured) {
        mutableStateOf<TokenUiStatus>(
            if (tApiConfigured) TokenUiStatus.Connected else TokenUiStatus.Missing,
        )
    }

    val verify = {
        if (status != TokenUiStatus.Checking && tokenInput.isNotBlank()) {
            status = TokenUiStatus.Checking
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
                    }
                }
            }
        }
    }

    TApiContent(
        modifier = modifier,
        status = status,
        tokenInput = tokenInput,
        showToken = showToken,
        docsError = docsError,
        tApiConfigured = tApiConfigured || status == TokenUiStatus.Connected,
        onBack = onBack,
        onTokenInputChange = { value ->
            tokenInput = value
            if (status !is TokenUiStatus.Checking) {
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
            if (status != TokenUiStatus.Checking) {
                status = TokenUiStatus.Checking
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
    Scaffold(
        modifier = modifier.fillMaxSize(),
        containerColor = TApiBackground,
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
            contentPadding = PaddingValues(
                start = 20.dp,
                top = 18.dp,
                end = 20.dp,
                bottom = 32.dp,
            ),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            item { TApiHeader(onBack = onBack) }
            item { StatusCard(status = status) }
            item {
                TokenInputCard(
                    status = status,
                    tokenInput = tokenInput,
                    showToken = showToken,
                    tApiConfigured = tApiConfigured,
                    onTokenInputChange = onTokenInputChange,
                    onToggleTokenVisibility = onToggleTokenVisibility,
                    onVerify = onVerify,
                    onRemove = onRemove,
                )
            }
            item { TokenDocsCard(onOpenDocs = onOpenDocs) }
            docsError?.let { message ->
                item { DocsErrorCard(message) }
            }
            item { TokenSecurityCard() }
        }
    }
}

@Composable
private fun TApiHeader(onBack: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        TextButton(onClick = onBack) {
            Text(
                text = "‹",
                fontSize = 34.sp,
                lineHeight = 34.sp,
                color = MaterialTheme.colorScheme.onSurface,
            )
        }
        Column {
            Text(
                text = "T‑API",
                fontSize = 32.sp,
                lineHeight = 38.sp,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = "Подключение T‑Invest API",
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
    val checking = status == TokenUiStatus.Checking
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(28.dp),
        colors = CardDefaults.cardColors(containerColor = TApiCard),
    ) {
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
                text = "Используйте read-only токен. После проверки он привязывается к вашему Telegram ID и хранится зашифрованно на сервере Analyst AI.",
                color = TApiMuted,
                style = MaterialTheme.typography.bodyMedium,
            )
            OutlinedTextField(
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
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { onVerify() }),
            )
            Button(
                modifier = Modifier.fillMaxWidth(),
                onClick = onVerify,
                enabled = !checking && tokenInput.isNotBlank(),
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    contentColor = MaterialTheme.colorScheme.onPrimary,
                ),
            ) {
                if (checking) {
                    CircularProgressIndicator(
                        color = MaterialTheme.colorScheme.onPrimary,
                        strokeWidth = 2.dp,
                    )
                } else {
                    Text(if (tApiConfigured) "Проверить и заменить" else "Проверить и подключить")
                }
            }
            if (tApiConfigured) {
                OutlinedButton(
                    modifier = Modifier.fillMaxWidth(),
                    onClick = onRemove,
                    enabled = !checking,
                ) {
                    Text("Отключить T‑API")
                }
            }
        }
    }
}

@Composable
private fun TokenDocsCard(onOpenDocs: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(28.dp),
        colors = CardDefaults.cardColors(containerColor = TApiCard),
    ) {
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
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
    ) {
        Text(
            text = message,
            modifier = Modifier.padding(18.dp),
            color = MaterialTheme.colorScheme.onErrorContainer,
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}

@Composable
private fun TokenSecurityCard() {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(28.dp),
        colors = CardDefaults.cardColors(containerColor = TApiCard),
    ) {
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
                text = "Токен передаётся по HTTPS на backend Analyst AI, проверяется read-only запросом T‑Invest и хранится на Timeweb в зашифрованном виде, привязанном к вашему Telegram ID.",
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
            "Проверяем подключение",
            "Analyst AI проверяет токен через сервер.",
            TApiBlue,
        )
        is TokenUiStatus.Error -> Triple(
            "Подключение не завершено",
            status.message,
            TApiRed,
        )
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(28.dp),
        colors = CardDefaults.cardColors(containerColor = TApiCard),
    ) {
        Column(
            modifier = Modifier.padding(22.dp),
            verticalArrangement = Arrangement.spacedBy(5.dp),
        ) {
            Text(
                text = title,
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
                color = color,
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
