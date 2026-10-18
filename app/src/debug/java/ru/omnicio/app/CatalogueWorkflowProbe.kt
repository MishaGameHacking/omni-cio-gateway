package ru.omnicio.app

import android.net.Uri
import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.data.workspace.VolumeReply

private const val CATALOGUE_UID = "synthetic-new-bond"
private const val CATALOGUE_NAME = "СИНТЕТИЧЕСКИЙ НОВЫЙ АКТИВ"

/** Test-only transport. No broker, model, order, or production account is used. */
internal fun catalogueProbeReply(path: String, method: String, body: JSONObject?, scenario: String): VolumeReply? {
    val endpoint = path.substringBefore('?')
    if (method == "GET" && endpoint == "/workspace/catalogue") {
        val query = Uri.parse("https://fixture.invalid$path")
        val kind = query.getQueryParameter("kind")
        check(kind in setOf("bond", "share", "etf"))
        check(query.getQueryParameter("offset") == "0")
        val terms = query.getQueryParameter("query").orEmpty().lowercase()
        val rows = JSONArray()
        if (scenario != "empty" && (terms.isBlank() || "new1".contains(terms))) rows.put(JSONObject()
            .put("uid", CATALOGUE_UID).put("instrument_type", kind).put("name", CATALOGUE_NAME)
            .put("ticker", "NEW1").put("isin", "SYNTHETIC-NOT-ISIN").put("currency", "RUB"))
        return VolumeReply(data = JSONObject().put("items", rows).put("total", rows.length())
            .put("revision", "synthetic-catalogue-revision").put("next_offset", JSONObject.NULL)
            .put("as_of", "2026-10-18T10:00:00Z"))
    }
    if (method != "POST" || endpoint != "/workspace/purchases/check") return null
    requireNotNull(body)
    check(body.keys().asSequence().toSet() == setOf("account_id", "instrument_uid", "lots", "limit_price", "strategy_version"))
    check(body.getString("account_id") == "synthetic-account")
    check(body.getString("instrument_uid") == CATALOGUE_UID)
    check(body.getInt("lots") == 1 && body.getString("limit_price") == "95")
    check(body.getInt("strategy_version") == 3)
    val allowed = scenario == "ready"
    return VolumeReply(data = JSONObject().put("constraints_passed", allowed).put("suitability_complete", false)
        .put("automatic_order", false).put("check_id", "synthetic-purchase-check")
        .put("total_cost", JSONObject().put("amount", "952").put("currency", "RUB"))
        .put("cash_after", JSONObject().put("amount", "9048").put("currency", "RUB"))
        .put("reasons", JSONArray().apply { if (!allowed) put("protected_reserve_would_be_spent") })
        .put("concentrations", JSONArray()).put("as_of", "2026-10-18T10:00:00Z")
        .put("expires_at", "2026-10-18T10:01:00Z"))
}
