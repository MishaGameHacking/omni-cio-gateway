package ru.omnicio.app.ui.home

import ru.omnicio.app.ui.spectrum.SpectrumActionButton as TextButton

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.data.market.*
import ru.omnicio.app.data.market.records
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.data.workspace.PersonalWorkspaceController
import ru.omnicio.app.ui.portfolio.*
import ru.omnicio.app.ui.spectrum.*
import ru.omnicio.app.ui.workspace.*
import java.math.BigDecimal
import java.time.LocalDate

/** A deterministic fingerprint excludes collection time; a successful fetch may contain no new values. */
internal fun homeSnapshotCapture(snapshot: PortfolioSnapshot): JSONObject = JSONObject()
    .put("as_of", snapshot.asOf).put("currency", snapshot.totalValue.currency)
    .put("total", snapshot.totalValue.value.toBigDecimal().toPlainString())
    .put("positions", JSONArray(snapshot.accounts.sortedBy { it.id }.flatMap { account ->
        account.positions.sortedBy { it.id }.map { position ->
            JSONObject().put("key", "${account.id}:${position.id}").put("uid", position.id)
                .put("title", position.title).put("account", account.name)
                .put("quantity", position.quantity?.toBigDecimal()?.toPlainString())
                .put("value", position.currentValue?.value?.toBigDecimal()?.toPlainString())
                .put("currency", position.currentValue?.currency).put("blocked", position.blocked)
        }
    }))

internal fun financialFingerprint(snapshot: PortfolioSnapshot?): String? = snapshot?.let {
    homeSnapshotCapture(it).apply { remove("as_of") }.toString()
}

@Composable
internal fun CapitalComposition(snapshot: PortfolioSnapshot, workspace: JSONObject?) {
    SpectrumCard {
        Text("Из чего состоит капитал", style = MaterialTheme.typography.titleLarge)
        val groups = snapshot.accounts.flatMap { it.positions }.groupBy { position -> when {
            position.blocked -> "С ограничениями"
            position.instrumentType in setOf("cash", "currency") -> "Денежный остаток"
            else -> "Вложено в инструменты"
        } }
        listOf("Вложено в инструменты", "Денежный остаток", "С ограничениями").forEach { title ->
            val positions = groups[title].orEmpty()
            val values = positions.mapNotNull { it.currentValue }.groupBy { it.currency }
            if (values.isEmpty()) DataRow(title, if (positions.isEmpty()) "Нет позиций в этой группе" else "Оценка не получена")
            values.forEach { (currency, amounts) -> DataRow(title,
                PrivateValue("${decimalText(amounts.sumOf { it.value.toBigDecimal() })} ${currencySymbol(currency)}")) }
            if (positions.any { it.currentValue == null }) Notice("$title: ${positions.count { it.currentValue == null }} без оценки.")
        }
        Notice("Каждая позиция учтена в одной группе. Денежный остаток не является лимитом покупки или вывода. Частично заблокированная позиция показана целиком в группе ограничений.")
        val capital = workspace?.section("capital")
        if (capital != null) DetailFold("Сверка с сервером и ограничения") {
            WorkspaceSectionNotice(capital)
            val data = capital.optJSONObject("data")
            DataRow("Общий капитал сервера", workspaceMoney(data?.optJSONObject("total")))
            data?.optInt("blocked_positions_count")?.let { DataRow("Позиций с ограничениями", it.toString()) }
            data?.optInt("unvalued_positions_count")?.let { DataRow("Без оценки", it.toString()) }
            SourceProvenance(capital.records("sources"))
        }
    }
}

@Composable
internal fun HomeAttribution(workspace: JSONObject?, period: PortfolioPeriod, onPeriod: (PortfolioPeriod) -> Unit) {
    SpectrumCard {
        Text("Почему изменилась сумма", style = MaterialTheme.typography.titleLarge)
        PeriodControls(period, onPeriod)
        val section = workspace?.section("attribution")
        WorkspaceSectionNotice(section)
        section?.optJSONObject("data")?.let { data ->
            DataRow("Начальная оценка", workspaceMoney(data.optJSONObject("opening_value")))
            DataRow("Конечная оценка", workspaceMoney(data.optJSONObject("closing_value")))
            DataRow("Изменение стоимости", workspaceMoney(data.optJSONObject("change")))
            DataRow("Внешние пополнения и выводы", workspaceMoney(data.optJSONObject("external_net_flow")))
            DataRow("Остаток после внешних потоков", workspaceMoney(data.optJSONObject("residual_after_external_flows")))
            Notice(data.optionalText("explanation") ?: "Изменение баланса само по себе не определяет инвестиционную прибыль.")
            if (!data.optBoolean("complete")) Notice("Разложение неполное. Неизвестные части не заменены нулём.")
            if (data.isNull("fx_component")) Notice("Отдельный валютный вклад не подтверждён источником.")
            DetailFold("Полученные денежные потоки") {
                data.records("flows").forEach { DataRow(categoryTitle(it.optString("category")), workspaceMoney(it.optJSONObject("amount"))) }
                SourceProvenance(section.records("sources"))
            }
        }
    }
}

@Composable
internal fun HomePayoutTimeline(workspace: JSONObject?, onAll: () -> Unit) {
    val destination = LocalPortfolioDestination.current
    SpectrumCard {
        Text("Лента выплат", style = MaterialTheme.typography.titleLarge)
        val section = workspace?.section("payouts")
        WorkspaceSectionNotice(section)
        val rows = section?.optJSONObject("data")?.records("items").orEmpty()
            .sortedBy { it.optionalText("date") ?: "9999" }
        val today = LocalDate.now().toString()
        val future = rows.filter { (it.optionalText("date") ?: "9999") >= today }
        val visible = (future + rows.filterNot(future::contains).asReversed()).take(5)
        visible.forEach { row ->
            val status = when (row.optString("status")) {
                "announced" -> "Объявлена"; "expected" -> "Ожидается"; "received" -> "Получена"; else -> "Статус не подтверждён"
            }
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(row.optionalText("title") ?: "Событие выплаты", style = MaterialTheme.typography.titleMedium)
                DataRow("${row.optionalText("date") ?: "Дата не получена"} · $status", workspaceMoney(row.optJSONObject("amount")))
                if (row.optBoolean("eligibility_unknown")) Notice("Право на выплату не подтверждено.")
                row.optionalText("instrument_uid")?.let { uid -> TextButton(onClick = {
                    destination(PortfolioDestination(query = uid, accountId = row.optionalText("account_id")))
                }) { Text("Открыть связанную позицию") } }
            }
        }
        if (rows.isEmpty() && section?.optString("state") == "available") Notice("В полученном календаре нет событий.")
        TextButton(onClick = onAll) { Text("Календарь и все выплаты") }
        SourceProvenance(workspace?.records("sources").orEmpty(), visible.flatMap { it.stringList("source_ids") })
    }
}

@Composable
internal fun HomeGoalProgress(workspace: JSONObject?) {
    val navigate = LocalWorkspaceNavigator.current
    SpectrumCard {
        Text("Цель и резерв", style = MaterialTheme.typography.titleLarge)
        val section = workspace?.section("goals")
        WorkspaceSectionNotice(section, "Создайте цель и резерв, чтобы видеть прогресс по данным портфеля.")
        section?.optJSONObject("data")?.records("items")?.forEach { goal ->
            Text(goal.optionalText("title") ?: "Моя цель", style = MaterialTheme.typography.titleMedium)
            DataRow("Цель", workspaceMoney(goal.optJSONObject("target")))
            DataRow("Отдельный резерв", workspaceMoney(goal.optJSONObject("reserve")))
            DataRow("Текущая оценка", workspaceMoney(goal.optJSONObject("current")))
            val percent = goal.optionalText("progress_percent")?.toBigDecimalOrNull()
            if (percent != null && !LocalWorkspacePreferences.current.value.hideHomeBalance) {
                SpectrumProgressBar(percent.toFloat().div(100f).coerceIn(0f, 1f))
                Text("${decimalText(percent)}% · фактическая оценка")
            }
        }
        TextButton(onClick = { navigate(WorkspaceRoute.Goals) }) { Text("Настроить цель и резерв") }
    }
}

@Composable
internal fun ChangesSinceVisit(snapshot: PortfolioSnapshot, personal: PersonalWorkspaceController) {
    val user = LocalWorkspaceSession.current.userId
    // Save only the visit identity across recreation. The financial baseline is
    // resolved from the encrypted store, not serialized into Activity state.
    var baselineVisit by rememberSaveable(user) { mutableStateOf<String?>(null) }
    var initialized by rememberSaveable(user) { mutableStateOf(false) }
    LaunchedEffect(personal.loaded, user) {
        if (personal.loaded && !initialized) {
            baselineVisit = personal.data.optionalText("current_visit")
            initialized = true
            personal.checkpointVisit(homeSnapshotCapture(snapshot))
        }
    }
    val baseline = when (baselineVisit) {
        null -> null
        personal.data.optionalText("current_visit") -> personal.data.optJSONObject("current_snapshot")
        personal.data.optionalText("previous_visit") -> personal.data.optJSONObject("previous_snapshot")
        else -> null
    }
    val current = homeSnapshotCapture(snapshot)
    val oldRows = baseline?.records("positions").orEmpty().associateBy { it.optString("key") }
    val nowRows = current.records("positions").associateBy { it.optString("key") }
    val changes = (oldRows.keys + nowRows.keys).mapNotNull { key ->
        val old = oldRows[key]; val now = nowRows[key]
        when {
            old == null -> now?.let { "${it.optString("title")} · появилась в ${it.optString("account")}" }
            now == null -> "${old.optString("title")} · отсутствует в текущем снимке"
            old.optionalText("quantity") != now.optionalText("quantity") -> "${now.optString("title")} · изменилось количество"
            old.optBoolean("blocked") != now.optBoolean("blocked") -> "${now.optString("title")} · изменились ограничения"
            old.optionalText("value") != now.optionalText("value") || old.optionalText("currency") != now.optionalText("currency") -> "${now.optString("title")} · изменилась оценка"
            else -> null
        }
    }
    SpectrumCard {
        Text("С прошлого посещения", style = MaterialTheme.typography.titleLarge)
        if (!initialized) Text("Читаем сохранённую точку сравнения…")
        else if (baselineVisit == null) Text("Первая точка сравнения сохранена. При следующем посещении появятся фактические изменения.")
        else if (baseline == null) Text("Исходная точка сравнения недоступна. Текущий снимок не подставлен вместо прежнего.")
        else {
            Notice("Сравниваем снимки ${baseline.optionalText("as_of") ?: baselineVisit ?: "без времени"} и ${snapshot.asOf ?: "без времени"}.")
            val before = baseline?.optionalText("total")?.toBigDecimalOrNull()
            val sameCurrency = baseline?.optionalText("currency") == snapshot.totalValue.currency
            if (before != null && sameCurrency) DataRow("Изменение общей оценки", PrivateValue(
                "${decimalText(snapshot.totalValue.value.toBigDecimal() - before)} ${currencySymbol(snapshot.totalValue.currency)}"))
            else Notice("Общую сумму нельзя сравнить: оценки в разных валютах или первая сумма неизвестна.")
            if (changes.isEmpty()) Text("Изменений состава, количества, оценок и ограничений не обнаружено.")
            changes.take(4).forEach { Text(it) }
            if (changes.size > 4) DetailFold("Все изменения (${changes.size})") { changes.drop(4).forEach { Text(it) } }
            Notice("Разница снимков не доказывает сделку, выплату или причину движения цены.")
        }
    }
}
