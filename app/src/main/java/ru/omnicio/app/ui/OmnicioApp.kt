package ru.omnicio.app.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.repeatOnLifecycle
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import ru.omnicio.app.R
import ru.omnicio.app.ui.theme.OmnicioTheme

@Composable
internal fun OmniIcon(resource: Int, description: String? = null, modifier: Modifier = Modifier) {
    Icon(painterResource(resource), description, modifier.size(24.dp))
}

@Composable
internal fun OmniCard(content: @Composable ColumnScope.() -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp), content = content)
    }
}

@Composable
internal fun SectionTitle(text: String) {
    Text(text, style = MaterialTheme.typography.titleLarge)
}

@Composable
internal fun EmptyState(title: String, detail: String, icon: Int = R.drawable.ic_info) {
    OmniCard {
        OmniIcon(icon, modifier = Modifier.size(32.dp))
        SectionTitle(title)
        Text(detail, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun OmnicioRoot(model: OmnicioViewModel = viewModel()) {
    val state by model.uiState.collectAsStateWithLifecycle()
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    var page by rememberSaveable { mutableStateOf("Обзор") }
    val destinations = listOf("Обзор" to R.drawable.ic_overview,
        "Портфель" to R.drawable.ic_portfolio, "Помощник" to R.drawable.ic_assistant)
    LaunchedEffect(state.authenticated) { if (state.authenticated) model.refresh() else page = "Обзор" }
    LaunchedEffect(lifecycle, state.authenticated) {
        if (state.authenticated) lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
            while (isActive) { model.refresh(); delay(60_000) }
        }
    }
    OmnicioTheme(darkTheme = state.darkTheme) {
        if (!state.authenticated) {
            AuthScreen(state, model)
        } else BoxWithConstraints(Modifier.fillMaxSize()) {
            val wide = maxWidth >= 600.dp
            Scaffold(
                topBar = {
                    TopAppBar(title = {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            Image(painterResource(R.drawable.omnicio_logo), null, Modifier.size(30.dp))
                            Text(if (page == "Настройки") page else "OMNICIO")
                        }
                    }, navigationIcon = {
                        if (page == "Настройки") IconButton(onClick = { page = "Обзор" }) {
                            OmniIcon(R.drawable.ic_back, "Назад")
                        }
                    }, actions = {
                        IconButton(onClick = model::refresh, enabled = !state.busy) {
                            OmniIcon(R.drawable.ic_refresh, "Загрузить данные с сервера")
                        }
                        IconButton(onClick = { page = "Настройки" }) {
                            OmniIcon(R.drawable.ic_settings, "Настройки")
                        }
                    })
                },
                bottomBar = {
                    if (!wide) NavigationBar {
                        destinations.forEach { (title, icon) ->
                            NavigationBarItem(selected = page == title, onClick = { page = title },
                                icon = { OmniIcon(icon) }, label = { Text(title) })
                        }
                    }
                },
            ) { padding ->
                Row(Modifier.padding(padding).fillMaxSize()) {
                    if (wide) NavigationRail {
                        destinations.forEach { (title, icon) ->
                            NavigationRailItem(selected = page == title, onClick = { page = title },
                                icon = { OmniIcon(icon) }, label = { Text(title) })
                        }
                    }
                    Column(Modifier.weight(1f).fillMaxHeight(), horizontalAlignment = Alignment.CenterHorizontally) {
                        if (state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                        state.error?.let {
                            Surface(color = MaterialTheme.colorScheme.errorContainer) {
                                Text(it, Modifier.fillMaxWidth().padding(16.dp), color = MaterialTheme.colorScheme.onErrorContainer)
                            }
                        }
                        state.notice?.let { Text(it, Modifier.padding(horizontal = 20.dp, vertical = 8.dp)) }
                        Box(Modifier.weight(1f).widthIn(max = 900.dp)) {
                            when (page) {
                                "Портфель" -> PortfolioScreen(state)
                                "Помощник" -> AssistantScreen(state, model)
                                "Настройки" -> SettingsScreen(state, model)
                                else -> OverviewScreen(state, model, onConnect = { page = "Настройки" })
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun AuthScreen(state: AppUiState, model: OmnicioViewModel) {
    var mode by remember { mutableStateOf("login") }
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var code by remember { mutableStateOf("") }
    var privacy by remember { mutableStateOf(false) }
    var consent by remember { mutableStateOf(false) }
    var terms by remember { mutableStateOf(false) }
    var adult by remember { mutableStateOf(false) }
    val uri = LocalUriHandler.current
    Surface(Modifier.fillMaxSize()) {
        Column(Modifier.safeDrawingPadding().imePadding().fillMaxSize().verticalScroll(rememberScrollState())
            .padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Column(Modifier.widthIn(max = 480.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                Spacer(Modifier.height(12.dp))
                Image(painterResource(R.drawable.omnicio_logo), "OMNICIO", Modifier.size(64.dp))
                Text("Ваш портфель.\nПодтверждённые данные.", style = MaterialTheme.typography.headlineLarge)
                Text("Войдите в OMNICIO. Счета, история и расчёты загружаются с сервера.",
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                state.notice?.let { Text(it) }
                if (state.challengeId != null) {
                    SectionTitle("Проверьте почту")
                    Text("Введите код из письма. Не закрывайте приложение до подтверждения.")
                    OutlinedTextField(code, { code = it.filter(Char::isDigit).take(6) },
                        label = { Text("Код из письма") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
                    if (state.challengePurpose == "reset") SecretField(password, { password = it }, "Новый пароль")
                    Button(onClick = { model.verify(code, password); password = ""; code = "" },
                        enabled = !state.busy && code.length == 6 &&
                            (state.challengePurpose != "reset" || password.isNotBlank()), modifier = Modifier.fillMaxWidth()) {
                        Text("Подтвердить")
                    }
                    TextButton(onClick = model::resendCode, enabled = !state.busy) { Text("Отправить код повторно") }
                    TextButton(onClick = model::cancelChallenge, enabled = !state.busy) { Text("Вернуться ко входу") }
                } else {
                    SectionTitle(when (mode) { "register" -> "Создать аккаунт"; "reset" -> "Восстановить доступ"; else -> "Вход" })
                    OutlinedTextField(email, { email = it }, label = { Text("Электронная почта") },
                        modifier = Modifier.fillMaxWidth(), singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email))
                    if (mode != "reset") SecretField(password, { password = it }, "Пароль")
                    if (mode == "register") {
                        CheckLine("Мне исполнилось 18 лет", adult) { adult = it }
                        CheckLine("Принимаю условия использования", terms) { terms = it }
                        CheckLine("Ознакомлен с политикой конфиденциальности", privacy) { privacy = it }
                        CheckLine("Согласен на обработку персональных данных", consent) { consent = it }
                        LegalLinks()
                    }
                    Button(onClick = {
                        when (mode) {
                            "register" -> model.register(email, password)
                            "reset" -> model.resetPassword(email)
                            else -> model.login(email, password)
                        }
                        password = ""
                    }, enabled = !state.busy && state.authConfig != null && email.isNotBlank() &&
                        (mode == "reset" || password.isNotEmpty()) &&
                        (mode != "register" || adult && terms && privacy && consent), modifier = Modifier.fillMaxWidth()) {
                        Text(when (mode) { "register" -> "Зарегистрироваться"; "reset" -> "Получить код"; else -> "Войти" })
                    }
                    if (state.authConfig == null && !state.busy) OutlinedButton(onClick = model::loadConfig) { Text("Повторить подключение") }
                    TextButton(onClick = { mode = if (mode == "login") "register" else "login"; password = "" }, enabled = !state.busy) {
                        Text(if (mode == "login") "Создать аккаунт" else "Уже есть аккаунт — войти")
                    }
                    if (mode == "login") TextButton(onClick = { mode = "reset"; password = "" }, enabled = !state.busy) { Text("Забыли пароль?") }
                }
                HorizontalDivider()
                Text("Финансовые данные не сохраняются на телефоне. После закрытия процесса приложения потребуется новый вход.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                TextButton(onClick = { uri.openUri("$SERVER_ORIGIN/legal/privacy.html") }) { Text("Конфиденциальность") }
            }
        }
    }
}

@Composable
internal fun SecretField(value: String, onChange: (String) -> Unit, label: String) {
    OutlinedTextField(value, onChange, label = { Text(label) }, modifier = Modifier.fillMaxWidth(),
        singleLine = true, visualTransformation = PasswordVisualTransformation(),
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password))
}

@Composable
internal fun CheckLine(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Checkbox(checked, onChange)
        Text(label, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
internal fun LegalLinks() {
    val uri = LocalUriHandler.current
    Column {
        listOf("Условия использования" to "terms", "Конфиденциальность" to "privacy", "Согласие на обработку" to "consent").forEach { (title, path) ->
            TextButton(onClick = { uri.openUri("$SERVER_ORIGIN/legal/$path.html") }) { Text(title) }
        }
    }
}
