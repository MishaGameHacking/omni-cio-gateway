package ru.omnicio.app.ui.spectrum

import android.view.View
import android.view.Window
import android.view.WindowManager.LayoutParams.FLAG_ALT_FOCUSABLE_IM
import androidx.activity.compose.LocalActivity
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.window.DialogWindowProvider
import java.util.IdentityHashMap

private val editorWindowLeases = EditorWindowFlagLeases<Window>(
    flag = FLAG_ALT_FOCUSABLE_IM,
    readFlags = { it.attributes.flags },
    setFlags = { window, flags, mask -> window.setFlags(flags, mask) },
)

/** Defer this window's first IME connection until a restored native editor is ready. */
@Composable
internal fun rememberEditorImeHandoff(
    owner: String,
    pendingVisibleRestore: Boolean,
    view: View,
): EditorImeHandoff {
    val window = view.enclosingDialogWindow() ?: LocalActivity.current?.window
    val handoff = remember(window, owner, view) {
        EditorImeHandoff(
            acquireLease = { window?.let(editorWindowLeases::acquire) ?: {} },
            editorReady = { view.isFocused && view.onCheckIsTextEditor() },
            releasePrepared = { window?.let(editorWindowLeases::releasePrepared) },
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
) {
    private var acquired = false
    private var releaseLease: (() -> Unit)? = null

    fun acquire() {
        if (acquired) return
        acquired = true
        // Focus callbacks may have prepared another editor before effects were remembered.
        if (editorReady()) releasePrepared() else releaseLease = acquireLease()
    }

    fun handoff(): Boolean {
        if (!editorReady()) return false
        releasePrepared()
        release()
        return true
    }

    fun release() {
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
    private class Owners(val originallySet: Boolean, var count: Int = 0)

    private val owners = IdentityHashMap<W, Owners>()

    fun acquire(window: W): () -> Unit {
        val state = owners[window] ?: Owners(readFlags(window) and flag != 0).also {
            if (!it.originallySet) setFlags(window, flag, flag)
            owners[window] = it
        }
        state.count++
        var active = true
        return {
            if (active) {
                active = false
                if (owners[window] === state) {
                    state.count--
                    if (state.count == 0) releasePrepared(window)
                }
            }
        }
    }

    // Any real editor can take over this window; a disabled pending editor must not block it.
    fun releasePrepared(window: W) {
        val state = owners.remove(window) ?: return
        if (!state.originallySet) setFlags(window, 0, flag)
    }
}
