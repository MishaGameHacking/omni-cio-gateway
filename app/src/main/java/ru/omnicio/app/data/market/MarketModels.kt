package ru.omnicio.app.data.market

import org.json.JSONObject
import java.math.BigDecimal
import java.time.Instant

data class MarketCandle(val time: String, val open: BigDecimal, val high: BigDecimal, val low: BigDecimal,
    val close: BigDecimal, val volumeLots: BigDecimal, val isComplete: Boolean, val sourceId: String?)
data class CandleSnapshot(val instrumentUid: String, val interval: String, val start: String, val end: String,
    val asOf: String?, val unitLabel: String, val currency: String?, val state: String, val reason: String?,
    val candles: List<MarketCandle>, val sources: List<JSONObject>, val events: List<JSONObject>, val unit: String? = null)

fun parseCandles(json: JSONObject, expectedUid: String): CandleSnapshot {
    require(json.optInt("schema_version") == 1 && json.optString("instrument_uid") == expectedUid)
    val rows = json.records("candles")
    require(rows.size <= 2500)
    val seen = hashSetOf<String>()
    val candles = rows.map { row ->
        val time = Instant.parse(row.getString("time")).toString(); require(seen.add(time))
        fun number(key: String): BigDecimal {
            val value = row.getString(key).toBigDecimal()
            require(value.precision() <= 128 && value.scale() in -128..128)
            require(value.toDouble().isFinite())
            return value
        }
        val open = number("open"); val high = number("high"); val low = number("low"); val close = number("close")
        val volume = number("volume_lots")
        require(low <= high && open in low..high && close in low..high && volume >= BigDecimal.ZERO)
        require(row.opt("is_complete") is Boolean)
        MarketCandle(time, open, high, low, close, volume, row.getBoolean("is_complete"), row.optionalText("source_id"))
    }.sortedBy { Instant.parse(it.time) }
    val state = json.optString("state", "unavailable")
    require(state in setOf("available", "partial", "unavailable", "not_configured", "empty"))
    return CandleSnapshot(expectedUid, json.getString("interval"), json.getString("start"), json.getString("end"),
        json.optionalText("as_of"), json.optionalText("unit_label") ?: "Единица цены не подтверждена", json.optionalText("currency"),
        state, json.optionalText("reason"), candles, json.records("sources"), json.records("events"), json.optionalText("unit"))
}
