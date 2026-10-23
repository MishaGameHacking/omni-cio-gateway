package ru.omnicio.app.ui.workspace

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Test

class StrategyPercentDraftTest {
    @Test fun clearedFieldCannotPersistThePreviouslyValidNumber() {
        val saved = StrategyDraft()
        val changed = StrategyPercentDraft(saved).edit(StrategyPercentField.Reserve, "15")
        assertEquals(15, changed.applyTo(saved)?.reserve)
        val cleared = changed.edit(StrategyPercentField.Reserve, "")
        assertEquals("", cleared.reserve)
        assertNotEquals(StrategyPercentDraft(saved), cleared)
        assertNull(cleared.applyTo(saved))
        val repaired = cleared.edit(StrategyPercentField.Reserve, "20")
        val persisted = repaired.applyTo(saved)
        assertEquals(20, persisted?.reserve)
        assertEquals("20", StrategyPercentDraft(requireNotNull(persisted)).reserve)
    }

    @Test fun anotherFieldCannotMakeAnIncompleteDraftSavable() {
        val saved = StrategyDraft()
        val invalid = StrategyPercentDraft(saved).edit(StrategyPercentField.Company, "0")
        val changedElsewhere = invalid.edit(StrategyPercentField.Reserve, "30")
        assertEquals("0", changedElsewhere.company)
        assertEquals("30", changedElsewhere.reserve)
        assertNull(changedElsewhere.applyTo(saved.copy(goal = 2)))
        val repaired = changedElsewhere.edit(StrategyPercentField.Company, "7").applyTo(saved.copy(goal = 2))
        assertEquals(7, repaired?.companyLimit)
        assertEquals(30, repaired?.reserve)
        assertEquals(2, repaired?.goal)
    }

    @Test fun everyFieldRetainsItsExistingInclusiveLimits() {
        val saved = StrategyDraft()
        val initial = StrategyPercentDraft(saved)
        for (field in StrategyPercentField.entries) {
            for (value in listOf(field.range.first, field.range.last)) {
                val changed = initial.edit(field, value.toString())
                assertEquals(value, changed.value(field))
                assertEquals(value.toString(), StrategyPercentDraft(requireNotNull(changed.applyTo(saved))).text(field))
            }
            for (text in listOf("", "-", "abc", (field.range.first - 1).toString(), (field.range.last + 1).toString())) {
                val changed = initial.edit(field, text)
                assertNull(changed.applyTo(saved))
            }
        }
    }

    @Test fun validationUsesExactlyTheTextLeftVisibleAfterAnEdit() {
        val saved = StrategyDraft()
        val pasted = StrategyPercentDraft(saved).edit(StrategyPercentField.Reserve, "0500")
        assertEquals("050", pasted.reserve)
        assertEquals(50, pasted.applyTo(saved)?.reserve)
        val invalid = pasted.edit(StrategyPercentField.Reserve, "9999")
        assertEquals("999", invalid.reserve)
        assertNull(invalid.applyTo(saved))
    }
}
