package ru.omnicio.app.data.updates

import android.content.Context

internal class UpdateCheckStore(context: Context) {
    private val preferences = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)

    fun shouldCheck(nowMillis: Long = System.currentTimeMillis()): Boolean {
        if (preferences.getBoolean(KEY_POLICY_BLOCKED, false)) return true
        if (preferences.getBoolean(KEY_INSTALLING, false)) return false
        val lastAttempt = preferences.getLong(KEY_LAST_ATTEMPT, 0L)
        return nowMillis - lastAttempt >= CHECK_INTERVAL_MILLIS
    }

    fun setPolicyBlocked(blocked: Boolean) {
        preferences.edit().putBoolean(KEY_POLICY_BLOCKED, blocked).commit()
    }

    fun isPolicyBlocked(): Boolean = preferences.getBoolean(KEY_POLICY_BLOCKED, false)

    fun markAttempt(nowMillis: Long = System.currentTimeMillis()) {
        preferences.edit().putLong(KEY_LAST_ATTEMPT, nowMillis).apply()
    }

    fun cacheRelease(release: AppRelease, nowMillis: Long = System.currentTimeMillis()) {
        preferences.edit()
            .putString(KEY_RELEASE, release.toJson())
            .putLong(KEY_RELEASE_RECEIVED, nowMillis)
            .apply()
    }

    fun cachedRelease(
        nowMillis: Long = System.currentTimeMillis(),
        allowExpired: Boolean = false,
    ): AppRelease? {
        val received = preferences.getLong(KEY_RELEASE_RECEIVED, 0L)
        if (received <= 0L || (!allowExpired && nowMillis - received > MAX_CACHE_AGE_MILLIS)) return null
        val raw = preferences.getString(KEY_RELEASE, null) ?: return null
        return runCatching { AppRelease.parse(raw) }.getOrNull()
    }

    fun markInstalling(expectedVersion: Long) {
        preferences.edit()
            .putBoolean(KEY_INSTALLING, true)
            .putLong(KEY_EXPECTED_VERSION, expectedVersion)
            .remove(KEY_INSTALL_ERROR)
            .apply()
    }

    fun markInstallFinished(error: String? = null) {
        preferences.edit()
            .putBoolean(KEY_INSTALLING, false)
            .putString(KEY_INSTALL_ERROR, error)
            .apply()
    }

    fun isInstalling(): Boolean = preferences.getBoolean(KEY_INSTALLING, false)

    fun expectedVersion(): Long = preferences.getLong(KEY_EXPECTED_VERSION, 0L)

    fun consumeInstallError(): String? {
        val value = preferences.getString(KEY_INSTALL_ERROR, null)
        if (value != null) preferences.edit().remove(KEY_INSTALL_ERROR).apply()
        return value
    }

    companion object {
        private const val PREFERENCES = "analyst_ai_updates"
        private const val KEY_LAST_ATTEMPT = "last_attempt"
        private const val KEY_RELEASE = "release"
        private const val KEY_RELEASE_RECEIVED = "release_received"
        private const val KEY_INSTALLING = "installing"
        private const val KEY_EXPECTED_VERSION = "expected_version"
        private const val KEY_INSTALL_ERROR = "install_error"
        private const val KEY_POLICY_BLOCKED = "policy_blocked"
        private const val CHECK_INTERVAL_MILLIS = 15L * 60L * 1_000L
        private const val MAX_CACHE_AGE_MILLIS = 7L * 24L * 60L * 60L * 1_000L
    }
}
