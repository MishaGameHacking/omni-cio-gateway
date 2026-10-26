package ru.omnicio.app.ui

import org.junit.Assert.*
import org.junit.Test
import ru.omnicio.app.ui.workspace.WorkspaceRoute

class NavigationCatalogueTest {
    @Test fun everyRestorableWorkspaceHasExactlyOneDestinationAndReachableParent() {
        assertEquals(analystDestinations.size, analystDestinations.map { it.id }.distinct().size)
        for (route in WorkspaceRoute.entries) {
            val matches = analystDestinations.filter { it.workspace == route }
            assertEquals(route.name, 1, matches.size)
            assertEquals(route.name, matches.single().id)
            assertTrue(analystPrimaryDestinations.any { it.tab == matches.single().parent })
        }
    }
    @Test fun portfolioIsADirectRootAndSectionSwitchesDoNotAccumulateSiblingHistory() {
        assertEquals(listOf("Home","Portfolio","Recommendations","Profile"), analystPrimaryDestinations.map { it.id })
        for (root in analystPrimaryDestinations) assertEquals(emptyList<String>(),sectionBackStack(root.id))
        assertEquals(listOf("Portfolio"),sectionBackStack("Strategies"))
        assertEquals(listOf("Recommendations"),sectionBackStack("Assistant"))
        assertEquals(listOf("Profile"),sectionBackStack("Appearance"))
        assertNull(sectionBackStack("unknown_saved_route"))
    }
    @Test fun drawerAndRailCanReachEveryExistingWorkingDestination() {
        assertTrue(analystMenuDestinations.containsAll(analystPrimaryDestinations))
        assertEquals(WorkspaceRoute.entries.toSet(),analystMenuDestinations.mapNotNull { it.workspace }.toSet())
        assertTrue(analystMenuDestinations.any { it.tab == AnalystTab.Risk })
        assertEquals("Портфель",AnalystTab.Portfolio.destination().title)
    }
    @org.junit.Test fun everyMenuDestinationHasItsOwnIcon() {
        val icons = analystMenuDestinations.map { it.symbol.asset }
        org.junit.Assert.assertEquals(icons.size, icons.toSet().size)
        org.junit.Assert.assertTrue(analystMenuDestinations.all { it.title.isNotBlank() })
    }
}
