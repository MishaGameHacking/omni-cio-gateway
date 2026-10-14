package ru.omnicio.app.data.research

import java.net.URI

/** A viewing URL only: never an order, transfer, private scheme or arbitrary host. */
object InstrumentPage {
    const val BROKER_PACKAGE = "ru.tinkoff.investing"
    private val path = Regex("/invest/(stocks|bonds|etfs)/[A-Za-z0-9][A-Za-z0-9_.-]{0,38}@?/")

    fun accepted(raw: String?): String? {
        if (raw.isNullOrBlank() || raw.length > 200) return null
        return runCatching {
            val uri = URI(raw)
            if (uri.scheme != "https" || uri.host != "www.tbank.ru" || uri.port != -1 ||
                uri.rawUserInfo != null || uri.rawQuery != null || uri.rawFragment != null ||
                uri.rawPath != uri.path || !path.matches(uri.rawPath)
            ) null else raw
        }.getOrNull()
    }
}
