package ru.omnicio.app.ui.workspace

import android.os.SystemClock
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import kotlinx.coroutines.delay
import ru.omnicio.app.data.workspace.VolumeWorkspaceClient
import ru.omnicio.app.ui.spectrum.*

/** Explicit search and read-only checks; typing and rendering never trigger AI. */
@Composable
internal fun MarketCatalogueScreen(onBack: () -> Unit) {
    val userId = LocalWorkspaceSession.current.userId
    var draft by rememberSaveable(userId) { mutableStateOf("") }
    var query by rememberSaveable(userId) { mutableStateOf("") }
    var kind by rememberSaveable(userId) { mutableIntStateOf(0) }
    var offset by rememberSaveable(userId) { mutableIntStateOf(0) }
    var revision by rememberSaveable(userId) { mutableStateOf<String?>(null) }
    var dossier by rememberSaveable(userId) { mutableStateOf<String?>(null) }
    var candidate by rememberSaveable(userId) { mutableStateOf<String?>(null) }
    val types = listOf("bond", "share", "etf")
    val path = "/workspace/catalogue?kind=${types[kind]}&query=${VolumeWorkspaceClient.encode(query)}&offset=$offset" +
        (revision?.let { "&revision=${VolumeWorkspaceClient.encode(it)}" } ?: "")
    val resource = rememberWorkspaceResource(path)
    WorkspaceDetailPage("Каталог брокера", "Реальные инструменты за пределами вашего портфеля", onBack, SpectrumSymbol.Search,
        adaptToIme = true) { padding ->
        val compact = LocalCompactWorkspaceInput.current
        LazyColumn(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)
            .semantics { testTagsAsResourceId = true }.testTag("workspace-content"),
            contentPadding = PaddingValues(horizontal = 20.dp, vertical = if (compact) 0.dp else 20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item {
                WorkspaceChoices("Тип", listOf("Облигации", "Акции", "Фонды"), kind) {
                    kind = it; offset = 0; revision = null
                }
                SpectrumTextField(draft, { draft = it.take(160) }, Modifier.fillMaxWidth().testTag("catalogue-query"),
                    label = { Text("Тикер, ISIN или название") }, singleLine = true)
                SpectrumPrimaryButton("Найти", { query = draft.trim(); offset = 0; revision = null; resource.refresh() },
                    Modifier.fillMaxWidth(), !resource.busy)
                WorkspaceRequestState(resource)
                Text("Каталог включает недоступные бумаги. Наличие в поиске не означает, что инструмент подходит вам.",
                    style = MaterialTheme.typography.bodySmall)
                resource.data?.let { Text("Найдено: ${it.optInt("total")} · Данные: ${it.text("as_of")}") }
            }
            items(resource.data?.records("items").orEmpty(), key = { it.text("uid") }) { row ->
                SpectrumCard {
                    Text(row.text("name"), style = MaterialTheme.typography.titleMedium)
                    Text("${row.text("ticker")} · ${row.text("isin")} · ${row.text("currency")}")
                    SpectrumSecondaryButton("Досье и источники", { dossier = row.text("uid") }, Modifier.fillMaxWidth())
                    if (types[kind] != "etf") SpectrumSecondaryButton("Проверить покупку", { candidate = row.toString() }, Modifier.fillMaxWidth())
                    else Text("Для подбора фонда требуется подтверждённый состав его активов.", style = MaterialTheme.typography.bodySmall)
                }
            }
            item {
                val data = resource.data
                if (data != null && !data.isNull("next_offset")) SpectrumSecondaryButton("Следующие 30", {
                    revision = data.text("revision"); offset = data.optInt("next_offset")
                }, Modifier.fillMaxWidth(), !resource.busy && resource.error == null)
                if (offset > 0) SpectrumSecondaryButton("К началу списка", { offset = 0; revision = null }, Modifier.fillMaxWidth())
            }
        }
    }
    dossier?.let { uid -> DiscoveryDossier(uid) { dossier = null } }
    candidate?.let { json -> PurchaseCheckDialog(JSONObject(json)) { candidate = null } }
}

@Composable
private fun PurchaseCheckDialog(instrument: JSONObject, close: () -> Unit) {
    val snapshot = LocalPortfolioSnapshot.current
    val accounts = snapshot?.accounts.orEmpty()
    val session = LocalWorkspaceSession.current
    val userId = session.userId
    val uid = instrument.text("uid")
    val rules = rememberWorkspaceResource("/workspace/strategy")
    val version = rules.data?.optJSONObject("active")?.optInt("version") ?: 0
    var accountId by rememberSaveable(userId, uid) { mutableStateOf(accounts.firstOrNull()?.id) }
    val accountIndex = accounts.indexOfFirst { it.id == accountId }
    LaunchedEffect(accounts.map { it.id }) {
        if (accounts.none { it.id == accountId }) accountId = accounts.firstOrNull()?.id
    }
    var lots by rememberSaveable(userId, uid) { mutableStateOf("1") }
    var price by rememberSaveable(userId, uid) { mutableStateOf("") }
    var result by remember { mutableStateOf<JSONObject?>(null) }
    var requestedAt by remember { mutableLongStateOf(0L) }
    val context = listOf(userId, session.token, uid, accountId.orEmpty(), version.toString(), snapshot?.asOf.orEmpty())
    var requestedContext by remember { mutableStateOf<List<String>?>(null) }
    LaunchedEffect(context) { result = null }
    val action = rememberWorkspaceAction { if (requestedContext == context) result = it }
    WorkspaceDialog("Проверить покупку", close) {
        Text(instrument.text("name"), style = MaterialTheme.typography.titleMedium)
        WorkspaceRequestState(rules)
        if (accounts.isNotEmpty()) WorkspaceChoices("Счёт", accounts.map { it.name }, accountIndex.coerceIn(accounts.indices)) {
            if (!action.busy) { accountId = accounts[it].id; result = null }
        }
        SpectrumTextField(lots, { lots = it.take(7); result = null }, Modifier.fillMaxWidth().testTag("purchase-lots"),
            label = { Text("Количество целых лотов") }, enabled = !action.busy)
        val priceLabel = if (instrument.text("instrument_type") == "bond") "Предельная цена, % номинала" else "Предельная цена за единицу"
        SpectrumTextField(price, { price = it.replace(',', '.').take(30); result = null }, Modifier.fillMaxWidth().testTag("purchase-price"),
            label = { Text(priceLabel) }, enabled = !action.busy)
        if (version == 0) Text("Сначала подтвердите стратегию и обновите портфель.")
        SpectrumPrimaryButton("Проверить ограничения", {
            result = null
            requestedContext = context
            requestedAt = SystemClock.elapsedRealtime()
            action.perform("/workspace/purchases/check", JSONObject().put("account_id", accounts[accountIndex].id)
                .put("instrument_uid", instrument.text("uid")).put("lots", lots.toInt())
                .put("limit_price", price).put("strategy_version", version))
        }, Modifier.fillMaxWidth(), !action.busy && accountIndex in accounts.indices && version > 0 &&
            (lots.toIntOrNull() ?: 0) in 1..1_000_000 && price.toBigDecimalOrNull()?.signum() == 1)
        WorkspaceActionState(action)
        result?.let { value -> PurchaseCheckResult(value, requestedAt) }
        Text("Проверка не отправляет заявку. Итоговая пригодность требует полного инвестиционного профиля и обоснования выбора.",
            style = MaterialTheme.typography.bodySmall)
        SpectrumSecondaryButton("Закрыть", close, Modifier.fillMaxWidth(), !action.busy)
    }
}

@Composable
private fun PurchaseCheckResult(value: JSONObject, requestedAt: Long) {
    var observedNow by remember(value) { mutableLongStateOf(SystemClock.elapsedRealtime()) }
    val lifetime = remainingPurchaseCheckMillis(value.text("as_of"), value.text("expires_at"), requestedAt, observedNow)
    LaunchedEffect(value, requestedAt) {
        while (true) {
            observedNow = SystemClock.elapsedRealtime()
            val remaining = remainingPurchaseCheckMillis(value.text("as_of"), value.text("expires_at"), requestedAt, observedNow)
            if (remaining == 0L) break
            delay(minOf(remaining, 1_000L))
        }
    }
    Text(if (lifetime == 0L) "Срок проверки истёк — повторите расчёт"
        else if (value.optBoolean("constraints_passed")) "Проверенные ограничения соблюдены" else "Покупка не прошла проверку",
        style = MaterialTheme.typography.titleMedium)
    value.optJSONObject("total_cost")?.let { Text(PrivateValue("Оценка брокера: ${it.text("amount")} ${it.text("currency")}")) }
    value.optJSONObject("cash_after")?.let { Text(PrivateValue("Собственные деньги после покупки: ${it.text("amount")} ${it.text("currency")}")) }
    DetailFold("Влияние на ограничения портфеля") {
        Text("Верхняя оценка долей учитывает полную стоимость покупки. Резерв защищается целиком на выбранном счёте.",
            style = MaterialTheme.typography.bodySmall)
        value.records("concentrations").forEach { row ->
            val label = when (row.text("axis")) {
                "position" -> "Позиция"
                "issuer" -> "Эмитент"
                "group" -> "Группа компаний"
                "sector" -> "Сектор"
                else -> "Валюта"
            }
            val share = row.text("share_upper_bound_percent").toBigDecimalOrNull()
                ?.setScale(2, java.math.RoundingMode.CEILING)?.toPlainString() ?: "нет данных"
            Text(PrivateValue("$label: до $share% · лимит ${row.text("limit_percent")}%"))
        }
    }
    value.strings("reasons").forEach { Text(purchaseReason(it), color = MaterialTheme.colorScheme.error) }
    Text("Актуально до ${value.text("expires_at")}. После изменения данных проверку нужно повторить.", style = MaterialTheme.typography.bodySmall)
    Text("Расчёт сохранён: ${value.text("check_id")}", style = MaterialTheme.typography.bodySmall)
}

private fun purchaseReason(code: String): String = when {
    code.contains("rating") -> "Кредитные рейтинги отсутствуют, конфликтуют или не соответствуют ограничениям."
    code.contains("identity") || code.contains("unknown") -> "Не подтверждены компания, группа или свойства актива."
    code.contains("reserve") -> "Покупка затрагивает защищённый резерв."
    code.contains("money") || code.contains("cost") -> "Недостаточно собственных денег либо стоимость не подтверждена."
    code.contains("limit_exceeded") -> "Покупка превысит подтверждённые ограничения концентрации."
    code.contains("fresh") || code.contains("stale") -> "Обновите портфель и рыночные данные."
    code.contains("liquidity") -> "По выбранной цене недостаточно видимых предложений."
    code.contains("qualification") || code.contains("tests") -> "Брокер не подтвердил необходимые права или тестирование."
    code.contains("currency") -> "Не подтверждён расчёт в общей валюте."
    code.contains("price_step") -> "Цена не соответствует шагу котировки либо шаг неизвестен."
    else -> "Не все обязательные условия покупки подтверждены. Проверьте досье и данные брокера."
}
