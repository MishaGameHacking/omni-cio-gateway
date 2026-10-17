package ru.omnicio.app

import java.time.Instant
import ru.omnicio.app.data.analysis.InsightCard
import ru.omnicio.app.data.portfolio.*
import ru.omnicio.app.ui.analysis.insightActive
import ru.omnicio.app.ui.portfolio.*
import ru.omnicio.app.ui.workspace.*

/** Runtime regressions in the debug probe; no authentication or release bypass. */
internal fun runWorkspaceUxChecks(): Int {
    val rub = MoneyAmount(ApiDecimal(500, 0), "RUB")
    val first = PortfolioPosition("one", "Первая компания", "FIRST", null, rub, null, isin = "RU000TEST001")
    val second = first.copy(id = "two", title = "Вторая", ticker = "SECOND", currentValue = MoneyAmount(ApiDecimal(999, 0), "USD"))
    val account = PortfolioAccount("a", "Счёт A", rub, null, listOf(first, second))
    check(matchingPosition(first, "first"))
    check(matchingPosition(first, "  RU000TEST001 "))
    check(matchingPosition(first, "компания"))
    check(!matchingPosition(first, "missing"))
    check(matchingPosition(first, ""))
    val rows = listOf(PortfolioRow(account, second), PortfolioRow(account, first))
    check(sortedPortfolioRows(rows, 1, "RUB").first().position.id == "one")
    check(sortedPortfolioRows(rows, 1, "USD").first().position.id == "two")
    val blocked = PortfolioRow(account, first.copy(blocked = true))
    check(sortedPortfolioRows(rows + blocked, 0, "RUB").first() == blocked)
    val now = Instant.parse("2026-10-17T00:00:00Z")
    val event = InsightCard("i", "risk", "warning", "Событие", "Тест", emptyList(), emptyList(), emptyList(), "2026-10-18T00:00:00Z", false, "2026-10-16T00:00:00Z")
    check(insightActive(event, now))
    check(!insightActive(event.copy(validUntil = "2026-10-16T00:00:00Z"), now))
    check(insightActive(event.copy(validUntil = null), now)) // Unknown validity remains visible.
    check(insightActive(event.copy(validUntil = "invalid"), now))
    check(strategyChanges(StrategyDraft(), StrategyDraft()).isEmpty())
    check(strategyChanges(StrategyDraft(), StrategyDraft(reserve = 20)).single().contains("10% → 20%"))
    check(operationStateLabel("OPERATION_STATE_EXECUTED") == "Исполнено")
    check(operationStateLabel("PRIVATE_NEW_CODE").startsWith("Статус уточняется"))
    check(relativeObservation("2026-10-16T23:50:00Z", now) == "10 мин назад")
    check(relativeObservation("broken", now) == "время не получено")
    check(relativeObservation("2026-10-18T00:00:00Z", now) == "время требует проверки")
    return 19
}
