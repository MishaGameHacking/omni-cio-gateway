package ru.omnicio.app.ui.portfolio

/** Retain an identity, never a frozen position price/quantity from a prior poll. */
internal data class PositionSelection(val accountId: String, val positionId: String, val virtual: Boolean = false)

internal fun <A, P> resolveSelectedPosition(
    selection: PositionSelection?,
    accounts: List<A>?,
    accountKey: (A) -> String,
    positions: (A, Boolean) -> List<P>,
    positionKey: (P) -> String,
): P? {
    if (selection == null || accounts == null || selection.accountId.isBlank() || selection.positionId.isBlank()) return null
    val account = accounts.singleOrNull { accountKey(it) == selection.accountId } ?: return null
    // Never substitute the same ticker/UID from another account or an actual
    // position for a virtual one. Ambiguous identifiers are not selectable.
    return positions(account, selection.virtual).singleOrNull { positionKey(it) == selection.positionId }
}

