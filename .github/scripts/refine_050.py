"""Apply fixed source edits to the checked-out feature tree; never run against main."""
from pathlib import Path
import re

ROOT = Path.cwd()
APP = ROOT / 'app/src/main/java/ru/omnicio/app'


def change(path, function):
    old = path.read_text(encoding='utf-8')
    new = function(old)
    if old == new:
        raise RuntimeError('Expected change missing: ' + str(path))
    path.write_bytes(new.replace('\r\n', '\n').encode('utf-8'))


change(ROOT / 'backend/requirements.txt', lambda text: text.rstrip() + '\ntzdata==2026.5\n')
change(ROOT / 'app/src/debug/AndroidManifest.xml', lambda text: text.replace('<application>', '<application android:allowBackup="false" android:usesCleartextTraffic="false">'))
change(APP / 'ui/theme/AnalystTheme.kt', lambda text: text.replace('    SideEffect {', '    SideEffect {\n        (context as? ComponentActivity)?.window?.isNavigationBarContrastEnforced = false'))
for name in ['ui/auth/TelegramLoginScreen.kt', 'ui/profile/TApiScreen.kt']:
    change(APP / name, lambda text: text.replace('contentColor = Color.White', 'contentColor = MaterialTheme.colorScheme.onPrimary').replace('color = Color.White', 'color = MaterialTheme.colorScheme.onPrimary'))


def screen(text):
    begin = text.index('                if (snapshot == null) {')
    finish = text.index('                    item(key = "total") {', begin)
    text = text[:begin] + '''                if (snapshot == null) {
                    item(key = "initial-state") { InitialPortfolioState(state, onProfileClick) }
                } else {
''' + text[finish:]
    begin = text.index('                    item(key = "total") {')
    finish = text.index('                    if (snapshot.accounts.isEmpty())', begin)
    text = text[:begin] + '''                    item(key = "total") {
                        PortfolioSummary(snapshot, selectedCurrency, refreshing, refreshError, lastUpdatedMillis, onCurrencyClick) { target ->
                            if (snapshot.accounts.size == 1) {
                                accountId = snapshot.accounts.first().id
                                section = target
                            } else selectForSection = target
                        }
                    }
''' + text[finish:]
    text = text.replace('snapshot?.asOf, refreshError,', 'snapshot.asOf, refreshError,')
    text += '''

@Composable
private fun InitialPortfolioState(state: PortfolioUiState, onProfile: () -> Unit) {
    CompactCard {
        when (state) {
            PortfolioUiState.Loading -> {
                CircularProgressIndicator(Modifier.size(24.dp), strokeWidth = 2.dp)
                Text("Получаем ваш портфель…")
            }
            is PortfolioUiState.Error -> {
                Text(state.message)
                Notice("Повторная проверка выполняется автоматически, пока приложение открыто.")
            }
            else -> {
                SectionHeading("Подключите T‑API")
                Notice("Счета и позиции появятся после подключения вашего read-only токена. Демонстрационных сумм здесь нет.")
                TextButton(onClick = onProfile) { Text("Открыть профиль") }
            }
        }
    }
}

@Composable
private fun PortfolioSummary(
    snapshot: PortfolioSnapshot, selectedCurrency: PortfolioCurrency, refreshing: Boolean,
    error: String?, lastUpdatedMillis: Long?, onCurrency: () -> Unit, openSection: (Int) -> Unit,
) {
    CompactCard {
        Text(snapshot.totalValue.moneyText(), Modifier.clickable(onClick = onCurrency), fontSize = 32.sp, fontWeight = FontWeight.Bold)
        snapshot.expectedYieldPercent?.let {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                NoticeInline("Текущая доходность API")
                SignedAmount(null, it)
            }
        }
        val waiting = refreshing && snapshot.totalValue.currency != selectedCurrency.name
        Notice(if (waiting) "Получаем оценку в ${selectedCurrency.name}…" else "Нажмите на сумму: ₽ → $ → €")
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf(OperationsTitle to 1, AnalyticsTitle to 3).forEach { (title, target) ->
                FilledTonalButton(modifier = Modifier.weight(1f), onClick = { openSection(target) },
                    enabled = snapshot.accounts.isNotEmpty(), contentPadding = PaddingValues(8.dp)) { Text(title) }
            }
        }
        val observed = snapshot.asOf ?: lastUpdatedMillis?.let { java.time.Instant.ofEpochMilli(it).toString() }
        Notice(error ?: "Получено ${dateText(observed)} · автообновление")
    }
}
'''
    for literal, constant in [('Операции', 'OperationsTitle'), ('Аналитика', 'AnalyticsTitle'), ('Денежные средства', 'CashTitle')]:
        text = text.replace('"' + literal + '"', constant)
    return text.replace('@Composable\nfun PortfolioScreen', 'private const val OperationsTitle = "Операции"\nprivate const val AnalyticsTitle = "Аналитика"\nprivate const val CashTitle = "Денежные средства"\n\n@Composable\nfun PortfolioScreen', 1)


change(APP / 'ui/portfolio/PortfolioScreen.kt', screen)


def backend_details(text):
    errors = '''READ_ERRORS = {
    400: {"description": "Invalid date range"},
    401: {"description": "Session required or expired"},
    404: {"description": "Account unavailable to this user"},
    409: {"description": "T-Invest token not connected"},
    422: {"description": "Invalid request or broker access"},
    500: {"description": "Stored token unreadable"},
    502: {"description": "Invalid broker response"},
    503: {"description": "Broker temporarily unavailable"},
    504: {"description": "Broker timeout"},
}
router = APIRouter()'''
    text = text.replace('router = APIRouter()', errors)
    text = re.sub(r'@router.get\(("[^"\n]+")\)', r'@router.get(\1, responses=READ_ERRORS)', text)
    text = text.replace('DO UPDATE SET observed_at=excluded.observed_at,value=excluded.value"""',
                        'DO UPDATE SET observed_at=excluded.observed_at,value=excluded.value\n                    WHERE excluded.observed_at >= portfolio_value_history.observed_at"""')
    text = text.replace('resolution = "intraday" if span <= timedelta(days=2) else "hour" if span <= timedelta(days=32) else "day"',
        'resolution = "day"\n    if span <= timedelta(days=2):\n        resolution = "intraday"\n    elif span <= timedelta(days=32):\n        resolution = "hour"')
    begin = text.index('def payment_rows(')
    end = text.index('\ndef load_payments(', begin)
    text = text[:begin] + '''def payment_rows(raw: dict, position: dict, kind: str, now: datetime) -> list[dict]:
    result = []
    for event in raw.get("events" if kind == "bond" else "dividends", []):
        row = payment_row(event, position, kind, now)
        if row is not None:
            result.append(row)
    return result


def payment_estimate(per_unit: dict | None, quantity: Decimal | None, unknown: bool, payment_date: str | None) -> dict | None:
    if per_unit is None or quantity is None or quantity <= 0 or unknown or not payment_date:
        return None
    return portfolio._money_payload(number(per_unit["value"]) * quantity, per_unit["currency"])


def payment_row(event: dict, position: dict, kind: str, now: datetime) -> dict | None:
    if str(event.get("dividendType", "")).lower() == "cancelled":
        return None
    amount_field, date_field, record_field = "dividendNet", "paymentDate", "recordDate"
    if kind == "bond":
        amount_field, date_field, record_field = "payOneBond", "couponDate", "fixDate"
    per_unit = money(event.get(amount_field))
    payment_date = event.get(date_field)
    record_date = event.get(record_field)
    display_date = payment_date or record_date
    if not display_date or display_date[:10] < now.date().isoformat():
        return None
    eligibility_unknown = not record_date or record_date[:10] <= now.date().isoformat()
    estimate = payment_estimate(per_unit, number(position.get("quantity")), eligibility_unknown, payment_date)
    return {"instrumentUid": position.get("instrumentUid"), "title": position.get("ticker") or position.get("figi"),
            "kind": "coupon" if kind == "bond" else "dividend", "date": display_date,
            "recordDate": record_date, "perUnit": per_unit, "estimate": estimate,
            "dateUnknown": not bool(payment_date), "eligibilityUnknown": eligibility_unknown}

''' + text[end:]
    return text


change(ROOT / 'backend/portfolio_details.py', backend_details)
change(ROOT / 'backend/autonomous_ai.py', lambda text: text.replace('    digest, material_digest = _save_snapshot(user_id, snapshot)', '''    # Archive the already fetched RUB valuation even when no LLM analysis is needed.
    try:
        from .portfolio_details import record_history
    except ImportError:
        from portfolio_details import record_history
    record_history(user_id, snapshot.get("accounts", []), current_time.astimezone(UTC).isoformat())
    digest, material_digest = _save_snapshot(user_id, snapshot)'''))


def test_dates(text):
    text = text.replace('        with self.assertRaises(HTTPException):\n            details.period_bounds(date(2024, 2, 2), date(2024, 2, 1), {})',
        '        first, last = date(2024, 2, 2), date(2024, 2, 1)\n        with self.assertRaises(HTTPException):\n            details.period_bounds(first, last, {})')
    return text.replace('        with self.assertRaises(HTTPException):\n            details.period_bounds(date(2035, 1, 1), date(2035, 1, 2), {})',
        '        first, last = date(2035, 1, 1), date(2035, 1, 2)\n        with self.assertRaises(HTTPException):\n            details.period_bounds(first, last, {})')


change(ROOT / 'backend/tests/test_portfolio_details.py', test_dates)


def hook(text):
    target = '        print("ACTIVITY_LAUNCH=success", flush=True)'
    assert target in text
    return text.replace(target, target + '''
        if args.api == 33 and os.getenv("RUN_PROFILE_UI_TESTS") == "1":
            from profile_ui_probe import exercise
            debug_apk = Path(__file__).resolve().parents[2] / "app/build/outputs/apk/debug/app-debug.apk"
            install("debug_ui_fixture_install", debug_apk, update=True)
            exercise(device)
            results.append({"test": "profile_ui", "success": True})''')


change(ROOT / '.github/scripts/test_apk_installation.py', hook)

# Store LF bytes in Git, regardless of the self-hosted runner checkout configuration.
for directory in [ROOT / 'backend', ROOT / 'app/src', ROOT / '.github/scripts']:
    for path in directory.rglob('*'):
        if path.is_file() and path.suffix in {'.py', '.kt', '.xml'}:
            raw = path.read_bytes()
            if b'\r\n' in raw:
                path.write_bytes(raw.replace(b'\r\n', b'\n'))
print('QUALITY_REFINEMENTS_COMPLETE')
