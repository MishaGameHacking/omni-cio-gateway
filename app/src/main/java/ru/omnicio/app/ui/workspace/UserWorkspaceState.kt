package ru.omnicio.app.ui.workspace

import androidx.compose.runtime.Composable
import androidx.compose.runtime.MutableState
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.SaveableStateHolder
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder

/** Retains only saveable UI context while the authenticated subtree is absent. */
internal class UserWorkspaceState(
    private val holder: SaveableStateHolder,
    private val retainedUser: MutableState<String?>,
) {
    /** The caller supplies the identity already established by authentication. */
    @Composable
    fun Content(confirmedUserId: String, content: @Composable () -> Unit) {
        require(confirmedUserId.isNotBlank())
        SideEffect {
            val previous = retainedUser.value
            if (previous != confirmedUserId) {
                previous?.let(holder::removeState)
                retainedUser.value = confirmedUserId
            }
        }
        holder.SaveableStateProvider(confirmedUserId, content)
    }

    /** Explicit logout also prevents the currently composed subtree being saved. */
    fun forget() {
        retainedUser.value?.let(holder::removeState)
        retainedUser.value = null
    }
}

@Composable
internal fun rememberUserWorkspaceState(): UserWorkspaceState {
    val holder = rememberSaveableStateHolder()
    val retainedUser = rememberSaveable { mutableStateOf<String?>(null) }
    return remember(holder, retainedUser) { UserWorkspaceState(holder, retainedUser) }
}
