package ru.omnicio.app.ui.workspace

import org.json.JSONObject

enum class AutoSaveKind { Notifications, Strategy, Analysis, Goal }
enum class AutoSavePhase { Pending, Invalid, Saving, Saved, Failed }
data class AutoSaveKey(val kind: AutoSaveKind, val documentId: String = "")

data class AutoSaveRecord(val kind: AutoSaveKind, val revision: Long, val baseline: String,
    val draft: String, val version: Int, val valid: Boolean, val phase: AutoSavePhase,
    val error: String? = null, val documentId: String = "") {
    val key: AutoSaveKey get() = AutoSaveKey(kind, documentId)
}

/** Stable comparison ignores JSON key order, without coercing source values. */
internal fun equivalentJson(a: Any?, b: Any?): Boolean = when {
    a === JSONObject.NULL || b === JSONObject.NULL -> a === b
    a == null || b == null -> a == null && b == null
    a is JSONObject && b is JSONObject -> a.keys().asSequence().toSet() == b.keys().asSequence().toSet() && a.keys().asSequence().all { equivalentJson(a.opt(it), b.opt(it)) }
    a is org.json.JSONArray && b is org.json.JSONArray -> a.length() == b.length() &&
        (0 until a.length()).all { equivalentJson(a.opt(it), b.opt(it)) }
    a is Number && b is Number -> {
        val left = a.toString().toBigDecimalOrNull(); val right = b.toString().toBigDecimalOrNull()
        left != null && right != null && left.compareTo(right) == 0
    }
    else -> a == b
}

/** Carry only the user's changed leaves onto the latest server document. */
internal fun mergeAutoSaveChanges(baseline: JSONObject, draft: JSONObject, latest: JSONObject): JSONObject {
    val result = JSONObject(latest.toString())
    (baseline.keys().asSequence().toSet() + draft.keys().asSequence().toSet()).forEach { key ->
        if (!equivalentJson(baseline.opt(key), draft.opt(key))) {
            if (!draft.has(key)) result.remove(key)
            else if (baseline.opt(key) is JSONObject && draft.opt(key) is JSONObject && latest.opt(key) is JSONObject)
                result.put(key, mergeAutoSaveChanges(baseline.getJSONObject(key), draft.getJSONObject(key), latest.getJSONObject(key)))
            else result.put(key, draft.opt(key))
        }
    }
    return result
}

/** An old acknowledgement advances the base but never replaces a newer edit. */
internal fun acknowledgeAutoSave(current: AutoSaveRecord, sent: AutoSaveRecord,
    confirmed: JSONObject, version: Int): AutoSaveRecord {
    require(current.key == sent.key && version >= 0)
    val value = if (current.revision == sent.revision) confirmed else
        mergeAutoSaveChanges(JSONObject(sent.draft), JSONObject(current.draft), confirmed)
    val pending = current.revision != sent.revision
    return current.copy(baseline = confirmed.toString(), draft = value.toString(), version = version,
        phase = if (pending) { if (current.valid) AutoSavePhase.Pending else AutoSavePhase.Invalid } else AutoSavePhase.Saved,
        error = null)
}

/** An uncertain command keeps its identity, but another document cannot bypass its retry delay. */
internal fun nextAutoSaveRecord(records: Collection<AutoSaveRecord>, recovery: AutoSaveRecord?): AutoSaveRecord? {
    if (recovery != null) {
        val current = records.firstOrNull { it.key == recovery.key } ?: return null
        return recovery.takeUnless { current.phase == AutoSavePhase.Failed }
    }
    return records.firstOrNull { it.phase == AutoSavePhase.Pending && it.valid }
}
