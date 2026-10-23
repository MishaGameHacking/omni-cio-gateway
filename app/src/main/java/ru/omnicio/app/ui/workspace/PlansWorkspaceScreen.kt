package ru.omnicio.app.ui.workspace

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID
import ru.omnicio.app.data.workspace.VolumeWorkspaceClient
import ru.omnicio.app.ui.spectrum.*

private const val planResourcePath = "/workspace/plans/"

@Composable
fun PlansWorkspaceScreen(onBack: () -> Unit) {
    val resource = rememberWorkspaceResource("/workspace/plans")
    val rules = rememberWorkspaceResource("/workspace/strategy")
    val refreshPortfolio = LocalPortfolioRefresh.current
    val navigate = LocalWorkspaceNavigator.current
    val context = LocalContext.current
    val foreground = workspaceForeground()
    var editor by rememberSaveable { mutableStateOf(false) }
    var jobId by rememberSaveable { mutableStateOf<String?>(null) }
    var handoff by rememberSaveable { mutableStateOf<String?>(null) }
    var leftApplication by rememberSaveable { mutableStateOf(false) }
    var linkError by remember { mutableStateOf<String?>(null) }
    val mutation = rememberWorkspaceAction { result ->
        result.optString("job_id").takeIf(String::isNotBlank)?.let { jobId = it }
        resource.refresh()
    }
    val create = rememberWorkspaceAction { editor = false; resource.refresh() }
    val open = rememberWorkspaceAction { plan ->
        val uri = validBrokerUri(plan.text("broker_url", ""))
        if (uri == null) linkError = "Ссылка брокера не прошла проверку." else {
            runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, uri)) }
                .onSuccess { handoff = plan.text("id"); leftApplication = false; linkError = null }
                .onFailure { linkError = "Не удалось открыть приложение или сайт брокера. План остаётся неподтверждённым." }
        }
        resource.refresh()
    }
    LaunchedEffect(foreground, handoff) {
        if (!foreground && handoff != null) leftApplication = true
        if (foreground && leftApplication && handoff != null) {
            val identifier = handoff
            handoff = null; leftApplication = false
            refreshPortfolio(); resource.refresh()
            mutation.perform(planResourcePath + VolumeWorkspaceClient.encode(identifier.orEmpty()) + "/reconcile",
                JSONObject().put("request_id", UUID.randomUUID().toString()), job = true, userInitiated = false)
        }
    }
    WorkspaceDetailPage("Действия", "Расчёт, ручной переход и сверка результата", onBack, SpectrumSymbol.Goal) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding).semantics { testTagsAsResourceId = true }.testTag("workspace-content"), contentPadding = PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(workspaceGap)) {
            item { WorkspaceRequestState(resource); WorkspaceActionState(create); WorkspaceActionState(mutation); WorkspaceActionState(open) }
            item { SpectrumCard(emphasized = true) {
                Text("Ваш план действий", style = MaterialTheme.typography.titleLarge)
                Text("Выберите инструмент и количество. Приложение проверит полученные сведения и покажет расчёт; подтверждение торгового поручения происходит у брокера.")
                SpectrumPrimaryButton("Подготовить план", { editor = true }, Modifier.fillMaxWidth(), symbol = SpectrumSymbol.Goal)
                SpectrumSecondaryButton("Выводы аналитика", { navigate(WorkspaceRoute.Reports) }, Modifier.fillMaxWidth())
                SpectrumSecondaryButton("Работа аналитика и расход", { navigate(WorkspaceRoute.AnalysisTimeline) }, Modifier.fillMaxWidth())
            } }
            item { PendingJobRecovery { jobId = it } }
            if (resource.data != null && resource.data.records("items").isEmpty() && !resource.busy) item {
                WorkspaceEmpty("Планов пока нет", "Подготовьте первый расчёт, чтобы затем открыть инструмент у брокера и сверить фактический результат.", "Подготовить план", { editor = true })
            }
            linkError?.let { message -> item { Text(message, color = MaterialTheme.colorScheme.error) } }
            jobId?.let { id -> item { WorkspaceJobPanel(id, { resource.refresh(); refreshPortfolio() }, { jobId = null }) } }
            resource.data?.records("items").orEmpty().forEach { plan -> item(key = plan.text("id")) {
                PlanCard(plan, enabled = !mutation.busy && !open.busy, onOpen = {
                    open.perform(planResourcePath + VolumeWorkspaceClient.encode(plan.text("id")) + "/open-broker",
                        JSONObject().put("request_id", UUID.randomUUID().toString()))
                }, onReconcile = { operationIds ->
                    mutation.perform(planResourcePath + VolumeWorkspaceClient.encode(plan.text("id")) + "/reconcile",
                        JSONObject().put("request_id", UUID.randomUUID().toString()).put("operation_ids", JSONArray(operationIds)), job = true)
                })
            } }
        }
    }
    if (editor) PlanEditor(rules.data?.optJSONObject("active")?.optInt("version") ?: 0, create) { editor = false }
}

@Composable
private fun PlanEditor(strategyVersion: Int, action: WorkspaceAction, close: () -> Unit) {
    val snapshot = LocalPortfolioSnapshot.current
    val accounts = snapshot?.accounts.orEmpty()
    var accountId by rememberSaveable { mutableStateOf(accounts.firstOrNull()?.id.orEmpty()) }
    val accountIds = accounts.map { it.id }
    LaunchedEffect(accountIds) { accountId = initialPlanAccountId(accountId, accountIds) }
    val account = accounts.firstOrNull { it.id == accountId }
    var positionId by rememberSaveable { mutableStateOf("") }
    var quantity by rememberSaveable { mutableStateOf("") }
    var side by rememberSaveable { mutableIntStateOf(0) }
    var search by rememberSaveable { mutableStateOf("") }
    val position = account?.positions?.firstOrNull { it.id == positionId }
    WorkspaceDialog("Подготовить действие", close) {
        if (accounts.isEmpty()) Text("Для расчёта нужен подтверждённый снимок подключённого счёта.") else {
            WorkspaceChoices("Счёт", accounts.map { it.name }, accounts.indexOf(account)) { accountId = accounts[it].id; positionId = "" }
            if (account == null && accountId.isNotBlank()) Text("Ранее выбранный счёт недоступен в этом снимке. Выберите счёт для расчёта.")
            WorkspaceTextInput(search, { search = it.take(100) }, "Найти инструмент на счёте", Modifier.fillMaxWidth(), enabled = !action.busy)
            val found = account?.positions.orEmpty().filter { search.isBlank() || it.title.contains(search, true) || it.ticker?.contains(search, true) == true }
            if (position != null) Text("Выбрано: " + position.title, style = MaterialTheme.typography.titleMedium)
            DetailFold("Выбрать из позиций · " + found.size, initiallyOpen = position == null) {
                found.take(30).forEach { item -> SpectrumSecondaryButton((if (positionId == item.id) "Выбрано · " else "") + item.title,
                    { positionId = item.id }, Modifier.fillMaxWidth(), !action.busy) }
                if (found.size > 30) Text("Показаны первые 30 позиций. Уточните название или тикер в поиске.")
            }
            WorkspaceChoices("Направление", listOf("Купить", "Продать"), side) { side = it }
            WorkspaceTextInput(quantity, { quantity = it.replace(',', '.').take(30) }, "Количество единиц инструмента", Modifier.fillMaxWidth(),
                enabled = !action.busy, keyboard = KeyboardOptions(keyboardType = KeyboardType.Decimal))
            Text("Сервер проверит лот и доступное количество. Цена расчёта берётся из снимка; комиссия и исполнимая котировка проверяются у брокера.")
            SpectrumPrimaryButton("Проверить и сохранить расчёт", {
                action.perform("/workspace/plans", JSONObject().put("request_id", UUID.randomUUID().toString())
                    .put("title", (if (side == 0) "Покупка · " else "Продажа · ") + position?.title.orEmpty())
                    .put("account_id", accountId).put("instrument_uid", positionId).put("quantity", quantity)
                    .put("side", if (side == 0) "buy" else "sell").put("strategy_version", strategyVersion))
            }, Modifier.fillMaxWidth(), !action.busy && position != null && quantity.toBigDecimalOrNull()?.signum() == 1)
        }
        WorkspaceActionState(action)
        SpectrumSecondaryButton("Закрыть", close, Modifier.fillMaxWidth(), !action.busy)
    }
}

/** Initialize only an absent choice; a refreshed snapshot must not redirect a user's plan. */
internal fun initialPlanAccountId(accountId: String, availableIds: List<String>): String =
    accountId.ifBlank { availableIds.firstOrNull().orEmpty() }

@Composable
private fun PlanCard(plan: JSONObject, enabled: Boolean, onOpen: () -> Unit, onReconcile: (List<String>) -> Unit) {
    var selected by rememberSaveable(plan.text("id")) { mutableStateOf(arrayListOf<String>()) }
    val state = plan.text("state", "calculated")
    val candidates = plan.records("candidate_operations")
    val bound = plan.records("bound_operations").map { it.text("id") }.toSet()
    val evidence = LocalEvidenceNavigator.current
    SpectrumCard(emphasized = state == "partial" || state == "obsolete") {
        Text(plan.text("title"), style = MaterialTheme.typography.titleLarge)
        SpectrumBadge(planStateLabel(state))
        Text("План: " + PrivateValue(plan.text("quantity") + " ед. · лот " + plan.text("lot")))
        Text("Сверено по операциям: " + PrivateValue(plan.text("executed_quantity", "0") + " ед."))
        Text("Оценка по снимку: " + PrivateValue(moneyText(plan.optJSONObject("calculation")?.optJSONObject("estimated_value"))))
        Text("Снимок от " + localMoment(plan.text("as_of", "")), style = MaterialTheme.typography.bodySmall)
        Text("Комиссия и возможность исполнения уточняются у брокера. Нажатие кнопки перехода не подтверждает сделку.", style = MaterialTheme.typography.bodySmall)
        SpectrumSecondaryButton("Показать инструмент", { evidence(EvidenceTarget("instrument", plan.text("instrument_uid"))) }, Modifier.fillMaxWidth())
        if (state !in setOf("done", "obsolete")) SpectrumPrimaryButton("Открыть у брокера", onOpen, Modifier.fillMaxWidth(), enabled, SpectrumSymbol.Portfolio)
        if (!plan.isNull("opened_at") && state != "obsolete") SpectrumSecondaryButton("Проверить фактические операции", { onReconcile(emptyList()) }, Modifier.fillMaxWidth(), enabled)
        if (candidates.isNotEmpty()) DetailFold("Найденные операции · " + candidates.size, initiallyOpen = true) {
            Text("Отметьте только уже выполненные операции, которые относятся к этому плану. Сервер заново сверит их и исключит повторное использование.")
            candidates.forEach { operation ->
                val id = operation.text("id")
                if (id in bound) Text("Привязана: " + localMoment(operation.text("date", "")) + " · " + PrivateValue(operation.text("quantity") + " ед."))
                else WorkspaceToggle(localMoment(operation.text("date", "")) + " · " + PrivateValue(operation.text("quantity") + " ед."),
                    PrivateValue(moneyText(operation.optJSONObject("payment"))), id in selected) { checked ->
                    selected = ArrayList(if (checked) selected + id else selected - id)
                }
            }
            SpectrumPrimaryButton("Подтвердить связь выбранных операций", { onReconcile(selected.toList()); selected = arrayListOf() },
                Modifier.fillMaxWidth(), enabled && selected.isNotEmpty())
        }
        if (plan.has("reconciliation_complete") && !plan.optBoolean("reconciliation_complete")) Text("Источник операций пока неполный. Итог исполнения не подтверждён.")
        if (state == "obsolete") Text("Правила изменились. Подготовьте новый расчёт по действующей стратегии.")
        EvidenceLinks(plan.records("sources"))
    }
}

private fun planStateLabel(state: String): String = when (state) {
    "calculated" -> "Расчёт подготовлен"; "open_broker" -> "Переход к брокеру запрошен"; "reconciling" -> "Сверка операций"
    "partial" -> "Подтверждена часть количества"; "done" -> "Количество подтверждено операциями"; "obsolete" -> "Нужен новый расчёт"
    else -> "Ожидаем подтверждение операций"
}

internal fun validBrokerUri(raw: String): Uri? = runCatching { Uri.parse(raw) }.getOrNull()?.takeIf {
    it.scheme == "https" && it.host in setOf("www.tbank.ru", "tbank.ru", "www.tinkoff.ru", "tinkoff.ru") && it.userInfo == null && it.port == -1 &&
        it.path?.startsWith("/invest/") == true
}
