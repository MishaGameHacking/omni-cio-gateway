package ru.omnicio.app

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity

/** One exported entry point. The actual, non-bypassable gate lives inside MainActivity. */
class BootstrapActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        forward(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        forward(intent)
    }

    private fun forward(incoming: Intent) {
        val next = Intent(this, MainActivity::class.java).apply {
            // Preserve only the documented Telegram return. External extras cannot
            // turn off version checks, impersonate a session, or change an endpoint.
            incoming.data?.takeIf { it.scheme == "analystai" && it.host == "auth" }?.let {
                data = it
                action = Intent.ACTION_VIEW
            }
            addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        }
        startActivity(next)
        finish()
    }
}
