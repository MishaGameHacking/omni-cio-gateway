package ru.omnicio.app.data.settings

import android.content.Context

class AppSettingsStore(context: Context) {
    private val preferences =
        context.applicationContext.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)

    fun screenshotsBlocked(): Boolean =
        preferences.getBoolean(KEY_SCREENSHOTS_BLOCKED, false)

    fun setScreenshotsBlocked(blocked: Boolean) {
        preferences.edit()
            .putBoolean(KEY_SCREENSHOTS_BLOCKED, blocked)
            .apply()
    }

    private companion object {
        const val PREFERENCES_NAME = "analyst_ai_settings"
        const val KEY_SCREENSHOTS_BLOCKED = "screenshots_blocked"
    }
}
