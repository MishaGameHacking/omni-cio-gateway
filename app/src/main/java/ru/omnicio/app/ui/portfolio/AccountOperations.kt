package ru.omnicio.app.ui.portfolio

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import ru.omnicio.app.data.backend.BackendResult
import ru.omnicio.app.data.portfolio.*

internal val OperationCategories = listOf("all" to "Все", "trades" to "Сделки", "fees" to "Комиссии", "tax" to "Налоги",
    "margin" to "Вармаржа", "redemptions" to "Погашения", "income" to "Дивиденды и купоны",
    "deposits" to "Пополнения", "withdrawals" to "Выводы", "other" to "Другое")
internal fun categoryTitle(category: String): String = when (category) {
    "dividends" -> "Дивиденды"; "coupons" -> "Купоны"
    else -> OperationCategories.firstOrNull { it.first == category }?.second ?: category
}

@Composable
internal fun AccountOperations(token: String, account: PortfolioAccount) {
    var start by rememberSaveable(account.id) { mutableStateOf<String?>(null) }
    var end by rememberSaveable(account.id) { mutableStateOf<String?>(null) }
    var category by rememberSaveable(account.id) { mutableIntStateOf(0) }
    val period = PortfolioPeriod(start, end)
    val request = rememberAccountData(token, account.id, "operations", period.parameters())
    var items by remember(token, account.id, period) { mutableStateOf<List<JSONObject>>(emptyList()) }
    var next by remember(token, account.id, period) { mutableStateOf<String?>(null) }
    var loadedOlder by remember(token, account.id, period) { mutableStateOf(false) }
    var pageError by remember(token, account.id, period) { mutableStateOf<String?>(null) }
    var chosen by remember { mutableStateOf<JSONObject?>(null) }
    LaunchedEffect(request.json) {
        request.json?.let { data ->
            val first = data.objects("items")
            items = (first + items).distinctBy { it.optString("id") }.sortedByDescending { it.optString("date") }
            if (!loadedOlder) next = data.optString("nextCursor").takeIf { data.optBoolean("hasNext") && it.isNotBlank() }
        }
    }
    val key = OperationCategories[category].first
    val visible = items.filter { key == "all" || it.optString("category") == key ||
        (key == "income" && it.optString("category") in setOf("dividends", "coupons")) }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item(key = "range") {
            PeriodControls(period) { start = it.start; end = it.end }
            ChoiceRow(OperationCategories.map { it.second }, category) { category = it }
            AccountDataNotice(request)
        }
        var previousDay = ""
        visible.forEach { operation ->
            val day = dateText(operation.nullableText("date"), "d MMMM yyyy")
            if (day != previousDay) {
                item(key = "day:$day") { Text(day, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 10.dp)) }
                previousDay = day
            }
            item(key = "operation:${operation.optString("id")}") {
                Card(onClick = { chosen = operation }, colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
                    Row(Modifier.fillMaxWidth().padding(14.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Column(Modifier.weight(1f)) {
                            Text(operation.optString("title").ifBlank { categoryTitle(operation.optString("category")) }, fontWeight = FontWeight.Medium)
                            Notice(account.name)
                            if (operation.optString("state") != "OPERATION_STATE_EXECUTED") Notice("${operation.optString("state")}")
                        }
                        SignedAmount(operation.money("payment"))
                    }
                }
            }
        }
        if (visible.isEmpty() && request.json != null && next == null) item { Notice("Операций за выбранный период и категорию нет.") }
        if (next != null && items.size < 10_000 && pageError == null) {
            val cursor = next!!
            item(key = "load:$cursor") {
                Notice("Загружаем следующие операции…")
                LaunchedEffect(cursor) {
                    val response = withContext(Dispatchers.IO) { PortfolioDataClient().details(token, account.id, "operations", period.parameters() + ("cursor" to cursor)) }
                    when (response) {
                        is BackendResult.Failure -> pageError = response.message
                        is BackendResult.Success -> {
                            val data = response.value
                            items = (items + data.objects("items")).distinctBy { it.optString("id") }.sortedByDescending { it.optString("date") }
                            loadedOlder = true
                            val after = data.optString("nextCursor")
                            next = after.takeIf { data.optBoolean("hasNext") && it.isNotBlank() && it != cursor }
                            if (data.optBoolean("hasNext") && next == null) pageError = "Брокер не вернул следующий курсор. История загружена не полностью."
                        }
                    }
                }
            }
        }
        if (pageError != null) item {
            Notice("${pageError}. Загружена только часть истории.")
            TextButton(onClick = { pageError = null }) { Text("Продолжить загрузку истории") }
        }
        if (items.size >= 10_000 && next != null) item { Notice("Показаны первые 10 000 операций. Сузьте период, чтобы увидеть оставшиеся.") }
    }
    chosen?.let { operation ->
        AlertDialog(onDismissRequest = { chosen = null }, title = { Text(operation.optString("title")) },
            text = { Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                DataRow("Дата, Москва", dateText(operation.nullableText("date")))
                DataRow("Сумма", operation.money("payment").moneyText(true))
                DataRow("Цена", operation.money("price").moneyText())
                DataRow("Количество", operation.nullableText("quantity") ?: "—")
                DataRow("Комиссия", operation.money("commission").moneyText())
                DataRow("Результат операции", operation.money("yield").moneyText(true))
                DataRow("Тип API", operation.optString("type"))
                DataRow("Статус API", operation.optString("state"))
                DataRow("ID", operation.optString("id"))
                Notice(operation.nullableText("description") ?: "")
            } }, confirmButton = { TextButton(onClick = { chosen = null }) { Text("Закрыть") } })
    }
}

@Composable
internal fun AccountOrders(token: String, account: PortfolioAccount) {
    val request = rememberAccountData(token, account.id, "orders", interval = 15_000)
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { AccountDataNotice(request); Notice("Только просмотр. Изменение и отмена заявок — в приложении брокера.") }
        request.json?.let { data ->
            listOf("orders" to "Активные заявки", "stopOrders" to "Стоп-заявки").forEach { (field, title) ->
                val block = data.optJSONObject(field)
                item(key = "heading:$field") { SectionHeading(title) }
                if (block?.optBoolean("available") != true) {
                    item(key = "unavailable:$field") { Notice("Не удалось получить этот раздел: ${block?.optString("reason") ?: "нет ответа"}. Это не означает, что заявок нет.") }
                } else {
                    val rows = block.optJSONObject("data")?.objects(field) ?: emptyList()
                    if (rows.isEmpty()) item(key = "empty:$field") { Notice("${title}: отсутствуют") }
                    items(rows, key = { "$field:${it.optString("orderId", it.optString("stopOrderId"))}" }) { row ->
                        OrderCard(row, field == "stopOrders", account)
                    }
                }
            }
            item(key = "limits") {
                CompactCard {
                    SectionHeading("Деньги и ограничения вывода")
                    val block = data.optJSONObject("withdrawLimits")
                    if (block?.optBoolean("available") != true) Notice("Лимиты недоступны; проверьте права токена или дождитесь обновления брокера.")
                    else {
                        val raw = block.optJSONObject("data") ?: JSONObject()
                        listOf("money" to "Остаток для вывода", "blocked" to "Заблокировано", "blockedGuarantee" to "Гарантийное обеспечение").forEach { (field, title) ->
                            val values = raw.objects(field)
                            if (values.isEmpty()) DataRow(title, "Нет значений в ответе API")
                            else values.forEach { DataRow(title, brokerMoney(it).moneyText()) }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun OrderCard(row: JSONObject, stop: Boolean, account: PortfolioAccount) {
    CompactCard {
        val uid = row.optString("instrumentUid", row.optString("figi"))
        val position = account.positions.firstOrNull { it.id == uid }
        Text(position?.title ?: row.optString("figi", uid), fontWeight = FontWeight.Bold)
        DataRow("Направление", if (row.optString("direction").endsWith("BUY")) "Покупка" else if (row.optString("direction").endsWith("SELL")) "Продажа" else row.optString("direction"))
        DataRow("Лотов", row.optString("lotsRequested"))
        if (!stop) DataRow("Исполнено лотов", row.optString("lotsExecuted"))
        DataRow("Цена", brokerMoney(row.optJSONObject(if (stop) "price" else "initialSecurityPrice")).moneyText())
        if (stop) DataRow("Стоп-цена", brokerMoney(row.optJSONObject("stopPrice")).moneyText())
        DataRow("Создана", dateText(row.nullableText(if (stop) "createDate" else "orderDate")))
        DataRow("Статус / тип API", row.optString(if (stop) "orderType" else "executionReportStatus"))
    }
}
