package ru.omnicio.app.ui.spectrum

import android.view.View
import android.view.Window
import android.view.WindowManager.LayoutParams.FLAG_ALT_FOCUSABLE_IM
import androidx.activity.compose.LocalActivity
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.platform.LocalWindowInfo
import androidx.compose.ui.window.DialogWindowProvider
import java.util.IdentityHashMap

private val editorWindowLeases = EditorWindowFlagLeases<Window>(
    flag = FLAG_ALT_FOCUSABLE_IM,
    readFlags = { it.attributes.flags },
    setFlags = { window, flags, mask -> window.setFlags(flags, mask) },
)

internal val LocalDialogImeHostHandoff = staticCompositionLocalOf<DialogImeHostHandoff?> { null }

/** Register this effect before Dialog's show effect, so its host cannot start a TYPE_NULL session. */
@Composable
internal fun rememberDialogImeHostHandoff(): DialogImeHostHandoff {
    val hostWindow = LocalView.current.enclosingDialogWindow() ?: LocalActivity.current?.window
    val handoff = remember(hostWindow) {
        DialogImeHostHandoff { hostWindow?.let { editorWindowLeases.acquire(it, releaseWhenPrepared = false) } ?: {} }
    }
    DisposableEffect(handoff) {
        handoff.acquire()
        onDispose { handoff.release() }
    }
    return handoff
}

/** The launched observation runs after child editors have registered their restoration holds. */
@Composable
internal fun DialogImeHostFocus(handoff: DialogImeHostHandoff) {
    val window = LocalWindowInfo.current
    LaunchedEffect(handoff, window.isWindowFocused) {
        if (window.isWindowFocused) handoff.windowReady()
    }
}

/** Defer this window's first IME connection until a restored native editor is ready. */
@Composable
internal fun rememberEditorImeHandoff(
    owner: String,
    pendingVisibleRestore: Boolean,
    view: View,
): EditorImeHandoff {
    val window = view.enclosingDialogWindow() ?: LocalActivity.current?.window
    val hostHandoff = LocalDialogImeHostHandoff.current
    val handoff = remember(window, owner, view, hostHandoff) {
        EditorImeHandoff(
            acquireLease = { window?.let { editorWindowLeases.acquire(it) } ?: {} },
            editorReady = { view.isFocused && view.onCheckIsTextEditor() },
            releasePrepared = { window?.let(editorWindowLeases::releasePrepared) },
            acquireHostLease = { hostHandoff?.holdForEditor() ?: {} },
        )
    }
    // Deliberately independent of enabled: loading may temporarily disable the saved editor.
    DisposableEffect(handoff, pendingVisibleRestore) {
        if (pendingVisibleRestore) handoff.acquire()
        onDispose { handoff.release() }
    }
    return handoff
}

private fun View.enclosingDialogWindow(): Window? {
    var ancestor = parent
    while (ancestor != null) {
        if (ancestor is DialogWindowProvider) return ancestor.window
        ancestor = ancestor.parent
    }
    return null
}

/** One restoration handoff; recomposition or a late cleanup cannot rearm a completed hold. */
internal class EditorImeHandoff(
    private val acquireLease: () -> (() -> Unit),
    private val editorReady: () -> Boolean,
    private val releasePrepared: () -> Unit,
    private val acquireHostLease: () -> (() -> Unit) = { {} },
) {
    private var acquired = false
    private var releaseLease: (() -> Unit)? = null
    private var releaseHostLease: (() -> Unit)? = null

    fun acquire() {
        if (acquired) return
        acquired = true
        // Even an already prepared editor still needs its target window to gain focus and show IME.
        releaseHostLease = acquireHostLease()
        // Focus callbacks may have prepared another editor before effects were remembered.
        if (editorReady()) releasePrepared() else releaseLease = acquireLease()
    }

    fun handoff(): Boolean {
        if (!editorReady()) return false
        releasePrepared()
        releaseEditorLease()
        return true
    }

    fun release() {
        releaseEditorLease()
        val release = releaseHostLease
        releaseHostLease = null
        release?.invoke()
    }

    private fun releaseEditorLease() {
        val release = releaseLease
        releaseLease = null
        release?.invoke()
    }
}

/** Keep the host ineligible until its modal window and any restored editor have taken over. */
internal class DialogImeHostHandoff(private val acquireLease: () -> (() -> Unit)) {
    private var acquired = false
    private var disposed = false
    private var windowHasFocus = false
    private var releaseLease: (() -> Unit)? = null
    private val pendingEditors = mutableSetOf<Any>()

    fun acquire() {
        if (acquired || disposed) return
        acquired = true
        if (!windowHasFocus || pendingEditors.isNotEmpty()) ensureLease()
    }

    fun holdForEditor(): () -> Unit {
        if (disposed) return {}
        val owner = Any()
        pendingEditors.add(owner)
        // Async data can mount a restored editor after the initially empty dialog gained focus.
        if (acquired) ensureLease()
        return {
            if (pendingEditors.remove(owner)) releaseIfReady()
        }
    }

    fun windowReady() {
        windowHasFocus = true
        releaseIfReady()
    }

    private fun releaseIfReady() {
        if (windowHasFocus && pendingEditors.isEmpty()) releaseCurrentLease()
    }

    fun release() {
        disposed = true
        pendingEditors.clear()
        releaseCurrentLease()
    }

    private fun ensureLease() {
        if (releaseLease == null) releaseLease = acquireLease()
    }

    private fun releaseCurrentLease() {
        val release = releaseLease
        releaseLease = null
        release?.invoke()
    }
}

/** Main-thread ownership of one flag, scoped by Window identity and lease generation. */
internal class EditorWindowFlagLeases<W : Any>(
    private val flag: Int,
    private val readFlags: (W) -> Int,
    private val setFlags: (W, Int, Int) -> Unit,
) {
    private class Owners(val originallySet: Boolean) {
        var editorCount = 0
        var protectedCount = 0
        var editorGeneration = Any()
    }

    private val owners = IdentityHashMap<W, Owners>()

    fun acquire(window: W, releaseWhenPrepared: Boolean = true): () -> Unit {
        val state = owners[window] ?: Owners(readFlags(window) and flag != 0).also {
            if (!it.originallySet) setFlags(window, flag, flag)
            owners[window] = it
        }
        val generation = state.editorGeneration
        if (releaseWhenPrepared) state.editorCount++ else state.protectedCount++
        var active = true
        return {
            if (active) {
                active = false
                if (owners[window] === state) {
                    if (!releaseWhenPrepared) state.protectedCount--
                    else if (state.editorGeneration === generation) state.editorCount--
                    releaseIfUnused(window, state)
                }
            }
        }
    }

    // A real editor can release preparation holds, but cannot redirect an open modal's host.
    fun releasePrepared(window: W) {
        val state = owners[window] ?: return
        state.editorCount = 0
        state.editorGeneration = Any()
        releaseIfUnused(window, state)
    }

    private fun releaseIfUnused(window: W, state: Owners) {
        if (state.editorCount == 0 && state.protectedCount == 0) {
            owners.remove(window)
            if (!state.originallySet) setFlags(window, 0, flag)
        }
    }
}
