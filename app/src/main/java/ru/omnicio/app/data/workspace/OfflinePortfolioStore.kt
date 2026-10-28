package ru.omnicio.app.data.workspace

import android.content.Context
import org.json.JSONObject
import ru.omnicio.app.data.portfolio.PortfolioCurrency
import ru.omnicio.app.data.portfolio.PortfolioDataClient
import ru.omnicio.app.data.portfolio.PortfolioSnapshot

data class OfflinePortfolio(val snapshot: PortfolioSnapshot, val receivedAtMillis: Long, val currency: PortfolioCurrency)

/** Cached financial data is never a session or an authority to submit a new operation. */
class OfflinePortfolioStore(context: Context) {
    private val encrypted = EncryptedWorkspaceStore(context)
    fun save(userId: String, currency: PortfolioCurrency, json: JSONObject, at: Long): Boolean {
        val envelope = JSONObject().put("schema", 1).put("received_at", at).put("currency", currency.name).put("snapshot", json)
        val saved = encrypted.saveJson(userId, key(currency), envelope)
        if (saved) encrypted.saveJson(userId, "portfolio_latest", JSONObject().put("currency", currency.name))
        return saved
    }
    fun read(userId: String, currency: PortfolioCurrency? = null): OfflinePortfolio? = runCatching {
        if (userId.isBlank()) return null
        val actual = currency ?: PortfolioCurrency.valueOf(encrypted.readJson(userId, "portfolio_latest")?.getString("currency") ?: return null)
        val envelope = encrypted.readJson(userId, key(actual)) ?: return null
        require(envelope.getInt("schema") == 1 && envelope.getString("currency") == actual.name)
        val at = envelope.getLong("received_at")
        require(at > 0 && at <= System.currentTimeMillis() + 60_000)
        OfflinePortfolio(PortfolioDataClient().parsePortfolio(envelope.getJSONObject("snapshot")), at, actual)
    }.getOrNull()
    fun clearSnapshots(userId: String) {
        PortfolioCurrency.entries.forEach { encrypted.remove(userId, key(it)) }
        encrypted.remove(userId, "portfolio_latest")
    }
    private fun key(currency: PortfolioCurrency) = "portfolio_${currency.name}"
}
