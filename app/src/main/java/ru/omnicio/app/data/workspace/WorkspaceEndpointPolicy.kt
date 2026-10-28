package ru.omnicio.app.data.workspace

import java.net.URI

/** Keep newly added controller reads on the same authenticated application origin. */
internal object WorkspaceEndpointPolicy {
    private val automationPaths = setOf(
        "/automation/status",
        "/automation/preferences",
        "/automation/decisions",
    )

    fun permits(path: String): Boolean {
        val allowed = path == "/workspace" || path.startsWith("/workspace/") ||
            path.startsWith("/workspace?") || path == "/analysis/profile" || path in automationPaths
        if (!allowed || '#' in path) return false
        return try {
            val uri = URI(path)
            uri.scheme == null && uri.authority == null && uri.path?.contains("..") == false
        } catch (_: Exception) {
            false
        }
    }
}
