package ru.omnicio.app.ui.home

import org.junit.Assert.*
import org.junit.Test

class SystemTelemetryTest {
    @Test fun unknownTotalNeverBecomesInventedPercent() {
        assertNull(observedProgress("9", null)?.fraction)
        assertNull(observedProgress("9", "null")?.fraction)
        assertNull(observedProgress("0", "0")?.fraction)
    }

    @Test fun inconsistentOrMalformedCountersCannotLookComplete() {
        assertNull(observedProgress("11", "10"))
        assertNull(observedProgress("-1", "10"))
        assertNull(observedProgress("4", "missing"))
        assertNull(observedProgress("1.5", "10"))
        assertEquals(.4f, observedProgress("4", "10")!!.fraction!!, .0001f)
    }

    @Test fun missingDisabledOrNegativeBudgetHasNoFill() {
        assertNull(observedBudgetFraction("20", null))
        assertNull(observedBudgetFraction("20", "0"))
        assertNull(observedBudgetFraction("-1", "100"))
        assertNull(observedBudgetFraction("NaN", "100"))
        assertEquals(.25f, observedBudgetFraction("12.5", "50")!!, .0001f)
        assertEquals(1f, observedBudgetFraction("120", "100")!!, .0001f)
    }
}
