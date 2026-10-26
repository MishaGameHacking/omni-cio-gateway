package ru.omnicio.app.ui.workspace

import org.junit.Assert.*
import org.junit.Test

class SuggestedInputModelTest {
    @Test fun searchUsesEveryWordAndReturnsOnlyExistingValues() {
        val options = listOf(WorkspaceSuggestion("id-1", "Первая компания", "FIRST RU0001"),
            WorkspaceSuggestion("id-2", "Вторая компания", "SECOND RU0002"))
        assertEquals(listOf(options[0]), matchingSuggestions(options, " ПЕРВАЯ ru0001 "))
        assertTrue(matchingSuggestions(options, "неизвестный uid").isEmpty())
        assertTrue(matchingSuggestions(options, "первая RU0002").isEmpty())
    }
    @Test fun duplicateLabelsKeepDistinctSourceIdsAndNoOptionCountCeiling() {
        val options = (1..2500).map { WorkspaceSuggestion("id-$it", "Название", "$it") }
        assertEquals(2500, matchingSuggestions(options, "").size)
        assertEquals("id-2500", matchingSuggestions(options, "2500").single().value)
        assertEquals(options, matchingSuggestions(options + options[0], ""))
    }
    @Test fun blankAllOptionAndUnknownCurrentValueDoNotCreateSyntheticChoices() {
        val all = WorkspaceSuggestion("", "Все счета")
        assertEquals(listOf(all), matchingSuggestions(listOf(all), ""))
        val zones = notificationZoneSuggestions("Europe/Moscow", "missing-zone")
        assertEquals("Europe/Moscow", zones.first().value)
        assertFalse(zones.any { it.value == "missing-zone" })
        assertEquals("Europe/Moscow", matchingSuggestions(zones, "Москва").single().value)
    }
}
