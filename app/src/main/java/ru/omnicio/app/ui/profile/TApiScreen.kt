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
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
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
        mutableStateOf<TokenUiStatus>(
            if (storedTokenExists) TokenUiStatus.Saved else TokenUiStatus.Missing,
        )
    }

    DisposableEffect(activity) {
        activity?.window?.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        onDispose {
            activity?.window?.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
        }
    }

    fun verifyAndSave() {
        if (status == TokenUiStatus.Checking) {
            return
        }

        status = TokenUiStatus.Checking
        scope.launch {
            val candidate = withContext(Dispatchers.IO) {
                tokenInput.trim().ifEmpty { tokenStore.load().orEmpty() }
            }

            if (candidate.isEmpty()) {
                status = TokenUiStatus.Error("Вставьте read-only токен T‑Invest API.")
                return@launch
            }

            when (val result = withContext(Dispatchers.IO) {
                apiClient.checkReadAccess(candidate)
            }) {
                TInvestTokenCheck.Valid -> {
                    val saved = withContext(Dispatchers.IO) {
                        runCatching { tokenStore.save(candidate) }.isSuccess
                    }
                    if (saved) {
                        tokenInput = ""
                        storedTokenExists = true
                        status = TokenUiStatus.Connected
                        onConnectionChanged(true)
                    } else {
                        status = TokenUiStatus.Error(
                            "Токен подтверждён, но не удалось сохранить его в защищённом хранилище.",
                        )
                    }
                }

                TInvestTokenCheck.Invalid -> {
                    status = TokenUiStatus.Error(
                        "T‑Invest API не принял токен. Проверьте, что токен актуален и относится к биржевому контуру.",
                    )
                }

                is TInvestTokenCheck.Unavailable -> {
                    status = TokenUiStatus.Error(result.message)
                }
            }
        }
    }

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
            item {
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

            item {
                StatusCard(status = status)
            }

            item {
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

                        OutlinedTextField(
                            modifier = Modifier.fillMaxWidth(),
                            value = tokenInput,
                            onValueChange = {
                                tokenInput = it
                                if (status !is TokenUiStatus.Checking) {
                                    status = if (storedTokenExists) {
                                        TokenUiStatus.Saved
                                    } else {
                                        TokenUiStatus.Missing
                                    }
                                }
                            },
                            enabled = status != TokenUiStatus.Checking,
                            singleLine = true,
                            label = {
                                Text(
                                    if (storedTokenExists && tokenInput.isEmpty()) {
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
                                    onClick = { showToken = !showToken },
                                    enabled = tokenInput.isNotEmpty(),
                                ) {
                                    Text(if (showToken) "Скрыть" else "Показать")
                                }
                            },
                            keyboardOptions = KeyboardOptions(
                                imeAction = ImeAction.Done,
                            ),
                            keyboardActions = KeyboardActions(
                                onDone = { verifyAndSave() },
                            ),
                        )

                        Button(
                            modifier = Modifier.fillMaxWidth(),
                            onClick = { verifyAndSave() },
                            enabled = status != TokenUiStatus.Checking &&
                                (tokenInput.isNotBlank() || storedTokenExists),
                            colors = ButtonDefaults.buttonColors(
                                containerColor = Color(0xFF111318),
                                contentColor = Color.White,
                            ),
                        ) {
                            if (status == TokenUiStatus.Checking) {
                                CircularProgressIndicator(
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

                        if (storedTokenExists) {
                            OutlinedButton(
                                modifier = Modifier.fillMaxWidth(),
                                onClick = {
                                    tokenStore.clear()
                                    tokenInput = ""
                                    storedTokenExists = false
                                    status = TokenUiStatus.Missing
                                    onConnectionChanged(false)
                                },
                                enabled = status != TokenUiStatus.Checking,
                            ) {
                                Text("Удалить токен с устройства")
                            }
                        }
                    }
                }
            }

            item {
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
                        TextButton(
                            onClick = {
                                uriHandler.openUri(TOKEN_DOCS_URL)
                            },
                        ) {
                            Text(
                                text = "Открыть официальную инструкцию T‑Invest",
                                color = TApiBlue,
                            )
                        }
                    }
                }
            }

            item {
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
                            text = "Привязку токена к серверному аккаунту Analyst AI добавим только вместе с серверной авторизацией пользователя, чтобы не придумывать небезопасную схему заранее.",
                            color = TApiMuted,
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
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

private tailrec fun Context.findActivity(): Activity? =
    when (this) {
        is Activity -> this
        is ContextWrapper -> baseContext.findActivity()
        else -> null
    }

private const val TOKEN_DOCS_URL =
    "https://developer.tbank.ru/invest/intro/intro/token"
