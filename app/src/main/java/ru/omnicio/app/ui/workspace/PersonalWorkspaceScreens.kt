package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import java.util.UUID
import ru.omnicio.app.data.workspace.VolumeWorkspaceClient
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.BuildConfig

@Composable
fun DevicesWorkspaceScreen(onBack: () -> Unit) {
    val resource = rememberWorkspaceResource("/workspace/devices")
    var chosen by remember { mutableStateOf<JSONObject?>(null) }
    val reauthenticate = LocalReauthenticate.current
    val action = rememberWorkspaceAction { result ->
        if (result.optBoolean("revoked")) {
            if (chosen?.optBoolean("current") == true) reauthenticate()
            chosen = null; resource.refresh()
        }
    }
    WorkspaceDetailPage("Устройства", "Подтверждённые сервером сеансы", onBack, SpectrumSymbol.Profile) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding), contentPadding = PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
            item { WorkspaceRequestState(resource); WorkspaceActionState(action) }
            items(resource.data?.records("items").orEmpty(), key = { it.text("id") }) { device ->
                SpectrumCard {
                    Text(device.text("label", "Устройство"), style = MaterialTheme.typography.titleLarge)
                    if (device.optBoolean("current")) SpectrumBadge("Текущее устройство")
                    Text("Последняя активность: " + localMoment(device.text("last_seen_at", "")))
                    Text("Сеанс до " + localMoment(device.text("expires_at", "")), style = MaterialTheme.typography.bodySmall)
                    SpectrumSecondaryButton("Завершить этот сеанс", { chosen = device }, Modifier.fillMaxWidth(), !action.busy)
                }
            }
        }
    }
    chosen?.let { device -> WorkspaceDialog("Завершить сеанс?", { if (!action.busy) chosen = null }) {
        Text(device.text("label", "Выбранное устройство") + " должно будет войти через Telegram заново. Сервер подтвердит отзыв доступа.")
        SpectrumPrimaryButton("Завершить сеанс", { action.perform("/workspace/devices/" + VolumeWorkspaceClient.encode(device.text("id")), method = "DELETE") },
            Modifier.fillMaxWidth(), !action.busy)
        SpectrumSecondaryButton("Оставить", { chosen = null }, Modifier.fillMaxWidth(), !action.busy)
        WorkspaceActionState(action)
    } }
}

@Composable
fun GoalsWorkspaceScreen(onBack: () -> Unit) {
    val resource = rememberWorkspaceResource("/workspace/goals")
    var editing by remember { mutableStateOf<JSONObject?>(null) }
    var open by rememberSaveable { mutableStateOf(false) }
    var deleting by remember { mutableStateOf<JSONObject?>(null) }
    val action = rememberWorkspaceAction { open = false; deleting = null; resource.refresh() }
    WorkspaceDetailPage("Цели и резерв", "Подтверждённый капитал и ваши планы", onBack, SpectrumSymbol.Goal) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding), contentPadding = PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
            item { WorkspaceRequestState(resource); WorkspaceActionState(action) }
            item { SpectrumPrimaryButton("Добавить цель", { editing = null; open = true }, Modifier.fillMaxWidth(), symbol = SpectrumSymbol.Goal) }
            items(resource.data?.records("items").orEmpty(), key = { it.text("id") }) { goal ->
                SpectrumCard(emphasized = true) {
                    Text(goal.text("title"), style = MaterialTheme.typography.titleLarge)
                    Text(PrivateValue(moneyText(goal.optJSONObject("current"))) + " из " + PrivateValue(moneyText(goal.optJSONObject("target"))))
                    val percent = goal.optString("progress_percent").toFloatOrNull()?.takeIf { it.isFinite() }
                    if (percent != null) SpectrumProgressBar((percent / 100f).coerceIn(0f, 1f))
                    Text("Резерв: " + PrivateValue(moneyText(goal.optJSONObject("reserve"))))
                    Text("Оценка: " + localMoment(goal.text("as_of", "ещё не получена")), style = MaterialTheme.typography.bodySmall)
                    Text("Прогресс учитывает полученный капитал после резерва. Будущие выплаты и прибыль не прибавляются.", style = MaterialTheme.typography.bodySmall)
                    SpectrumSecondaryButton("Изменить цель", { editing = goal; open = true }, Modifier.fillMaxWidth())
                    SpectrumSecondaryButton("Удалить цель", { deleting = goal }, Modifier.fillMaxWidth())
                }
            }
            if (resource.data?.records("items")?.isEmpty() == true) item { WorkspaceEmpty("Выберите первую цель", "Укажите свою сумму и резерв. Приложение покажет прогресс по фактическому капиталу в этой валюте.") }
        }
    }
    if (open) GoalEditor(editing, { open = false }, action)
    deleting?.let { goal -> WorkspaceDialog("Удалить цель?", { deleting = null }) {
        Text(goal.text("title"))
        SpectrumPrimaryButton("Удалить", { action.perform("/workspace/goals/" + VolumeWorkspaceClient.encode(goal.text("id")), method = "DELETE") },
            Modifier.fillMaxWidth(), !action.busy)
        SpectrumSecondaryButton("Оставить", { deleting = null }, Modifier.fillMaxWidth())
        WorkspaceActionState(action)
    } }
}

@Composable
private fun GoalEditor(existing: JSONObject?, close: () -> Unit, action: WorkspaceAction) {
    var title by remember(existing) { mutableStateOf(existing?.text("title", "") ?: "") }
    var amount by remember(existing) { mutableStateOf(existing?.optJSONObject("target")?.text("amount", "") ?: "") }
    var reserve by remember(existing) { mutableStateOf(existing?.optJSONObject("reserve")?.text("amount", "0") ?: "0") }
    var currency by remember(existing) { mutableIntStateOf(listOf("RUB", "USD", "EUR").indexOf(existing?.optJSONObject("target")?.text("currency", "RUB") ?: "RUB").coerceAtLeast(0)) }
    val valid = title.isNotBlank() && amount.toBigDecimalOrNull()?.signum() == 1 && reserve.toBigDecimalOrNull()?.signum()?.let { it >= 0 } == true
    WorkspaceDialog(if (existing == null) "Новая цель" else "Изменить цель", close) {
        WorkspaceTextInput(title, { title = it.take(100) }, "Название", Modifier.fillMaxWidth())
        WorkspaceTextInput(amount, { amount = it.replace(',', '.').take(18) }, "Целевая сумма", Modifier.fillMaxWidth(), keyboard = KeyboardOptions(keyboardType = KeyboardType.Decimal))
        WorkspaceTextInput(reserve, { reserve = it.replace(',', '.').take(18) }, "Сохранить в резерве", Modifier.fillMaxWidth(), keyboard = KeyboardOptions(keyboardType = KeyboardType.Decimal))
        WorkspaceChoices("Валюта", listOf("RUB", "USD", "EUR"), currency) { currency = it }
        SpectrumPrimaryButton("Сохранить цель", {
            val selected = listOf("RUB", "USD", "EUR")[currency]
            action.perform("/workspace/goals", JSONObject().put("request_id", UUID.randomUUID().toString()).put("id", existing?.optString("id") ?: JSONObject.NULL)
                .put("title", title.trim()).put("target", JSONObject().put("amount", amount).put("currency", selected))
                .put("reserve", JSONObject().put("amount", reserve).put("currency", selected)))
        }, Modifier.fillMaxWidth(), valid && !action.busy)
        WorkspaceActionState(action)
    }
}

@Composable
fun RecentWorkspaceScreen(onBack: () -> Unit) {
    val history = LocalWorkspaceHistory.current
    WorkspaceDetailPage("Недавно открыто", "История этого рабочего сеанса", onBack) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding), contentPadding = PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
            if (history.items.isEmpty()) item { WorkspaceEmpty("Разделы появятся здесь", "Открывайте портфель, исследования и настройки — недавние переходы сохранятся в этом сеансе.") }
            items(history.items, key = { it.name }) { route ->
                WorkspaceLink(route.title, "Вернуться к разделу", SpectrumSymbol.Allocation) { history.open(route.name) }
            }
        }
    }
}

@Composable
fun NewFeaturesWorkspaceScreen(onBack: () -> Unit) {
    val navigate = LocalWorkspaceNavigator.current
    WorkspaceDetailPage("Что нового", "Analyst AI " + BuildConfig.VERSION_NAME, onBack, SpectrumSymbol.Update) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding), contentPadding = PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
            item { SpectrumCard(emphasized = true) {
                Text("Ваше новое пространство", style = MaterialTheme.typography.headlineMedium)
                Text("Объёмные материалы, предметные реакции на касание и три уровня движения. Читаемые данные остаются в центре.")
            } }
            item { WorkspaceLink("Подберите оформление", "Светлая тема, яркое освещение и предпросмотр", SpectrumSymbol.Allocation) { navigate(WorkspaceRoute.Appearance) } }
            item { WorkspaceLink("Найдите и сравните", "Общий поиск, наблюдение, фильтры и сравнение", SpectrumSymbol.Portfolio) { navigate(WorkspaceRoute.Discovery) } }
            item { WorkspaceLink("Сохраните исследование", "Источники, дата и ваши заметки", SpectrumSymbol.Sources) { navigate(WorkspaceRoute.Library) } }
            item { WorkspaceLink("Обсудите портфель", "Контекстный чат, основания и контроль расхода", SpectrumSymbol.Analyst) { navigate(WorkspaceRoute.Assistant) } }
            item { WorkspaceLink("Проверьте стратегию", "Влияние, подтверждение и история версий", SpectrumSymbol.Goal) { navigate(WorkspaceRoute.Strategies) } }
            item { WorkspaceLink("Настройте уведомления", "Тихие часы, события и проверка на истории", SpectrumSymbol.Notifications) { navigate(WorkspaceRoute.NotificationSettings) } }
            item { SpectrumSecondaryButton("Продолжить работу", onBack, Modifier.fillMaxWidth()) }
        }
    }
}

@Composable
fun WorkspaceGestureHint(id: String, title: String, detail: String) {
    val context = LocalContext.current
    val store = remember(context) { context.getSharedPreferences("workspace_gestures", 0) }
    var dismissed by remember(id) { mutableStateOf(store.getBoolean(id, false)) }
    if (!dismissed) SpectrumCard {
        Text(title, style = MaterialTheme.typography.titleMedium)
        Text(detail, style = MaterialTheme.typography.bodySmall)
        SpectrumSecondaryButton("Понятно", { dismissed = true; store.edit().putBoolean(id, true).apply() }, Modifier.fillMaxWidth())
    }
}

