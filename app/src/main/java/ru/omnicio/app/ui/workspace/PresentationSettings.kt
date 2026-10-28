package ru.omnicio.app.ui.workspace

import org.json.JSONObject

/** The wire format contains settings only; credentials and investment rules never enter it. */
internal fun WorkspacePreferences.toSettings(): JSONObject = JSONObject()
    .put("accent", accent.name).put("density", density.name).put("depth", depth)
    .put("hide_home_balance", hideHomeBalance).put("home_structure", homeStructure)
    .put("haptics", haptics).put("motion", motion.name).put("bright_light", brightLight)
    .put("screenshots_blocked", screenshotsBlocked)

internal fun presentationSettings(json: JSONObject?): WorkspacePreferences? = runCatching {
    requireNotNull(json)
    fun flag(key: String): Boolean = json.opt(key) as? Boolean ?: error("invalid_setting")
    fun word(key: String): String = json.opt(key) as? String ?: error("invalid_setting")
    WorkspacePreferences(AccentStyle.valueOf(word("accent")), InterfaceDensity.valueOf(word("density")),
        flag("depth"), flag("hide_home_balance"), flag("home_structure"), flag("haptics"),
        MotionLevel.valueOf(word("motion")), flag("bright_light"), flag("screenshots_blocked"))
}.getOrNull()

internal data class PresentationSnapshot(val version: Long, val value: WorkspacePreferences) {
    companion object {
        fun parse(json: JSONObject?): PresentationSnapshot? {
            if (json?.opt("schema_version") != 1) return null
            val number = json.opt("version")
            if (number !is Int && number !is Long) return null
            val version = (number as Number).toLong()
            if (version !in 0..9_007_199_254_740_991L) return null
            return presentationSettings(json.optJSONObject("settings"))?.let { PresentationSnapshot(version, it) }
        }
    }
}

internal fun mergeSettings(base: JSONObject, patch: JSONObject): JSONObject =
    JSONObject(base.toString()).also { result -> patch.keys().forEach { key -> result.put(key, patch.get(key)) } }

internal fun settingsDifference(before: JSONObject, after: JSONObject): JSONObject =
    JSONObject().also { result -> after.keys().forEach { key ->
        if (before.opt(key) != after.get(key)) result.put(key, after.get(key))
    } }

/** A response for an older request must not erase edits made while that request was in flight. */
internal fun acknowledgeSettings(pending: JSONObject, sent: JSONObject): JSONObject =
    JSONObject(pending.toString()).also { result -> sent.keys().forEach { key ->
        if (result.opt(key) == sent.get(key)) result.remove(key)
    } }

internal fun restoredSettingsPatch(raw: String?): JSONObject {
    val patch = runCatching { JSONObject(raw ?: "{}") }.getOrNull() ?: return JSONObject()
    val defaults = WorkspacePreferences().toSettings()
    if (patch.keys().asSequence().any { !defaults.has(it) }) return JSONObject()
    return if (presentationSettings(mergeSettings(defaults, patch)) == null) JSONObject() else patch
}

/** A previous account's permissive cache never opens a capture window for an unknown account policy. */
internal fun screenCaptureBlocked(signedIn: Boolean, serverConfirmed: Boolean, preference: Boolean): Boolean =
    !signedIn || !serverConfirmed || preference

/** An appearance reset must preserve independently selected privacy and home settings. */
internal fun WorkspacePreferences.resetAppearance(): WorkspacePreferences = WorkspacePreferences(
    hideHomeBalance = hideHomeBalance, homeStructure = homeStructure, screenshotsBlocked = screenshotsBlocked)
