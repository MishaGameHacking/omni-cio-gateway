package ru.omnicio.app.ui.workspace

import org.junit.Assert.assertEquals
import org.junit.Test

class PlanEditorInitializationTest {
    @Test fun openEditorSelectsAnAccountWhenItsFirstSnapshotArrives() {
        var accountId = initialPlanAccountId("", emptyList())
        assertEquals("", accountId)

        val positions = mapOf("account-a" to listOf("instrument-a"), "account-b" to listOf("instrument-b"))
        accountId = initialPlanAccountId(accountId, positions.keys.toList())
        assertEquals("account-a", accountId)
        assertEquals(listOf("instrument-a"), positions[accountId])
    }

    @Test fun restoredChoiceSurvivesAnEmptySnapshotAndChangedAccountOrder() {
        var accountId = "account-b"
        for (accounts in listOf(emptyList(), listOf("account-a", "account-b"), listOf("account-b", "account-a"))) {
            accountId = initialPlanAccountId(accountId, accounts)
            assertEquals("account-b", accountId)
        }
    }

    @Test fun unavailableChosenAccountIsNotSilentlyReplaced() {
        val remainingAccounts = listOf("account-a")
        val accountId = initialPlanAccountId("account-b", remainingAccounts)
        assertEquals("account-b", accountId)
        assertEquals(-1, remainingAccounts.indexOf(accountId))
    }

    @Test fun explicitChoiceMadeBeforeTheInitializationEffectRunsWins() {
        val arrivingAccounts = listOf("account-a", "account-b")
        val selectedByUser = "account-b"
        assertEquals(selectedByUser, initialPlanAccountId(selectedByUser, arrivingAccounts))
    }
}
