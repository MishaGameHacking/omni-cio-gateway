package ru.omnicio.app.ui.workspace

import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.data.analysis.AnalysisProfile

internal fun JSONObject.autoSaveId(): String? = optString("id").takeUnless { it.isBlank() || it == "null" }

internal fun goalEditableDocument(goal: JSONObject): JSONObject = JSONObject()
    .put("id", goal.autoSaveId() ?: JSONObject.NULL).put("title", goal.optString("title", ""))
    .put("target", goal.optJSONObject("target") ?: JSONObject().put("amount", "").put("currency", "RUB"))
    .put("reserve", goal.optJSONObject("reserve") ?: JSONObject().put("amount", "0").put("currency", "RUB"))

internal fun goalDocumentValid(goal: JSONObject): Boolean {
    val target = goal.optJSONObject("target") ?: return false
    val reserve = goal.optJSONObject("reserve") ?: return false
    return goal.optString("title").trim().isNotEmpty() && goal.optString("title").length <= 100 &&
        target.optString("amount").toBigDecimalOrNull()?.signum() == 1 &&
        reserve.optString("amount").toBigDecimalOrNull()?.signum()?.let { it >= 0 } == true &&
        target.optString("currency") in listOf("RUB", "USD", "EUR") &&
        reserve.optString("currency") == target.optString("currency")
}

/** Server presentation fields never become writable preferences. */
internal fun analysisEditableDocument(value: JSONObject): JSONObject {
    val result = JSONObject()
    listOf("risk_level", "horizon", "allowed_markets", "max_position_percent", "min_cash_percent",
        "notify_critical", "notify_briefs").forEach { key -> if (value.has(key)) result.put(key, value.get(key)) }
    return result
}

fun AnalysisProfile.automaticDocument(): JSONObject = JSONObject().put("risk_level", riskLevel).put("horizon", horizon)
    .put("allowed_markets", JSONArray(allowedMarkets)).put("max_position_percent", maxPositionPercent)
    .put("min_cash_percent", minCashPercent).put("notify_critical", notifyCritical).put("notify_briefs", notifyBriefs)

fun automaticAnalysisProfile(value: JSONObject): AnalysisProfile = AnalysisProfile(
    riskLevel = value.getString("risk_level"), horizon = value.getString("horizon"),
    allowedMarkets = value.getJSONArray("allowed_markets").let { rows -> (0 until rows.length()).map { rows.getString(it) } },
    maxPositionPercent = value.getDouble("max_position_percent"), minCashPercent = value.getDouble("min_cash_percent"),
    notifyCritical = value.getBoolean("notify_critical"), notifyBriefs = value.getBoolean("notify_briefs"), configured = true)
