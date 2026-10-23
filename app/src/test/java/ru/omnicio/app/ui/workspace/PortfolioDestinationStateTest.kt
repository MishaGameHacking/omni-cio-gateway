package ru.omnicio.app.ui.workspace

import androidx.compose.runtime.saveable.SaverScope
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PortfolioDestinationStateTest {
    private val scope = object : SaverScope {
        override fun canBeSaved(value: Any) = true
    }

    @Test fun pendingNavigationRetainsAccountFiltersAndExactOperation() {
        val target = PortfolioDestination(1, "account-b", "instrument-a", "energy", "bond",
            "operation-17", "2026-10-17T09:15:00Z")
        val saved = with(PortfolioDestinationSaver) { scope.save(target) }
        assertEquals(target, PortfolioDestinationSaver.restore(requireNotNull(saved)))
    }

    @Test fun missingDestinationAndOptionalFieldsStayMissing() {
        val absent = with(PortfolioDestinationSaver) { scope.save(null) }
        assertNull(PortfolioDestinationSaver.restore(requireNotNull(absent)))
        val target = PortfolioDestination(section = 3)
        val saved = with(PortfolioDestinationSaver) { scope.save(target) }
        assertEquals(target, PortfolioDestinationSaver.restore(requireNotNull(saved)))
    }

    @Test fun malformedSavedNavigationDoesNotSelectAnotherDestination() {
        assertNull(PortfolioDestinationSaver.restore(listOf("1", "account-b")))
        for (section in listOf("-1", "5", "not-a-section")) {
            assertNull(PortfolioDestinationSaver.restore(listOf(section, "account-b", "", "", "", "", "")))
        }
    }
}
