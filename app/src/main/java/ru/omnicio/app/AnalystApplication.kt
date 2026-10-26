package ru.omnicio.app

import android.app.Application
import ru.omnicio.app.data.diagnostics.ClientDiagnostics
import ru.omnicio.app.ui.theme.storedApplicationTheme
import ru.omnicio.app.ui.theme.syncSavedApplicationTheme

/** Version checking is owned by MandatoryUpdateHost, never a second lifecycle callback. */
class AnalystApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        ClientDiagnostics.install(this)
        syncSavedApplicationTheme(this, storedApplicationTheme(this))
    }
}
