package ru.omnicio.app.data.tinvest

import java.net.HttpURLConnection
import java.net.URI
import javax.net.ssl.HttpsURLConnection

sealed interface TInvestTokenCheck {
    data object Valid : TInvestTokenCheck
    data object Invalid : TInvestTokenCheck
    data class Unavailable(val message: String) : TInvestTokenCheck
}

class TInvestApiClient {
    fun checkReadAccess(token: String): TInvestTokenCheck {
        val normalized = token.trim()
        if (normalized.isEmpty()) {
            return TInvestTokenCheck.Invalid
        }

        val connection = runCatching {
            (URI.create(GET_ACCOUNTS_URL).toURL().openConnection() as HttpsURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = CONNECT_TIMEOUT_MS
                readTimeout = READ_TIMEOUT_MS
                doOutput = true
                setRequestProperty("Authorization", "Bearer $normalized")
                setRequestProperty("Content-Type", "application/json")
                setRequestProperty("Accept", "application/json")
            }
        }.getOrElse {
            return TInvestTokenCheck.Unavailable("Не удалось подготовить защищённое соединение.")
        }

        return try {
            connection.outputStream.use { stream ->
                stream.write(EMPTY_REQUEST.toByteArray(Charsets.UTF_8))
            }

            when (connection.responseCode) {
                HttpURLConnection.HTTP_OK -> TInvestTokenCheck.Valid
                HttpURLConnection.HTTP_UNAUTHORIZED,
                HttpURLConnection.HTTP_FORBIDDEN -> TInvestTokenCheck.Invalid
                HttpURLConnection.HTTP_CLIENT_TIMEOUT,
                HTTP_TOO_MANY_REQUESTS,
                HttpURLConnection.HTTP_INTERNAL_ERROR,
                HttpURLConnection.HTTP_BAD_GATEWAY,
                HttpURLConnection.HTTP_UNAVAILABLE,
                HttpURLConnection.HTTP_GATEWAY_TIMEOUT -> {
                    TInvestTokenCheck.Unavailable(
                        "T‑Invest API временно недоступен. Попробуйте ещё раз позже.",
                    )
                }
                else -> {
                    TInvestTokenCheck.Unavailable(
                        "T‑Invest API вернул код ${connection.responseCode}.",
                    )
                }
            }
        } catch (_: Exception) {
            TInvestTokenCheck.Unavailable(
                "Не удалось связаться с T‑Invest API. Проверьте интернет-соединение.",
            )
        } finally {
            connection.disconnect()
        }
    }

    private companion object {
        const val GET_ACCOUNTS_URL =
            "https://invest-public-api.tbank.ru/rest/tinkoff.public.invest.api.contract.v1.UsersService/GetAccounts"
        const val EMPTY_REQUEST = "{}"
        const val CONNECT_TIMEOUT_MS = 10_000
        const val READ_TIMEOUT_MS = 15_000
        const val HTTP_TOO_MANY_REQUESTS = 429
    }
}
