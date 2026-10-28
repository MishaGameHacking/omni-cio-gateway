package ru.omnicio.app.data.notifications

/** Platform scheduling can be refused; that is a delivery failure, not a fatal UI event. */
internal object NotificationScheduling {
    fun attempt(schedule: () -> Boolean): Boolean = try {
        schedule()
    } catch (_: SecurityException) {
        false
    } catch (_: IllegalStateException) {
        false
    } catch (_: IllegalArgumentException) {
        false
    }
}
