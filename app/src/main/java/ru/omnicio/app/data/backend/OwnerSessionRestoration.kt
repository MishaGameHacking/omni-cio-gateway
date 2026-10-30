package ru.omnicio.app.data.backend

internal sealed interface OwnerSessionAccess {
    data class Password(val errorMessage: String? = null, val validatedAccessToken: String? = null) : OwnerSessionAccess
    data class Migration(val accessToken: String) : OwnerSessionAccess
    data class Restored(val accessToken: String, val user: AnalystUser) : OwnerSessionAccess
}

/** A saved credential is evidence to validate, never authorization from a cached user. */
internal fun restoreOwnerSessionAccess(
    storedToken: String?,
    passwordRequested: Boolean,
    validate: (String) -> BackendResult<AnalystUser>,
    status: () -> BackendResult<OwnerAccessStatus>,
    clearInvalidSession: () -> Unit,
): OwnerSessionAccess {
    if (storedToken == null) return OwnerSessionAccess.Password()
    val user = when (val result = validate(storedToken)) {
        is BackendResult.Success -> result.value
        is BackendResult.Failure -> {
            if (result.statusCode in setOf(401, 403)) clearInvalidSession()
            return OwnerSessionAccess.Password(result.message)
        }
    }
    return when (val result = status()) {
        is BackendResult.Failure -> OwnerSessionAccess.Password(result.message)
        is BackendResult.Success -> when {
            !result.value.configured -> OwnerSessionAccess.Migration(storedToken)
            passwordRequested -> OwnerSessionAccess.Password(validatedAccessToken = storedToken)
            else -> OwnerSessionAccess.Restored(storedToken, user)
        }
    }
}
