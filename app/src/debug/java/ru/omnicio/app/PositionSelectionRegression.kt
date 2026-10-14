package ru.omnicio.app

import ru.omnicio.app.ui.portfolio.PositionSelection
import ru.omnicio.app.ui.portfolio.resolveSelectedPosition

private data class ProbePosition(val id: String, val amount: String, val blocked: Boolean = false)
private data class ProbeAccount(val id: String, val actual: List<ProbePosition>, val virtual: List<ProbePosition> = emptyList())

/** Snapshot/identity tests only. Synthetic prices never enter production UI. */
internal fun runPositionSelectionChecks(): Int {
    var count = 0
    fun verify(test: () -> Unit) { test(); count++ }
    fun resolve(ref: PositionSelection?, accounts: List<ProbeAccount>?) = resolveSelectedPosition(
        ref, accounts, ProbeAccount::id, { a, v -> if (v) a.virtual else a.actual }, ProbePosition::id,
    )
    val before = ProbePosition("uid", "100")
    val now = ProbePosition("uid", "101", blocked = true)
    val ref = PositionSelection("account-a", "uid")
    val a = ProbeAccount("account-a", listOf(before))
    val b = ProbeAccount("account-b", listOf(ProbePosition("uid", "999")))
    verify { check(resolve(ref, listOf(a)) === before) }
    verify { check(resolve(ref, listOf(a.copy(actual = listOf(now)))) === now) }
    verify { check(resolve(ref, listOf(a.copy(actual = listOf(now))))!!.blocked) }
    verify { check(resolve(ref, listOf(b, a)) === before) }
    verify { check(resolve(ref, listOf(b)) == null) }
    verify { check(resolve(ref, listOf(a.copy(actual = emptyList()))) == null) }
    verify { check(resolve(ref, listOf(a.copy(actual = listOf(before, now)))) == null) }
    verify { check(resolve(ref, listOf(a, a)) == null) }
    verify { check(resolve(ref, null) == null) }
    verify { check(resolve(null, listOf(a)) == null) }
    verify { check(resolve(ref, emptyList()) == null) }
    val virtual = ProbePosition("uid", "42")
    val mixed = a.copy(virtual = listOf(virtual))
    verify { check(resolve(ref, listOf(mixed)) === before) }
    verify { check(resolve(ref.copy(virtual = true), listOf(mixed)) === virtual) }
    verify { check(resolve(ref.copy(virtual = true), listOf(a)) == null) }
    verify { check(resolve(ref.copy(positionId = "UID"), listOf(a)) == null) }
    verify { check(resolve(PositionSelection("", "uid"), listOf(a.copy(id = ""))) == null) }
    verify { check(resolve(ref.copy(positionId = " "), listOf(a.copy(actual = listOf(before.copy(id = " "))))) == null) }
    verify { check(before.amount == "100"); check(a.actual.single() === before) }
    return count
}

fun main() { println("POSITION_SELECTION_TESTS=passed:" + runPositionSelectionChecks()) }
