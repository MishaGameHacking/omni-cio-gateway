package ru.omnicio.app

import ru.omnicio.app.data.research.InstrumentPage

/** Pure JVM tests; no broker app installation or production identity changes. */
fun runInstrumentLinkRegressions(): Int {
    val good = listOf("https://www.tbank.ru/invest/stocks/SBER/", "https://www.tbank.ru/invest/bonds/SU26232RMFS7/", "https://www.tbank.ru/invest/etfs/TPAY/")
    val bad = listOf(null, "", "intent://order", "http://www.tbank.ru/invest/stocks/SBER/", "https://www.tbank.ru.evil.test/invest/stocks/SBER/", "https://www.tbank.ru:444/invest/stocks/SBER/", "https://www.tbank.ru/invest/stocks/SBER/?buy=1", "https://evil@www.tbank.ru/invest/stocks/SBER/", "https://www.tbank.ru/invest/stocks/%53BER/", "https://www.tbank.ru/invest/stocks/../", "https://www.tbank.ru/invest/stocks/SBER/#trade")
    good.forEach { check(InstrumentPage.accepted(it) == it) }
    bad.forEach { check(InstrumentPage.accepted(it) == null) }
    check(InstrumentPage.BROKER_PACKAGE == "ru.tinkoff.investing")
    return good.size + bad.size + 1
}

fun main() { println("INSTRUMENT_LINK_TESTS=passed:" + runInstrumentLinkRegressions()) }
