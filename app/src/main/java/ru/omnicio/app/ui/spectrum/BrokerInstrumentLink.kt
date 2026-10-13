package ru.omnicio.app.ui.spectrum

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri

/** Result never claims an order or even that a specific brokerage app was opened. */
sealed interface BrokerOpenResult {
    data object AppHandlerOpened : BrokerOpenResult
    data object NoAppHandler : BrokerOpenResult
    data object InvalidLink : BrokerOpenResult
}

/** trustedUrl comes from a verified instrument registry, never model-generated text.
 * No guessed private scheme, package or order parameters; let Android resolve app links.
 * For NoAppHandler the caller offers explicit browser choice and copy ticker/ISIN.
 */
fun openInstrumentInApp(activity: Activity, trustedUrl: String): BrokerOpenResult {
    val uri = Uri.parse(trustedUrl)
    val safePath = Regex("/invest/(stocks|bonds|etfs|currencies)/[A-Za-z0-9@_.-]{1,80}/")
    if (trustedUrl.length > 512 || uri.scheme != "https" || uri.encodedAuthority != "www.tbank.ru" ||
        uri.query != null || uri.fragment != null || !safePath.matches(uri.path.orEmpty()) ||
        uri.pathSegments.any { it == "." || it == ".." }
    ) return BrokerOpenResult.InvalidLink
    val intent = Intent(Intent.ACTION_VIEW, uri)
        .addCategory(Intent.CATEGORY_BROWSABLE)
        .addFlags(Intent.FLAG_ACTIVITY_REQUIRE_NON_BROWSER)
    return try {
        activity.startActivity(intent)
        BrokerOpenResult.AppHandlerOpened
    } catch (_: ActivityNotFoundException) {
        BrokerOpenResult.NoAppHandler
    } catch (_: SecurityException) {
        BrokerOpenResult.NoAppHandler
    }
}
