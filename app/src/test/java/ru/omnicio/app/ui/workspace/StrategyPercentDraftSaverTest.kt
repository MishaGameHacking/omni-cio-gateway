package ru.omnicio.app.ui.workspace

import androidx.compose.runtime.saveable.SaverScope
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class StrategyPercentDraftSaverTest {
    private val scope = object : SaverScope {
        override fun canBeSaved(value: Any) = value is String || value is Int || value is Boolean
    }

    @Test fun restoringAnIncompleteEditorDoesNotResurrectTheOldPercentage() {
        val baseline = StrategyDraft()
        val edited = StrategyPercentDraft(baseline)
            .edit(StrategyPercentField.Reserve, "15")
            .edit(StrategyPercentField.Reserve, "")
            .edit(StrategyPercentField.Company, "99")
        val saved = with(StrategyPercentDraftSaver) { scope.save(edited) }
        val restored = StrategyPercentDraftSaver.restore(requireNotNull(saved))
        assertEquals(edited, restored)
        assertNull(requireNotNull(restored).applyTo(baseline))
        val repaired = restored.edit(StrategyPercentField.Reserve, "20")
            .edit(StrategyPercentField.Company, "7")
        val confirmed = requireNotNull(repaired.applyTo(baseline))
        val savedDraft = with(StrategyDraftSaver) { scope.save(confirmed) }
        assertEquals(confirmed, StrategyDraftSaver.restore(requireNotNull(savedDraft)))
        assertEquals(20, confirmed.reserve)
        assertEquals(7, confirmed.companyLimit)
    }

    @Test fun incompleteSavedInputCannotBeReplacedWithDefaults() {
        assertNull(StrategyPercentDraftSaver.restore(emptyList<String>()))
        assertNull(StrategyPercentDraftSaver.restore(listOf("10", "5")))
    }
}
