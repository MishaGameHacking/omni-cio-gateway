package ru.omnicio.app.ui.workspace

import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import ru.omnicio.app.ui.spatial.SpatialIcon
import ru.omnicio.app.ui.spectrum.SpectrumSecondaryButton

internal const val eventImpactQuestion = "Как это событие может повлиять на мои позиции?"

/** Facts and destinations come from the server's owned evidence; channels remain interpretations. */
@Composable
internal fun ImpactHypothesisPanel(hypothesis: JSONObject) {
    if (hypothesis.text("kind", "") != "hypothesis") {
        Text("Формат разбора события не подтверждён. Обновите диалог, чтобы проверить сохранённый результат.")
        return
    }
    val sources = hypothesis.records("sources")
    Column(Modifier.fillMaxWidth().testTag("assistant-impact"), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            SpatialIcon("analyst", Modifier.size(40.dp))
            Text("Гипотеза влияния ИИ", Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
        }
        Text("Возможный механизм, предпосылки и неопределённость. Причинное влияние на цену не установлено.",
            style = MaterialTheme.typography.bodyMedium)
        hypothesis.text("as_of", "").takeIf(String::isNotBlank)?.let {
            Text("Позиции в снимке от " + localMoment(it), style = MaterialTheme.typography.bodySmall)
        }
        DetailFold("Публикация, компания и мои позиции", headerModifier = Modifier.testTag("assistant-impact-basis")) {
            ImpactEvent(hypothesis.optJSONObject("event"), sources)
            hypothesis.records("companies").forEach { ImpactCompany(it, sources) }
            hypothesis.records("positions").forEach { ImpactPosition(it, sources) }
        }
        hypothesis.records("channels").forEachIndexed { index, channel ->
            ImpactChannel(index, channel, sources)
        }
        DetailFold("Ограничения разбора") {
            hypothesis.strings("limitations").forEach { Text(it) }
            Text("Денежный эффект и доходность не рассчитаны. Разбор не создаёт торговое поручение.")
        }
    }
}

@Composable
private fun ImpactEvent(event: JSONObject?, sources: List<JSONObject>) {
    if (event == null) {
        Text("Данные выбранной публикации не сохранены.")
        return
    }
    Text("Публикация", style = MaterialTheme.typography.titleSmall)
    Text(event.text("title", "Название не получено"))
    Text(localMoment(event.text("published_at", "Дата публикации не получена")), style = MaterialTheme.typography.bodySmall)
    if (!event.optBoolean("event_identity_verified")) {
        Text("Общая идентичность события ещё не подтверждена; используется конкретная публикация.", style = MaterialTheme.typography.bodySmall)
    }
    if (!event.optBoolean("primary_source_verified")) {
        Text("Первоисточник публикации не установлен.", style = MaterialTheme.typography.bodySmall)
    }
    ImpactSources(event, sources)
}

@Composable
private fun ImpactCompany(company: JSONObject, sources: List<JSONObject>) {
    Text("Компания", style = MaterialTheme.typography.titleSmall)
    if (company.text("identity_state", "") == "verified") {
        Text(company.text("issuer_name", company.text("issuer_id", "Эмитент")))
        ImpactSources(company, sources)
    } else {
        Text("Эмитент не подтверждён. Связь новости относится к инструменту, а сведения о компании требуют проверки.")
    }
}

@Composable
private fun ImpactPosition(position: JSONObject, sources: List<JSONObject>) {
    val navigate = LocalEvidenceNavigator.current
    val uid = position.text("instrument_uid", "")
    val account = position.text("account_id", "")
    Text("Моя позиция · " + position.text("account_name", "Счёт"), style = MaterialTheme.typography.titleSmall)
    position.text("quantity", "").takeIf(String::isNotBlank)?.let { Text("Количество: " + PrivateValue(it)) }
    Text("Оценка: " + PrivateValue(moneyText(position.optJSONObject("value"))))
    Text("Наблюдение от " + localMoment(position.text("as_of", "Дата не получена")), style = MaterialTheme.typography.bodySmall)
    if (uid.isNotBlank() && account.isNotBlank()) {
        SpectrumSecondaryButton("Открыть эту позицию", { navigate(EvidenceTarget("instrument", uid, accountId = account)) },
            Modifier.fillMaxWidth().testTag("assistant-impact-position"))
    }
    ImpactSources(position, sources)
}

@Composable
private fun ImpactChannel(index: Int, channel: JSONObject, sources: List<JSONObject>) {
    DetailFold("Возможный канал " + (index + 1), headerModifier = Modifier.testTag("assistant-impact-channel-$index")) {
        Text(PrivateValue(channel.text("mechanism", "Механизм не получен")), style = MaterialTheme.typography.bodyLarge)
        Text("Направление гипотезы: " + impactDirection(channel.text("direction", "")))
        Text("Горизонт гипотезы: " + impactHorizon(channel.text("horizon", "")))
        Text("Предпосылки", style = MaterialTheme.typography.titleSmall)
        channel.strings("assumptions").forEachIndexed { assumptionIndex, assumption ->
            Text((assumptionIndex + 1).toString() + ". " + PrivateValue(assumption))
        }
        Text("Неопределённость", style = MaterialTheme.typography.titleSmall)
        Text(PrivateValue(channel.text("uncertainty", "Основания требуют дополнительной проверки")))
        ImpactSources(channel, sources, Modifier.testTag("assistant-impact-channel-$index-sources"))
    }
}

@Composable
private fun ImpactSources(item: JSONObject, sources: List<JSONObject>, headerModifier: Modifier = Modifier) {
    val ids = item.strings("source_ids").toSet()
    val selected = sources.filter { it.text("id", "") in ids }
    if (selected.isNotEmpty()) EvidenceLinks(selected, headerModifier = headerModifier)
    else Text("Метаданные источников не получены.", style = MaterialTheme.typography.bodySmall)
}

private fun impactDirection(value: String): String = when (value) {
    "positive" -> "Возможное положительное влияние"
    "negative" -> "Возможное отрицательное влияние"
    "mixed" -> "Разнонаправленные факторы"
    else -> "Недостаточно оснований для направления"
}

private fun impactHorizon(value: String): String = when (value) {
    "short_term" -> "Краткосрочный"
    "medium_term" -> "Среднесрочный"
    "long_term" -> "Долгосрочный"
    else -> "Не определён"
}
