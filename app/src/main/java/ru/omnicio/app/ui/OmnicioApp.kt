package ru.omnicio.app.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.ui.semantics.Role
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

private const val SETTINGS = "Настройки"

@Composable
internal fun OmnicioRoot(model: OmnicioViewModel = viewModel()) {
    val state by model.uiState.collectAsStateWithLifecycle()
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    var page by rememberSaveable { mutableStateOf("Обзор") }
    BackHandler(enabled = state.authenticated && page != "Обзор") { page = "Обзор" }
    val destinations = listOf("Обзор" to R.drawable.ic_overview,
        "Портфель" to R.drawable.ic_portfolio, "Помощник" to R.drawable.ic_assistant)
    LaunchedEffect(state.authenticated, state.socialFlow == null, state.challengePurpose) {
        if (state.authenticated && state.socialFlow == null && state.challengePurpose == null) model.refresh()
        else if (!state.authenticated) page = "Обзор"
    }
    LaunchedEffect(lifecycle, state.authenticated) {
        if (state.authenticated) lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
            while (isActive) { if (state.socialFlow == null) model.refresh(); delay(60_000) }
        }
    }
    OmnicioTheme(darkTheme = state.darkTheme) {
        if (state.socialFlow != null) {
            SocialFlowScreen(state, model)
        } else if (!state.authenticated || state.challengePurpose == "enroll") {
            AuthScreen(state, model)
        } else if (state.legalConsent != null) {
            LegalConsentScreen(state, model)
        } else BoxWithConstraints(Modifier.fillMaxSize()) {
            val wide = maxWidth >= 600.dp
            Scaffold(
                topBar = {
                    AppToolbar(page, state.busy, model::refresh) { page = it }
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
                        StatusMessages(state)
                        Box(Modifier.weight(1f).widthIn(max = 900.dp)) {
                            AppPage(page, state, model) { page = SETTINGS }
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AppToolbar(page: String, busy: Boolean, refresh: () -> Unit, navigate: (String) -> Unit) {
    TopAppBar(title = {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Image(painterResource(R.drawable.omnicio_logo), null, Modifier.size(30.dp))
            Text(if (page == SETTINGS) page else "OMNICIO")
        }
    }, navigationIcon = {
        if (page == SETTINGS) IconButton(onClick = { navigate("Обзор") }) {
            OmniIcon(R.drawable.ic_back, "Назад")
        }
    }, actions = {
        IconButton(onClick = refresh, enabled = !busy) { OmniIcon(R.drawable.ic_refresh, "Загрузить данные с сервера") }
        IconButton(onClick = { navigate(SETTINGS) }) { OmniIcon(R.drawable.ic_settings, SETTINGS) }
    })
}

@Composable
private fun AppPage(page: String, state: AppUiState, model: OmnicioViewModel, connect: () -> Unit) {
    when (page) {
        "Портфель" -> PortfolioScreen(state)
        "Помощник" -> AssistantScreen(state, model)
        SETTINGS -> SettingsScreen(state, model)
        else -> OverviewScreen(state, model, onConnect = connect)
    }
}

@Composable
internal fun StatusMessages(state: AppUiState) {
    if (state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
    state.error?.let {
        Surface(color = MaterialTheme.colorScheme.errorContainer) {
            Text(it, Modifier.fillMaxWidth().padding(16.dp), color = MaterialTheme.colorScheme.onErrorContainer)
        }
    }
    state.notice?.let { Text(it, Modifier.padding(horizontal = 20.dp, vertical = 8.dp)) }
}

@Stable
internal class AuthFormState {
    var mode by mutableStateOf("login")
    var email by mutableStateOf("")
    var password by mutableStateOf("")
    var code by mutableStateOf("")
    var privacy by mutableStateOf(false)
    var consent by mutableStateOf(false)
    var terms by mutableStateOf(false)
    var adult by mutableStateOf(false)

    val title: String get() = when (mode) {
        "register" -> "Создать аккаунт"
        "reset" -> "Восстановить доступ"
        else -> "Вход"
    }
    val submitLabel: String get() = when (mode) {
        "register" -> "Зарегистрироваться"
        "reset" -> "Получить код"
        else -> "Войти"
    }
    val valid: Boolean get() = email.isNotBlank() && (mode == "reset" || password.isNotEmpty()) &&
        (mode != "register" || adult && terms && privacy && consent)

    fun submit(model: OmnicioViewModel) {
        when (mode) {
            "register" -> model.register(email, password)
            "reset" -> model.resetPassword(email)
            else -> model.login(email, password)
        }
        password = ""
    }
}

@Composable
private fun AuthScreen(state: AppUiState, model: OmnicioViewModel) {
    val legalVersions = state.authConfig?.optJSONObject("legal_versions")?.toString()
    val form = remember(legalVersions) { AuthFormState() }
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
                StatusMessages(state)
                if (state.challengeId != null) VerifyForm(state, model, form)
                else {
                    if (form.mode == "login") {
                        SocialButtons(state, model)
                        HorizontalDivider()
                        Text("Или войдите по почте", style = MaterialTheme.typography.titleMedium)
                    }
                    SignInForm(state, model, form)
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
private fun VerifyForm(state: AppUiState, model: OmnicioViewModel, form: AuthFormState) {
    val digits = state.authConfig?.optInt("email_code_digits") ?: 0
    var now by remember { mutableLongStateOf(android.os.SystemClock.elapsedRealtime()) }
    LaunchedEffect(state.challengeId) {
        while (isActive) { now = android.os.SystemClock.elapsedRealtime(); delay(1000) }
    }
    SectionTitle("Проверьте почту")
    Text("Введите код из письма. Не закрывайте приложение до подтверждения.")
    OutlinedTextField(form.code, { form.code = it.filter { c -> c in '0'..'9' }.take(digits) },
        label = { Text("Код из письма · $digits цифр") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
    if (state.challengePurpose == "reset") SecretField(form.password, { form.password = it }, "Новый пароль")
    Button(onClick = { model.verify(form.code, form.password); form.password = ""; form.code = "" },
        enabled = !state.busy && digits > 0 && form.code.length == digits && now < state.challengeExpiresAt &&
            (state.challengePurpose != "reset" || form.password.isNotBlank()), modifier = Modifier.fillMaxWidth()) {
        Text("Подтвердить")
    }
    if (now >= state.challengeExpiresAt) Text("Срок действия кода истёк. Запросите новый код.")
    TextButton(onClick = model::resendCode, enabled = !state.busy && now >= state.resendAt) {
        Text(if (now >= state.resendAt) "Отправить код повторно"
            else "Повторная отправка через ${(state.resendAt - now + 999) / 1000} с")
    }
    TextButton(onClick = model::cancelChallenge, enabled = !state.busy) { Text(if (state.authenticated) "Вернуться в профиль" else "Вернуться ко входу") }
}

@Composable
private fun SignInForm(state: AppUiState, model: OmnicioViewModel, form: AuthFormState) {
    val available = state.authConfig?.optBoolean(when (form.mode) {
        "register" -> "registration_available"
        "reset" -> "password_reset_available"
        else -> "login_enabled"
    }, false) == true
    SectionTitle(form.title)
    if (state.authConfig != null && !available) Text("Этот способ доступа временно недоступен. Повторите проверку позже.")
    OutlinedTextField(form.email, { form.email = it }, label = { Text("Электронная почта") },
        modifier = Modifier.fillMaxWidth(), singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email))
    if (form.mode != "reset") SecretField(form.password, { form.password = it }, "Пароль")
    if (form.mode == "register") RegistrationConsent(form)
    Button(onClick = { form.submit(model) }, enabled = !state.busy && available && form.valid,
        modifier = Modifier.fillMaxWidth()) { Text(form.submitLabel) }
    if ((state.authConfig == null || !available) && !state.busy) OutlinedButton(onClick = model::loadConfig) { Text("Повторить подключение") }
    TextButton(onClick = { form.mode = if (form.mode == "login") "register" else "login"; form.password = "" }, enabled = !state.busy) {
        Text(if (form.mode == "login") "Создать аккаунт" else "Уже есть аккаунт — войти")
    }
    if (form.mode == "login") TextButton(onClick = { form.mode = "reset"; form.password = "" }, enabled = !state.busy) { Text("Забыли пароль?") }
}

@Composable
internal fun RegistrationConsent(form: AuthFormState) {
    CheckLine("Мне исполнилось 18 лет", form.adult) { form.adult = it }
    CheckLine("Принимаю условия использования", form.terms) { form.terms = it }
    CheckLine("Ознакомлен с политикой конфиденциальности", form.privacy) { form.privacy = it }
    CheckLine("Согласен на обработку персональных данных", form.consent) { form.consent = it }
    LegalLinks()
}

@Composable
internal fun SecretField(value: String, onChange: (String) -> Unit, label: String) {
    OutlinedTextField(value, onChange, label = { Text(label) }, modifier = Modifier.fillMaxWidth(),
        singleLine = true, visualTransformation = PasswordVisualTransformation(),
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password))
}

@Composable
internal fun CheckLine(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().heightIn(min = 48.dp).toggleable(
        value = checked, role = Role.Checkbox, onValueChange = onChange),
        verticalAlignment = Alignment.CenterVertically) {
        Checkbox(checked, null)
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

@Composable
private fun LegalConsentScreen(state: AppUiState, model: OmnicioViewModel) {
    val versions = state.legalConsent?.toString()
    val form = remember(versions) { AuthFormState() }
    Surface(Modifier.fillMaxSize()) {
        Column(Modifier.safeDrawingPadding().padding(24.dp).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp)) {
            SectionTitle("Обновились документы")
            Text("Ознакомьтесь с актуальными условиями. Согласия сохраняются только после вашего подтверждения.")
            StatusMessages(state)
            if (state.legalConsent?.length() == 0) {
                OutlinedButton(onClick = model::refresh, enabled = !state.busy) { Text("Загрузить документы") }
            } else {
                RegistrationConsent(form)
                Button(onClick = model::acceptLegal,
                    enabled = !state.busy && form.adult && form.terms && form.privacy && form.consent) {
                    Text("Подтвердить и продолжить")
                }
            }
            TextButton(onClick = model::logout) { Text("Выйти без подтверждения") }
        }
    }
}
