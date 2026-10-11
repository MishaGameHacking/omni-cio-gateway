package ru.omnicio.app.ui

import org.json.JSONObject

internal data class StrategyUiState(
    val catalog: JSONObject? = null,
    val selection: JSONObject? = null,
    val loaded: Boolean = false,
    val assessment: JSONObject? = null,
) {
    val version: Int get() = selection?.getInt("version") ?: 0

    fun afterFailure(error: Exception, expired: Boolean): StrategyUiState {
        if (expired) return StrategyUiState()
        val rejected = error is ApiFailure &&
            (error.code.startsWith("strategy_") || error.code == "settings_version_conflict")
        return if (rejected) copy(assessment = null) else StrategyUiState()
    }
}

internal fun ServerApi.loadStrategy(publicId: String): StrategyUiState {
    val catalog = request("/api/strategy/catalog")
    val response = request("/api/profile/strategy")
    if (response.getString("public_id") != publicId) throw ApiFailure(409, "profile_context_changed")
    return StrategyUiState(catalog, response.optJSONObject("selection"), loaded = true)
}

/** Copies the server template. Personal money facts never acquire default zeros. */
internal fun strategyTemplate(template: JSONObject, current: JSONObject?): JSONObject {
    val document = JSONObject(template.toString())
    listOf("profile" to "reserve_rub", "profile" to "planned_withdrawal_rub",
        "policy" to "securities_tax_rate_percent").forEach { (section, key) ->
        current?.optJSONObject(section)?.let { document.getJSONObject(section).put(key, it.get(key)) }
    }
    return document
}

internal val allocationLabels = linkedMapOf("shares" to "Акции", "bonds" to "Облигации",
    "funds" to "Фонды", "cash" to "Деньги")

internal fun strategyAllocationValid(document: JSONObject): Boolean =
    allocationLabels.keys.sumOf { document.getJSONObject("allocation").getInt(it) } == 100
