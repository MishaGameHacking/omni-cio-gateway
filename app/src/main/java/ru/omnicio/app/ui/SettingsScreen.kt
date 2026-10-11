package ru.omnicio.app.ui

import androidx.compose.foundation.layout.*
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

@Composable
internal fun SettingsScreen(state: AppUiState, model: OmnicioViewModel) {
    var credential by remember { mutableStateOf("") }
    var accepted by remember { mutableStateOf(false) }
    var disconnect by remember { mutableStateOf(false) }
    var goalForm by remember { mutableStateOf(false) }
    val connected = state.workspace?.connection?.connected == true
    LazyColumn(contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item { AccessSettings(state, model) }
        item { StrategySettings(state, model) }
        item {
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
        item {
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
        item {
            OmniCard {
                OmniIcon(R.drawable.ic_goal)
                SectionTitle("Цели")
                when {
                    state.workspace == null -> Text("Цели не загружены.")
                    state.amountsHidden -> Text("Суммы целей скрыты. Измените настройку на Обзоре.")
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
        item {
            OmniCard {
                OmniIcon(R.drawable.ic_shield)
                SectionTitle("Данные и доступ")
                Text("Портфель, история и события хранятся на сервере. Приложение держит полученные ответы только в памяти текущего процесса; офлайн-копий нет.")
                Text("Токен брокера и сессия не записываются на устройство. Сессия завершается при выходе; после завершения процесса требуется повторный вход.")
                Text("Профиль: ${state.publicId ?: "не определён"}", style = MaterialTheme.typography.bodySmall)
                LegalLinks()
                OutlinedButton(onClick = model::logout, enabled = !state.busy) {
                    OmniIcon(R.drawable.ic_logout)
                    Spacer(Modifier.width(8.dp))
                    Text("Выйти из аккаунта")
                }
            }
        }
        item {
            OmniCard {
                SectionTitle("О приложении")
                Text("OMNICIO ${BuildConfig.VERSION_NAME}")
                Text("Аналитика по официальным источникам. Нет торговых действий и обещаний доходности.", style = MaterialTheme.typography.bodySmall)
                Text("Уведомления вне приложения пока не подключены. События доступны в разделе «Помощник».", style = MaterialTheme.typography.bodySmall)
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
