"""One-time, fixed-path source integration; removed before merging the feature PR."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'app/src/main/java/ru/omnicio/app'


def edit(path, change):
    old = path.read_text(encoding='utf-8')
    new = change(old)
    if old == new:
        raise RuntimeError('Expected source modification missing: ' + str(path.relative_to(ROOT)))
    path.write_text(new, encoding='utf-8')
    print('UPDATED ' + str(path.relative_to(ROOT)))


def main_activity(text):
    text = text.replace('import ru.omnicio.app.ui.portfolio.PortfolioScreen',
        'import ru.omnicio.app.ui.theme.AnalystTheme\nimport ru.omnicio.app.data.portfolio.rememberLivePortfolio\nimport ru.omnicio.app.ui.portfolio.PortfolioScreen')
    text = re.sub(r'    var portfolioState by remember \{ mutableStateOf<PortfolioUiState>\(PortfolioUiState.NotConnected\) \}\n', '', text)
    start = text.index('    LaunchedEffect(signedIn?.accessToken, tApiConfigured, portfolioCurrency) {')
    end = text.index('    MaterialTheme {', start)
    text = text[:start] + '''    val livePortfolio = rememberLivePortfolio(signedIn?.accessToken, tApiConfigured, portfolioCurrency)
    val portfolioState = livePortfolio.state

''' + text[end:]
    text = text.replace('    MaterialTheme {', '    AnalystTheme {')
    text = text.replace('                                state = portfolioState,', '''                                state = portfolioState,
                                accessToken = current.accessToken,
                                refreshing = livePortfolio.refreshing,
                                refreshError = livePortfolio.error,
                                lastUpdatedMillis = livePortfolio.lastSuccessMillis,''')
    text = re.sub(r'\s+if \(!configured\) \{\s+portfolioState = PortfolioUiState.NotConnected\s+\}', '', text)
    text = re.sub(r'^\s+portfolioState = PortfolioUiState.NotConnected\n', '', text, flags=re.M)
    if 'var portfolioState' in text or 'portfolioState =' in text.replace('val portfolioState =', ''):
        raise RuntimeError('Obsolete portfolio state remains')
    return text


edit(APP / 'MainActivity.kt', main_activity)


def profile(text):
    text = text.replace('import androidx.compose.foundation.layout.*', 'import androidx.compose.foundation.layout.*\nimport androidx.compose.foundation.rememberScrollState\nimport androidx.compose.foundation.verticalScroll')
    start = text.index('@Composable\nprivate fun InformationDialog')
    return text[:start] + '''@Composable
private fun InformationDialog(title: String, text: String, close: () -> Unit) {
    AlertDialog(onDismissRequest = close, title = { Text(title) },
        text = { Column(Modifier.verticalScroll(rememberScrollState())) { Text(text) } },
        confirmButton = { TextButton(onClick = close) { Text("Понятно") } })
}
'''


edit(APP / 'ui/profile/ProfileScreen.kt', profile)


def components(text):
    text = text.replace('import androidx.compose.foundation.Canvas', 'import androidx.compose.foundation.Canvas\nimport androidx.compose.foundation.verticalScroll')
    start = text.index('@Composable\nprivate fun Modifier.verticalScrollSafe')
    end = text.index('internal data class ChartSlice', start)
    text = text[:start] + text[end:]
    return text.replace('Modifier.verticalScrollSafe()', 'Modifier.verticalScroll(rememberScrollState())')


edit(APP / 'ui/portfolio/PortfolioComponents.kt', components)
edit(APP / 'ui/portfolio/PortfolioScreen.kt', lambda t: t.replace('snapshot.asOf, refreshError,', 'snapshot?.asOf, refreshError,'))
edit(APP / 'ui/theme/AnalystTheme.kt', lambda t: t.replace('ThemeMode.SYSTEM.name)!!', 'ThemeMode.SYSTEM.name) ?: ThemeMode.SYSTEM.name'))

# Existing screens must consume the root palette rather than hard-coded whites.
for path in (APP / 'ui').rglob('*.kt'):
    if path.name in {'AnalystTheme.kt', 'PortfolioComponents.kt'}:
        continue
    source = path.read_text(encoding='utf-8')
    updated = source
    roles = {'Background': 'background', 'Card': 'surface', 'Muted': 'onSurfaceVariant', 'Blue': 'primary', 'Red': 'error'}
    for suffix, role in roles.items():
        pattern = r'private val (\w*' + suffix + r') = (?:Color\(0x[0-9A-Fa-f]+\)|Color.White)'
        updated = re.sub(pattern, lambda match: 'private val ' + match.group(1) + ': Color\n    @Composable get() = MaterialTheme.colorScheme.' + role, updated)
    if path.name == 'AnalystBottomBar.kt':
        updated = updated.replace('modifier = modifier.navigationBarsPadding(),', 'modifier = modifier,')
        updated = updated.replace('color = Color.White,', 'color = MaterialTheme.colorScheme.surface,')
        updated = updated.replace('.fillMaxWidth()\n                .padding(horizontal', '.fillMaxWidth()\n                .navigationBarsPadding()\n                .padding(horizontal')
        updated = updated.replace('if (selected) Color(0xFF16191F) else Color(0xFF9298A2)', 'if (selected) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant')
    if path.name in {'AnalysisScreens.kt', 'TApiScreen.kt', 'TelegramLoginScreen.kt', 'PlaceholderTabScreen.kt'}:
        for literal, role in {'Color(0xFFF5F6F8)': 'background', 'Color(0xFF858C96)': 'onSurfaceVariant',
                              'Color(0xFF8A9099)': 'onSurfaceVariant', 'Color(0xFF16191F)': 'onSurface',
                              'Color(0xFF1C1D20)': 'onSurface', 'Color(0xFFE8EAED)': 'outlineVariant'}.items():
            # Avoid changing other global constants into non-composable initializers.
            updated = re.sub(r'(private val (\w+) = )' + re.escape(literal),
                lambda m: 'private val ' + m.group(2) + ': Color\n    @Composable get() = MaterialTheme.colorScheme.' + role, updated)
            updated = updated.replace(literal, 'MaterialTheme.colorScheme.' + role)
        updated = updated.replace('containerColor = Color.White', 'containerColor = MaterialTheme.colorScheme.surface')
    if updated != source:
        if 'import androidx.compose.material3.MaterialTheme' not in updated and 'import androidx.compose.material3.*' not in updated:
            updated = updated.replace('\n\nimport ', '\n\nimport androidx.compose.material3.MaterialTheme\nimport ', 1)
        path.write_text(updated, encoding='utf-8')
        print('THEMED ' + str(path.relative_to(ROOT)))

# Register authenticated read-only endpoints without changing OIDC/session handling.
edit(ROOT / 'backend/app.py', lambda t: t + '''

try:
    from .portfolio_details import router as portfolio_details_router
except ImportError:
    from portfolio_details import router as portfolio_details_router
app.include_router(portfolio_details_router)
''')


def details(text):
    text = text.replace('if not isinstance(value, dict) or "units" not in value:', 'if not isinstance(value, dict):')
    text = text.replace('str(value["units"])', 'str(value.get("units", 0))')
    text = text.replace('_cache: OrderedDict = OrderedDict()', '_cache: OrderedDict = OrderedDict()\n_public_cache: OrderedDict = OrderedDict()')
    text = text.replace('    def metadata(self, raw: dict) -> dict:', '    def metadata(self, raw: dict, budget: list[int] | None = None) -> dict:')
    start = text.index('        try:\n            return cached(("instrument"')
    end = text.index('\n\n\ndef position_value', start)
    text = text[:start] + '''        key = ("instrument", str(identifier))
        existing = public_lookup(key)
        if existing is not None:
            return existing
        if budget is not None:
            if budget[0] <= 0:
                return {}
            budget[0] -= 1
        try:
            value = self.read("instrument", {"idType": kind, "id": identifier}).get("instrument", {})
        except HTTPException:
            return {}
        public_store(key, value, 86400)
        return value


def public_lookup(key: tuple) -> dict | None:
    # Never acquire another single-flight stripe while serving a dashboard stripe.
    with _cache_lock:
        row = _public_cache.get(key)
        return copy.deepcopy(row[1]) if row and row[0] > time.monotonic() else None


def public_store(key: tuple, value: dict, ttl: int) -> None:
    with _cache_lock:
        _public_cache[key] = time.monotonic() + ttl, copy.deepcopy(value)
        _public_cache.move_to_end(key)
        while len(_public_cache) > 2048:
            _public_cache.popitem(last=False)
''' + text[end:]
    text = text.replace('        return portfolio._post_tinvest(self.client, BASE + METHODS[method], self.token, body)', '''        previous_timeout = self.client.timeout
        if method in {"instrument", "coupons", "dividends"}:
            self.client.timeout = backend.httpx.Timeout(3, connect=2)
        try:
            return portfolio._post_tinvest(self.client, BASE + METHODS[method], self.token, body)
        finally:
            self.client.timeout = previous_timeout''')
    text = text.replace('metadata = reader.metadata(item) if meta_budget[0] > 0 else {}\n        meta_budget[0] -= 1', 'metadata = reader.metadata(item, meta_budget)')
    text = text.replace('    rows.extend(cash_positions(balances))', '    rows.extend(supplement_positions(reader, rows, balances, meta_budget))\n    rows.extend(cash_positions(balances))')
    text = text.replace('metadata_budget = [40]', 'metadata_budget = [4]')
    text = text.replace('    if metadata_budget[0] < 0:', '    if any(not p.get("company") and p.get("instrumentType") != "cash" for a in accounts for p in a["positions"]):')
    start = text.index('\ndef read_account(')
    text = text[:start] + '''

def supplement_positions(reader: BrokerReader, rows: list[dict], balances: dict, budget: list[int]) -> list[dict]:
    """Do not drop exchange-blocked securities that GetPortfolio cannot value."""
    seen = {row["id"] for row in rows}
    extra = []
    for field, fallback_kind in (("securities", "security"), ("futures", "futures"), ("options", "option")):
        for item in balances.get(field, []):
            identifier = str(item.get("instrumentUid") or item.get("positionUid") or item.get("figi") or "")
            if not identifier or identifier in seen:
                continue
            seen.add(identifier)
            blocked = Decimal(str(item.get("blocked", 0)))
            quantity = Decimal(str(item.get("balance", 0))) + blocked
            raw = {**item, "instrumentType": item.get("instrumentType", fallback_kind),
                   "quantity": portfolio._decimal_payload(quantity),
                   "blocked": bool(item.get("exchangeBlocked")), "blockedLots": portfolio._decimal_payload(blocked)}
            extra.append(normalize_position(raw, reader.metadata(raw, budget)))
    return extra

''' + text[start:]
    text = text.replace('ORDER BY observed_at LIMIT 2000', 'ORDER BY observed_at LIMIT 2001')
    text = text.replace('"value": row["value"]} for row in rows]', '"value": row["value"]} for row in rows[:2000]], "historyTruncated": len(rows) > 2000')
    start = text.index('\ndef payment_rows(')
    end = text.index('\n\n@router.get("/tinvest/accounts/{account_id}/payments")', start)
    text = text[:start] + '''
def payment_rows(raw: dict, position: dict, kind: str, now: datetime) -> list[dict]:
    result = []
    for event in raw.get("events" if kind == "bond" else "dividends", []):
        if str(event.get("dividendType", "")).lower() == "cancelled":
            continue
        per_unit = money(event.get("payOneBond" if kind == "bond" else "dividendNet"))
        payment_date = event.get("couponDate" if kind == "bond" else "paymentDate")
        record_date = event.get("fixDate" if kind == "bond" else "recordDate")
        display_date = payment_date or record_date
        if not display_date or display_date[:10] < now.date().isoformat():
            continue
        quantity = number(position.get("quantity"))
        eligibility_unknown = not record_date or record_date[:10] <= now.date().isoformat()
        estimate = None
        if per_unit and quantity is not None and quantity > 0 and not eligibility_unknown and payment_date:
            estimate = portfolio._money_payload(number(per_unit["value"]) * quantity, per_unit["currency"])
        result.append({"instrumentUid": position.get("instrumentUid"), "title": position.get("ticker") or position.get("figi"),
                       "kind": "coupon" if kind == "bond" else "dividend", "date": display_date,
                       "recordDate": record_date, "perUnit": per_unit, "estimate": estimate,
                       "dateUnknown": not bool(payment_date), "eligibilityUnknown": eligibility_unknown})
    return result


def load_payments(user: Any, account_id: str) -> dict:
    now = datetime.now(timezone.utc)
    items, missing = [], 0
    budget = 4
    with BrokerReader(user) as reader:
        reader.account(account_id)
        raw = reader.read("portfolio", {"accountId": account_id, "currency": "RUB"})
        holdings = [p for p in raw.get("positions", []) if p.get("instrumentType") in {"share", "bond"}]
        for position in holdings:
            kind = position["instrumentType"]
            identifier = position.get("instrumentUid") or position.get("figi")
            key = ("payments", kind, identifier, now.date().isoformat())
            response = public_lookup(key)
            if response is None and budget > 0:
                budget -= 1
                body = {"instrumentId": identifier, "from": (now - timedelta(days=45)).isoformat(),
                        "to": (now + timedelta(days=365)).isoformat()}
                try:
                    response = reader.read("coupons" if kind == "bond" else "dividends", body)
                    public_store(key, response, 3600)
                except HTTPException:
                    response = None
            if response is None:
                missing += 1
            else:
                items.extend(payment_rows(response, position, kind, now))
    return {"items": sorted(items, key=lambda item: item["date"]), "complete": missing == 0,
            "asOf": iso_now(), "note": "Календарь опубликованных событий по текущим позициям. Оценка по количеству бумаг не гарантирует выплату. Право зависит от реестра, расчетов и будущих сделок. Сумма налога не прогнозируется."}
''' + text[end:]
    text = text.replace('account_id), 3600, lambda: load_payments', 'account_id), 60, lambda: load_payments')
    return text


edit(ROOT / 'backend/portfolio_details.py', details)
edit(ROOT / 'app/build.gradle.kts', lambda t: t.replace('versionCode = 20', 'versionCode = 21').replace('versionName = "0.4.2"', 'versionName = "0.5.0"'))
edit(ROOT / '.github/workflows/android-ci.yml', lambda t: t.replace('android-debug-0cbb7ee3668c4093007831d310780fa47afe9dda', 'android-preview-020a18c1b57b2614ed1867f40cb33b0d736ccabe').replace('Analyst-AI-debug-0cbb7ee.apk', 'Analyst-AI-0.4.2-preview-020a18c.apk').replace('9c45e7600edb8c9044b933ada9ba896595eff5c44fdf93382684456c99b4c009', '5d9bf30bb617092d2091384e5925f7a9f4e5b6195407070162a7d43dfcb8ef75'))

for path in (APP / 'ui').rglob('*.kt'):
    for index, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if 'Color.White' in line or 'private val' in line and 'Color(' in line:
            print('COLOR_REVIEW ' + str(path.relative_to(ROOT)) + ':' + str(index) + ' ' + line.strip())
print('INTEGRATION_COMPLETE')
