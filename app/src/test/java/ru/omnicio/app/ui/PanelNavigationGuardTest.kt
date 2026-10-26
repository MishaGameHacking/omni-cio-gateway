package ru.omnicio.app.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test
import ru.omnicio.app.ui.workspace.WorkspaceRoute

class PanelNavigationGuardTest {
    @Test
    fun anUnguardedDestinationContinues() {
        val guard = PanelNavigationGuard()
        var navigations = 0
        guard.request(WorkspaceRoute.Library) { navigations++ }
        assertEquals(1, navigations)
    }

    @Test
    fun aDirtyEditorCanHoldTheRealDestinationUntilConfirmation() {
        val guard = PanelNavigationGuard()
        var pending: (() -> Unit)? = null
        val events = mutableListOf<String>()
        guard.register(WorkspaceRoute.Strategies) { proceed ->
            events += "confirmation"
            pending = proceed
        }
        guard.request(WorkspaceRoute.Strategies) { events += "destination" }
        assertEquals(listOf("confirmation"), events)
        assertNotNull(pending)
        pending!!.invoke()
        assertEquals(listOf("confirmation", "destination"), events)
    }

    @Test
    fun repeatingAConfirmationCannotNavigateTwice() {
        val guard = PanelNavigationGuard()
        var pending: (() -> Unit)? = null
        var navigations = 0
        guard.register(WorkspaceRoute.Strategies) { pending = it }
        guard.request(WorkspaceRoute.Strategies) { navigations++ }
        pending!!.invoke()
        pending!!.invoke()
        assertEquals(1, navigations)
    }

    @Test
    fun disposedEditorCannotContinueAnOldRequest() {
        val guard = PanelNavigationGuard()
        var pending: (() -> Unit)? = null
        var navigations = 0
        val old = guard.register(WorkspaceRoute.Strategies) { pending = it }
        guard.request(WorkspaceRoute.Strategies) { navigations++ }
        guard.unregister(old)
        pending!!.invoke()
        assertEquals(0, navigations)
    }

    @Test
    fun outgoingCleanupCannotRemoveTheIncomingEditorGuard() {
        val guard = PanelNavigationGuard()
        var incoming: (() -> Unit)? = null
        var navigations = 0
        val old = guard.register(WorkspaceRoute.Strategies) { error("Stale editor intercepted navigation") }
        guard.register(WorkspaceRoute.Appearance) { incoming = it }
        guard.unregister(old)
        guard.request(WorkspaceRoute.Appearance) { navigations++ }
        assertEquals(0, navigations)
        incoming!!.invoke()
        assertEquals(1, navigations)
    }

    @Test
    fun replacedRegistrationInvalidatesItsPendingContinuation() {
        val guard = PanelNavigationGuard()
        var oldPending: (() -> Unit)? = null
        var navigations = 0
        guard.register(WorkspaceRoute.Strategies) { oldPending = it }
        guard.request(WorkspaceRoute.Strategies) { navigations++ }
        guard.register(WorkspaceRoute.Appearance) { it() }
        oldPending!!.invoke()
        assertEquals(0, navigations)
        guard.request(WorkspaceRoute.Appearance) { navigations++ }
        assertEquals(1, navigations)
    }

    @Test
    fun anUnrelatedRouteNeverUsesAnotherEditorsConfirmation() {
        val guard = PanelNavigationGuard()
        var navigations = 0
        guard.register(WorkspaceRoute.Strategies) { error("Wrong editor intercepted navigation") }
        guard.request(WorkspaceRoute.Library) { navigations++ }
        assertEquals(1, navigations)
    }

    @Test
    fun theWidePrimaryPathMustWaitForTheCurrentEditorsConfirmation() {
        val guard = PanelNavigationGuard()
        val source = AnalystTab.Profile to WorkspaceRoute.Strategies
        var active: Pair<AnalystTab, WorkspaceRoute?> = source
        var pending: (() -> Unit)? = null
        val events = mutableListOf<String>()
        guard.register(WorkspaceRoute.Strategies) { pending = it; events += "confirmation" }
        guard.requestDestination(source, { active }, sameDestination = false) {
            events += "home"
            active = AnalystTab.Home to null
        }
        assertEquals(listOf("confirmation"), events)
        assertEquals(source, active)
        pending!!.invoke()
        pending!!.invoke()
        assertEquals(listOf("confirmation", "home"), events)
        assertEquals(AnalystTab.Home to null, active)
    }

    @Test
    fun choosingTheCurrentPrimaryTabDoesNotPromptOrNavigate() {
        val guard = PanelNavigationGuard()
        val source: Pair<AnalystTab, WorkspaceRoute?> = AnalystTab.Profile to null
        var navigations = 0
        guard.requestDestination(source, { source }, sameDestination = true) { navigations++ }
        assertEquals(0, navigations)
    }

    @Test
    fun aDestinationChangeInvalidatesThePendingWideContinuation() {
        val guard = PanelNavigationGuard()
        val source = AnalystTab.Profile to WorkspaceRoute.Strategies
        var active: Pair<AnalystTab, WorkspaceRoute?> = source
        var pending: (() -> Unit)? = null
        var navigations = 0
        guard.register(WorkspaceRoute.Strategies) { pending = it }
        guard.requestDestination(source, { active }, sameDestination = false) { navigations++ }
        active = AnalystTab.Actions to WorkspaceRoute.Market
        pending!!.invoke()
        assertEquals(0, navigations)
    }

    @Test
    fun anOutgoingRouteCannotOpenAConfirmationForTheIncomingPage() {
        val guard = PanelNavigationGuard()
        val source = AnalystTab.Profile to WorkspaceRoute.Strategies
        val active = AnalystTab.Profile to WorkspaceRoute.Appearance
        var requests = 0
        var navigations = 0
        guard.register(WorkspaceRoute.Strategies) { requests++ }
        guard.requestDestination(source, { active }, sameDestination = false) { navigations++ }
        assertEquals(0, requests)
        assertEquals(0, navigations)
    }
}
