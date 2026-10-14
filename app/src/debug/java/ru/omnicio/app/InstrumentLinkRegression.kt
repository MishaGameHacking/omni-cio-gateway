package ru.omnicio.app

import ru.omnicio.app.data.research.InstrumentPage

/** Pure JVM tests; no broker app installation or production identity changes. */
fun runInstrumentLinkRegressions(): Int {
    val good = listOf(
        "https://www.tbank.ru/invest/stocks/SBER/",
        "https://www.tbank.ru/invest/bonds/SU26232RMFS7/",
        "https://www.tbank.ru/invest/etfs/TPAY/",
    )
    // Reviewed false positive: this is deliberately REJECTED input to a pure
    // URI validator. No socket, Intent or browser ever receives this string.
    // Keep this negative case; changing it to HTTPS would remove the protection.
    @Suppress("kotlin:S5332")
    val rejectedCleartextFixture = "http://www.tbank.ru/invest/stocks/SBER/"
    val bad = listOf(
        null, "", "intent://order", rejectedCleartextFixture,
        "https://www.tbank.ru.evil.test/invest/stocks/SBER/",
        "https://www.tbank.ru:444/invest/stocks/SBER/",
        "https://www.tbank.ru/invest/stocks/SBER/?buy=1",
        "https://evil@www.tbank.ru/invest/stocks/SBER/",
        "https://www.tbank.ru/invest/stocks/%53BER/",
        "https://www.tbank.ru/invest/stocks/../",
        "https://www.tbank.ru/invest/stocks/SBER/#trade",
    )
    good.forEach { check(InstrumentPage.accepted(it) == it) }
    bad.forEach { check(InstrumentPage.accepted(it) == null) }
    check(InstrumentPage.BROKER_PACKAGE == "ru.tinkoff.investing")
    return good.size + bad.size + 1
}

fun main() { println("INSTRUMENT_LINK_TESTS=passed:" + runInstrumentLinkRegressions()) }
