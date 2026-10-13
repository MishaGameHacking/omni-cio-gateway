package ru.omnicio.app

import android.app.Activity
import android.app.Application
import android.content.Intent
import android.os.Bundle
import ru.omnicio.app.data.updates.UpdateCheckStore

class AnalystApplication : Application(), Application.ActivityLifecycleCallbacks {
    override fun onCreate() {
        super.onCreate()
        registerActivityLifecycleCallbacks(this)
    }

    override fun onActivityResumed(activity: Activity) {
        if (activity !is MainActivity) return
        val store = UpdateCheckStore(this)
        if (!store.shouldCheck()) return
        store.markAttempt()
        activity.startActivity(
            Intent(activity, BootstrapActivity::class.java).apply {
                putExtra(BootstrapActivity.EXTRA_RESUME_CHECK, true)
            },
        )
    }

    override fun onActivityCreated(activity: Activity, savedInstanceState: Bundle?) = Unit
    override fun onActivityStarted(activity: Activity) = Unit
    override fun onActivityPaused(activity: Activity) = Unit
    override fun onActivityStopped(activity: Activity) = Unit
    override fun onActivitySaveInstanceState(activity: Activity, outState: Bundle) = Unit
    override fun onActivityDestroyed(activity: Activity) = Unit
}
