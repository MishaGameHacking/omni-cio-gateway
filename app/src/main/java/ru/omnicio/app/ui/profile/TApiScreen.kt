package ru.omnicio.app.ui.profile

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.view.WindowManager
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
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
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
import ru.omnicio.app.data.tinvest.TInvestApiClient
import ru.omnicio.app.data.tinvest.TInvestTokenCheck
import ru.omnicio.app.data.tinvest.TInvestTokenStore

private sealed interface TokenUiStatus {
    data object Missing : TokenUiStatus
    data object Saved : TokenUiStatus
    data object Checking : TokenUiStatus
    data object Connected : TokenUiStatus
    data class Error(val message: String) : TokenUiStatus
}

private data class TokenVerificationOutcome(
    val status: TokenUiStatus,
    val connected: Boolean,
)

private val TApiBackground = Color(0xFFF5F6F8)
private val TApiCard = Color.White
private val TApiMuted = Color(0xFF858C96)
private val TApiBlue = Color(0xFF4D8FEA)
private val TApiGreen = Color(0xFF178B4D)
private val TApiRed = Color(0xFFB42318)

@Composable
fun TApiScreen(
    onBack: () -> Unit,
    onConnectionChanged: (Boolean) -> Unit,
    modifier: Modifier = Modifier,
) {
    BackHandler(onBack = onBack)

    val context = LocalContext.current
    val uriHandler = LocalUriHandler.current
    val activity = remember(context) { context.findActivity() }
    val tokenStore = remember(context) { TInvestTokenStore(context) }
    val apiClient = remember { TInvestApiClient() }
    val scope = rememberCoroutineScope()

    var tokenInput by rememberSaveable { mutableStateOf("") }
    var showToken by rememberSaveable { mutableStateOf(false) }
    var storedTokenExists by remember { mutableStateOf(tokenStore.hasToken()) }
    var status by remember {
        mutableStateOf<TokenUiStatus>(initialTokenStatus(storedTokenExists))
    }

    ProtectSensitiveScreen(activity)

    val verify = {
        if (status != TokenUiStatus.Checking) {
            status = TokenUiStatus.Checking
            scope.launch {
                val outcome = verifyAndPersistToken(
                    tokenInput = tokenInput,
                    tokenStore = tokenStore,
                    apiClient = apiClient,
                )
                status = outcome.status
                if (outcome.connected) {
                    tokenInput = ""
                    storedTokenExists = true
                    onConnectionChanged(true)
                }
            }
        }
    }

    TApiContent(
        modifier = modifier,
        status = status,
        tokenInput = tokenInput,
        showToken = showToken,
        storedTokenExists = storedTokenExists,
        onBack = onBack,
        onTokenInputChange = { value ->
            tokenInput = value
            if (status != TokenUiStatus.Checking) {
                status = initialTokenStatus(storedTokenExists)
            }
        },
        onToggleTokenVisibility = {
            showToken = !showToken
        },
        onVerify = verify,
        onRemove = {
            tokenStore.clear()
            tokenInput = ""
            storedTokenExists = false
            status = TokenUiStatus.Missing
            onConnectionChanged(false)
        },
        onOpenDocs = {
            uriHandler.openUri(TOKEN_DOCS_URL)
        },
    )
}

@Composable
private fun ProtectSensitiveScreen(activity: Activity?) {
    DisposableEffect(activity) {
        activity?.window?.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        onDispose {
            activity?.window?.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
        }
    }
}

private suspend fun verifyAndPersistToken(
    tokenInput: String,
    tokenStore: TInvestTokenStore,
    apiClient: TInvestApiClient,
): TokenVerificationOutcome {
    val candidate = withContext(Dispatchers.IO) {
        tokenInput.trim().ifEmpty { tokenStore.load().orEmpty() }
    }

    if (candidate.isEmpty()) {
        return TokenVerificationOutcome(
            status = TokenUiStatus.Error("Вставьте read-only токен T‑Invest API."),
            connected = false,
        )
    }

    val check = withContext(Dispatchers.IO) {
        apiClient.checkReadAccess(candidate)
    }
    return when (check) {
        TInvestTokenCheck.Valid -> persistValidatedToken(candidate, tokenStore)
        TInvestTokenCheck.Invalid -> TokenVerificationOutcome(
            status = TokenUiStatus.Error(
                "T‑Invest API не принял токен. Проверьте, что токен актуален и относится к биржевому контуру.",
            ),
            connected = false,
        )
        is TInvestTokenCheck.Unavailable -> TokenVerificationOutcome(
            status = TokenUiStatus.Error(check.message),
            connected = false,
        )
    }
}

private suspend fun persistValidatedToken(
    token: String,
    tokenStore: TInvestTokenStore,
): TokenVerificationOutcome {
    val saved = withContext(Dispatchers.IO) {
        runCatching { tokenStore.save(token) }.isSuccess
    }
    return if (saved) {
        TokenVerificationOutcome(
            status = TokenUiStatus.Connected,
            connected = true,
        )
    } else {
        TokenVerificationOutcome(
            status = TokenUiStatus.Error(
                "Токен подтверждён, но не удалось сохранить его в защищённом хранилище.",
            ),
            connected = false,
        )
    }
}

private fun initialTokenStatus(storedTokenExists: Boolean): TokenUiStatus =
    if (storedTokenExists) TokenUiStatus.Saved else TokenUiStatus.Missing

@Composable
private fun TApiContent(
    status: TokenUiStatus,
    tokenInput: String,
    showToken: Boolean,
    storedTokenExists: Boolean,
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
                    storedTokenExists = storedTokenExists,
                    onTokenInputChange = onTokenInputChange,
                    onToggleTokenVisibility = onToggleTokenVisibility,
                    onVerify = onVerify,
                    onRemove = onRemove,
                )
            }
            item { TokenDocsCard(onOpenDocs = onOpenDocs) }
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
    storedTokenExists: Boolean,
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
                text = "Токен доступа",
                fontSize = 22.sp,
                lineHeight = 28.sp,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = "Используйте read-only токен. Он подходит для чтения счетов и портфеля и не даёт Analyst AI права выставлять торговые поручения.",
                color = TApiMuted,
                style = MaterialTheme.typography.bodyMedium,
            )
            TokenField(
                value = tokenInput,
                showToken = showToken,
                storedTokenExists = storedTokenExists,
                enabled = !checking,
                onValueChange = onTokenInputChange,
                onToggleVisibility = onToggleTokenVisibility,
                onDone = onVerify,
            )
            VerifyButton(
                checking = checking,
                storedTokenExists = storedTokenExists,
                tokenInput = tokenInput,
                onVerify = onVerify,
            )
            if (storedTokenExists) {
                OutlinedButton(
                    modifier = Modifier.fillMaxWidth(),
                    onClick = onRemove,
                    enabled = !checking,
                ) {
                    Text("Удалить токен с устройства")
                }
            }
        }
    }
}

@Composable
private fun TokenField(
    value: String,
    showToken: Boolean,
    storedTokenExists: Boolean,
    enabled: Boolean,
    onValueChange: (String) -> Unit,
    onToggleVisibility: () -> Unit,
    onDone: () -> Unit,
) {
    OutlinedTextField(
        modifier = Modifier.fillMaxWidth(),
        value = value,
        onValueChange = onValueChange,
        enabled = enabled,
        singleLine = true,
        label = {
            Text(
                if (storedTokenExists && value.isEmpty()) {
                    "Новый токен или проверка сохранённого"
                } else {
                    "Вставьте токен"
                },
            )
        },
        visualTransformation = if (showToken) {
            VisualTransformation.None
        } else {
            PasswordVisualTransformation()
        },
        trailingIcon = {
            TextButton(
                onClick = onToggleVisibility,
                enabled = value.isNotEmpty(),
            ) {
                Text(if (showToken) "Скрыть" else "Показать")
            }
        },
        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
        keyboardActions = KeyboardActions(onDone = { onDone() }),
    )
}

@Composable
private fun VerifyButton(
    checking: Boolean,
    storedTokenExists: Boolean,
    tokenInput: String,
    onVerify: () -> Unit,
) {
    Button(
        modifier = Modifier.fillMaxWidth(),
        onClick = onVerify,
        enabled = !checking && (tokenInput.isNotBlank() || storedTokenExists),
        colors = ButtonDefaults.buttonColors(
            containerColor = Color(0xFF111318),
            contentColor = Color.White,
        ),
    ) {
        if (checking) {
            CircularProgressIndicator(
                modifier = Modifier.padding(2.dp),
                color = Color.White,
                strokeWidth = 2.dp,
            )
        } else {
            Text(
                if (storedTokenExists && tokenInput.isBlank()) {
                    "Проверить сохранённый токен"
                } else {
                    "Проверить и сохранить"
                },
            )
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
                text = "Выпустите read-only токен в настройках T‑Инвестиций. Токен показывается для сохранения только один раз, поэтому скопируйте его сразу и вставьте выше.",
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
                text = "После успешной проверки токен хранится только на этом устройстве в зашифрованном виде с ключом Android Keystore. Токен не записывается в GitHub, APK или логи.",
                color = TApiMuted,
                style = MaterialTheme.typography.bodyMedium,
            )
            Text(
                text = "Привязку токена к серверному аккаунту Analyst AI добавим вместе с серверной авторизацией пользователя, чтобы секрет не оказался в неподготовленном серверном контуре.",
                color = TApiMuted,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

@Composable
private fun StatusCard(status: TokenUiStatus) {
    val (title, subtitle, color) = statusPresentation(status)
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

private fun statusPresentation(status: TokenUiStatus): Triple<String, String, Color> =
    when (status) {
        TokenUiStatus.Missing -> Triple(
            "T‑API не подключён",
            "Вставьте read-only токен пользователя.",
            TApiMuted,
        )
        TokenUiStatus.Saved -> Triple(
            "Токен сохранён",
            "Можно проверить текущий токен или заменить его новым.",
            TApiBlue,
        )
        TokenUiStatus.Checking -> Triple(
            "Проверяем токен",
            "Analyst AI выполняет read-only запрос GetAccounts.",
            TApiBlue,
        )
        TokenUiStatus.Connected -> Triple(
            "T‑API подключён",
            "Read-only доступ к счетам подтверждён.",
            TApiGreen,
        )
        is TokenUiStatus.Error -> Triple(
            "Подключение не завершено",
            status.message,
            TApiRed,
        )
    }

private tailrec fun Context.findActivity(): Activity? =
    when (this) {
        is Activity -> this
        is ContextWrapper -> baseContext.findActivity()
        else -> null
    }

private const val TOKEN_DOCS_URL =
    "https://developer.tbank.ru/invest/intro/intro/token"
