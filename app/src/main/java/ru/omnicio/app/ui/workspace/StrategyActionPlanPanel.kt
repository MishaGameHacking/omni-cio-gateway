package ru.omnicio.app.ui.workspace

import androidx.activity.compose.LocalActivity
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp
import java.time.Instant
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import org.json.JSONObject
import androidx.compose.runtime.saveable.rememberSaveable
import ru.omnicio.app.ui.spectrum.*

@Composable
internal fun StrategyActionPlanPanel() {
    val resource = rememberWorkspaceResource("/automation/strategy-plan")
    var jobId by rememberSaveable { mutableStateOf<String?>(null) }
    val job = rememberWorkspaceResource("/workspace/jobs/" + (jobId ?: "none"), enabled = jobId != null)
    val refresh = rememberWorkspaceAction { reply -> jobId = reply.optString("job_id").takeIf { it.isNotBlank() } }
    val foreground = workspaceForeground()
    val state = job.data?.optString("state")
    LaunchedEffect(jobId, foreground, job.data) {
        if (jobId == null || !foreground) return@LaunchedEffect
        if (state in setOf("completed", "failed", "cancelled", "uncertain")) {
            resource.refresh()
        } else {
            delay(2_000)
            job.refresh()
        }
    }
    val running = jobId != null && state !in setOf("completed", "failed", "cancelled", "uncertain")
    val activity = LocalActivity.current
    val browser = LocalUriHandler.current
    var browserFallback by remember { mutableStateOf<String?>(null) }
    var message by remember { mutableStateOf<String?>(null) }
    val now by produceState(Instant.now()) { while(isActive) { value = Instant.now(); delay(5_000) } }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        WorkspaceRequestState(resource)
        Text("Следующий шаг по портфелю", style = MaterialTheme.typography.titleLarge)
        Text("Количество рассчитывает сервер по подтверждённым остаткам, целевым долям и свежему стакану.", style = MaterialTheme.typography.bodyMedium)
        val actions = resource.data?.records("actions").orEmpty()
        if (actions.isEmpty()) SpectrumCard {
            Text("Пока без операции", style = MaterialTheme.typography.titleMedium)
            Text("Ожидаем свежий расчёт или недостающие сведения. Увеличивать риск, чтобы заполнить план, система не будет.")
        }
        actions.forEach { row ->
            val expires = runCatching { Instant.parse(row.optString("expires_at")) }.getOrNull()
            val current = expires?.isAfter(now) == true
            val sell = row.optString("action") == "sell"
            SpectrumCard(emphasized = current) {
                SpectrumBadge(if (current) "Расчёт по стратегии" else "Нужен новый расчёт")
                Text(row.text("name"), style = MaterialTheme.typography.titleLarge)
                Text(row.text("ticker"))
                Text(PrivateValue((if (sell) "Продать " else "Докупить ") + row.optInt("suggested_lots") + " лот. · " + row.text("quantity", "—") + " шт."),
                    style = MaterialTheme.typography.titleMedium)
                Text(PrivateValue(moneyText(row.optJSONObject("total_cost"))))
                Text(row.text("explanation"))
                Text("Цена проверена: " + localMoment(row.text("as_of")), style = MaterialTheme.typography.bodySmall)
                val url = row.text("broker_url", "")
                SpectrumPrimaryButton("Открыть актив в Т‑Инвестициях", {
                    if (expires?.isAfter(Instant.now()) == true && activity != null) {
                        when(openInstrumentInApp(activity, url)) {
                            BrokerOpenResult.NoAppHandler -> browserFallback = url
                            BrokerOpenResult.InvalidLink -> message = "Ссылка инструмента не прошла проверку."
                            BrokerOpenResult.AppHandlerOpened -> message = "Проверьте цену и количество у брокера. Переход не отправляет заявку."
                        }
                    }
                }, Modifier.fillMaxWidth(), enabled = current && url.isNotBlank() && activity != null)
                Text("Налоги зависят от счёта и вашей ситуации. Итоговые условия показывает брокер перед покупкой или продажей.", style = MaterialTheme.typography.bodySmall)
            }
        }
        StrategyPendingRows(resource.data?.records("pending").orEmpty())
        message?.let { Text(it) }
        WorkspaceRequestState(job)
        refresh.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        if (running) Text("Обновляем остатки и котировки, затем рассчитываем план…")
        if (state == "failed") Text("Расчёт не завершён. Проверьте подключение и повторите обновление.")
        SpectrumSecondaryButton(if (running) "Расчёт выполняется" else "Обновить цены и план", {
            jobId = null
            refresh.perform("/workspace/refresh", JSONObject().put("currency", "RUB").put("strategy_plan", true), job = true)
        }, Modifier.fillMaxWidth(), enabled = !running && !refresh.busy && !refresh.ambiguous)
        Text("После операции следующий шаг появится по обновлённому портфелю. Расчёты не используют платный ИИ.", style = MaterialTheme.typography.bodySmall)
    }
    browserFallback?.let { url -> WorkspaceDialog("Открыть карточку в браузере?", { browserFallback = null }) {
        Text("На этом устройстве нет приложения, принимающего проверенную ссылку актива. Можно открыть ту же карточку на сайте Т‑Банка.")
        SpectrumPrimaryButton("Открыть карточку", { browser.openUri(url); browserFallback = null })
        SpectrumSecondaryButton("Отмена", { browserFallback = null })
    } }
}

@Composable
private fun StrategyPendingRows(pending: List<JSONObject>) {
    if (pending.isNotEmpty()) DetailFold("Ожидают проверки · ${pending.size}") {
        pending.take(8).forEach { row ->
            Text(row.text("name"), style = MaterialTheme.typography.titleMedium)
            val message = if ((row.optJSONArray("missing_evidence")?.length() ?: 0) > 0)
                strategyWaitingMessage(row)
            else "Котировка или данные портфеля требуют обновления."
            Text(message, style = MaterialTheme.typography.bodySmall)
        }
    }
}

private fun strategyWaitingMessage(row: JSONObject): String {
    val reasons = row.optJSONArray("missing_evidence")
    val code = reasons?.optString(0).orEmpty()
    return when (code) {
        "loss_capacity_not_confirmed", "income_stability_unknown" -> "Укажите финансовую устойчивость в настройках стратегии."
        "no_whole_lot_within_target_and_reserve", "no_whole_lot_reduction" -> "Целый лот не помещается в свободный бюджет и лимиты."
        "strategy_operation_window_incomplete", "strategy_operation_window_stale" -> "Нужно обновить историю операций для проверки повторных сделок."
        "strategy_rebalance_cooldown", "strategy_turnover_limit" -> "Система ограничивает частые перестроения и расходы."
        "reinvestment_disabled_new_buys_paused" -> "Новые покупки приостановлены в настройках."
        "bond_maturity_outside_horizon" -> "Срок погашения не соответствует вашему горизонту."
        "instrument_lot_changed_refresh_required" -> "Брокер изменил размер лота; нужен новый расчёт."
        else -> "Не выполнены все условия стратегии. Актив не включён в план."
    }
}
