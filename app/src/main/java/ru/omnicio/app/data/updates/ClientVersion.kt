package ru.omnicio.app.data.updates

import java.net.HttpURLConnection
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import ru.omnicio.app.BuildConfig

object ClientVersion {
    private val mutableBlocked = MutableStateFlow(false)
    val blocked: StateFlow<Boolean> = mutableBlocked

    fun attach(connection: HttpURLConnection) {
        connection.instanceFollowRedirects = false
        connection.setRequestProperty("X-Analyst-Package", BuildConfig.APPLICATION_ID)
        connection.setRequestProperty("X-Analyst-Version-Code", BuildConfig.VERSION_CODE.toString())
    }

    fun observeStatus(status: Int) {
        if (status == 426) mutableBlocked.value = true
    }

    fun verifiedCurrent() { mutableBlocked.value = false }
}
