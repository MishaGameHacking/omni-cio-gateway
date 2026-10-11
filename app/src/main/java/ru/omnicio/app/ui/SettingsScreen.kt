package ru.omnicio.app.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.clickable
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import ru.omnicio.app.BuildConfig
import ru.omnicio.app.R

@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun SettingsScreen(state: AppUiState, model: OmnicioViewModel,
    authenticate: ((Boolean) -> Unit) -> Unit) {
    var section by remember { mutableStateOf<String?>(null) }
    val sections = listOf("Оформление" to R.drawable.ic_moon, "Доступ" to R.drawable.ic_shield,
        "Счёт" to R.drawable.ic_bank, "Стратегия" to R.drawable.ic_portfolio,
        "Цели" to R.drawable.ic_goal, "О приложении" to R.drawable.ic_info)
    LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Text("Профиль", style = MaterialTheme.typography.headlineLarge)
            Text("OMNICIO · ${state.publicId.orEmpty()}", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        sections.forEach { (title, icon) -> item {
            Card(Modifier.fillMaxWidth().clickable { section = title },
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
                ListItem(headlineContent = { Text(title, style = MaterialTheme.typography.titleMedium) },
                    leadingContent = { OmniIcon(icon) }, trailingContent = { OmniIcon(R.drawable.ic_chevron) })
            }
        } }
        item { TextButton(onClick = model::logout, enabled = !state.busy) { Text("Выйти из аккаунта") } }
    }
    section?.let { current ->
        ModalBottomSheet(onDismissRequest = { section = null },
            properties = sheetProperties(state.screenshotsBlocked)) {
            Box(Modifier.fillMaxHeight(0.9f)) { SettingsDetails(state, model, current, authenticate) }
        }
    }
}

@Composable
private fun SettingsDetails(state: AppUiState, model: OmnicioViewModel, section: String,
    authenticate: ((Boolean) -> Unit) -> Unit) {
    var credential by remember { mutableStateOf("") }
    var accepted by remember { mutableStateOf(false) }
    var disconnect by remember { mutableStateOf(false) }
    var goalForm by remember { mutableStateOf(false) }
    val connected = state.workspace?.connection?.connected == true
    LazyColumn(contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item { Text(section, style = MaterialTheme.typography.headlineMedium) }
        if (section == "Доступ") item { AccessSettings(state, model) }
        if (section == "Доступ") item {
            var authError by remember { mutableStateOf(false) }
            OmniCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Защита входа", style = MaterialTheme.typography.titleMedium)
                        Text("Отпечаток или код телефона", style = MaterialTheme.typography.bodySmall)
                    }
                    Switch(state.biometricLock, { value -> authenticate { success ->
                        authError = !success
                        if (success) model.setBiometricLock(value)
                    } }, modifier = Modifier.semantics { contentDescription = "Защита входа" })
                }
                if (authError) Text("Подтверждение не получено. Проверьте блокировку экрана в настройках телефона.",
                    style = MaterialTheme.typography.bodySmall)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Запретить скриншоты", style = MaterialTheme.typography.titleMedium)
                        Text(if (state.screenshotsBlocked) "Снимки и запись экрана запрещены" else "Снимки и запись экрана разрешены",
                            style = MaterialTheme.typography.bodySmall)
                    }
                    Switch(state.screenshotsBlocked, model::setScreenshotsBlocked,
                        modifier = Modifier.semantics { contentDescription = "Запретить скриншоты" })
                }
            }
        }
        if (section == "Стратегия") item { StrategySettings(state, model) }
        if (section == "Оформление") item {
            OmniCard {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    OmniIcon(R.drawable.ic_moon)
                    Text("Тёмная тема", Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
                    Switch(state.darkTheme, model::setDarkTheme,
                        modifier = Modifier.semantics { contentDescription = "Тёмная тема" })
                }
                Text("Оформление сохраняется на этом устройстве.", style = MaterialTheme.typography.bodySmall)
            }
        }
        if (section == "Счёт") item {
            OmniCard {
                OmniIcon(R.drawable.ic_bank)
                SectionTitle("Т-Инвестиции")
                when {
                    state.workspace == null -> {
                        Text("Состояние подключения не получено.")
                        OutlinedButton(onClick = model::refresh, enabled = !state.busy) { Text("Проверить подключение") }
                    }
                    connected -> {
                        Text(state.workspace.connection.name ?: "Подключённый счёт")
                        Text("Проверка: ${timestampLabel(state.workspace.connection.verifiedAt)}", style = MaterialTheme.typography.bodySmall)
                        Text("Сервер читает данные счёта. Приложение не отправляет торговые поручения.")
                        OutlinedButton(onClick = model::syncPortfolio, enabled = !state.busy) { Text("Обновить у брокера") }
                        TextButton(onClick = { disconnect = true }, enabled = !state.busy) { Text("Отключить счёт") }
                    }
                    else -> {
                        Text("Нужен токен только для чтения выбранного счёта. Он будет передан по HTTPS на сервер OMNICIO и сохранён там в зашифрованном виде. На телефоне токен не сохраняется.")
                        SecretField(credential, { credential = it; model.clearAccounts() }, "Токен Т-Инвестиций")
                        CheckLine("Разрешаю серверу OMNICIO читать данные моего счёта", accepted) { accepted = it }
                        Button(onClick = { model.previewBroker(credential) },
                            enabled = accepted && credential.length >= 20 && !state.busy) { Text("Проверить и выбрать счёт") }
                        state.accounts.forEach { account ->
                            OutlinedButton(onClick = {
                                model.connectBroker(credential, account.id)
                                credential = ""
                            }, enabled = accepted && credential.length >= 20 && !state.busy && account.status == "ACCOUNT_STATUS_OPEN",
                                modifier = Modifier.fillMaxWidth()) { Text(account.name.ifBlank { account.id }) }
                        }
                        LegalLinks()
                    }
                }
            }
        }
        if (section == "Цели") item {
            OmniCard {
                OmniIcon(R.drawable.ic_goal)
                SectionTitle("Цели")
                when {
                    state.workspace == null -> Text("Цели не загружены.")
                    state.amountsHidden -> Text("Суммы целей скрыты. Измените настройку в Портфеле.")
                    state.workspace.goals.isEmpty() -> Text("Сервер не вернул сохранённых целей.")
                    else -> state.workspace.goals.forEach {
                        Text(it.title, style = MaterialTheme.typography.titleMedium)
                        Text(money(it.target))
                        Text(it.date ?: "Срок не указан", style = MaterialTheme.typography.bodySmall)
                    }
                }
                if (connected) OutlinedButton(onClick = { goalForm = !goalForm }, enabled = !state.busy) {
                    Text(if (goalForm) "Закрыть форму" else "Добавить цель")
                }
                if (goalForm && connected) GoalForm(state.busy, model)
            }
        }
        if (section == "Доступ") item {
            OmniCard {
                OmniIcon(R.drawable.ic_shield)
                SectionTitle("Данные и доступ")
                Text("Портфель, история и события хранятся на сервере. Приложение держит полученные ответы только в памяти текущего процесса; офлайн-копий нет.")
                Text("Вход сохраняется в зашифрованном виде на этом устройстве. Выход удаляет сохранённую сессию. Токен брокера хранится только на сервере.")
                Text("Профиль: ${state.publicId ?: "не определён"}", style = MaterialTheme.typography.bodySmall)
                LegalLinks()
                OutlinedButton(onClick = model::logout, enabled = !state.busy) {
                    OmniIcon(R.drawable.ic_logout)
                    Spacer(Modifier.width(8.dp))
                    Text("Выйти из аккаунта")
                }
            }
        }
        if (section == "О приложении") item {
            OmniCard {
                SectionTitle("О приложении")
                Text("OMNICIO ${BuildConfig.VERSION_NAME}")
                Text("Аналитика по официальным источникам. Нет торговых действий и обещаний доходности.", style = MaterialTheme.typography.bodySmall)
                Text("Уведомления вне приложения пока не подключены. События доступны в разделе «Пульс».", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
    if (disconnect) AlertDialog(onDismissRequest = { disconnect = false },
        title = { Text("Отключить счёт?") },
        text = { Text("Сервер удалит сохранённое подключение. Дальнейшее чтение счёта прекратится.") },
        confirmButton = { TextButton(onClick = { disconnect = false; model.disconnectBroker() }) { Text("Отключить") } },
        dismissButton = { TextButton(onClick = { disconnect = false }) { Text("Отмена") } })
}

@Composable
private fun GoalForm(busy: Boolean, model: OmnicioViewModel) {
    var title by remember { mutableStateOf("") }
    var target by remember { mutableStateOf("") }
    var date by remember { mutableStateOf("") }
    var allocation by remember { mutableStateOf("") }
    OutlinedTextField(title, { title = it.take(120) }, label = { Text("Название цели") }, modifier = Modifier.fillMaxWidth())
    OutlinedTextField(target, { target = it }, label = { Text("Целевая сумма, ₽") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), modifier = Modifier.fillMaxWidth())
    OutlinedTextField(date, { date = it }, label = { Text("Дата: ГГГГ-ММ-ДД") }, modifier = Modifier.fillMaxWidth())
    OutlinedTextField(allocation, { allocation = it }, label = { Text("Доля портфеля для цели, %") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), modifier = Modifier.fillMaxWidth())
    Text("Вы задаёте цель самостоятельно. Прогресс рассчитывает сервер по стоимости портфеля; доходность не гарантируется.", style = MaterialTheme.typography.bodySmall)
    Button(onClick = { model.createGoal(title, target, date, allocation) },
        enabled = !busy && title.isNotBlank() && target.isNotBlank() && date.isNotBlank() && allocation.isNotBlank()) {
        Text("Сохранить на сервере")
    }
}

