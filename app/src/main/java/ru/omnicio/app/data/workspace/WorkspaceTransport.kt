package ru.omnicio.app.data.workspace

import org.json.JSONObject

/** Production transport is HTTPS. A debug source set may provide an isolated deterministic test implementation. */
interface WorkspaceTransport {
    fun request(token: String, path: String, method: String = "GET", body: JSONObject? = null): VolumeReply
}
