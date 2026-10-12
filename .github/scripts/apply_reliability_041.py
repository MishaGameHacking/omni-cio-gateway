from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def change(path, old, new):
    target = ROOT / path
    text = target.read_text(encoding='utf-8')
    if text.count(old) != 1:
        raise RuntimeError(f'Expected one replacement anchor in {path}: {old[:70]!r}')
    target.write_text(text.replace(old, new, 1), encoding='utf-8')

a = 'backend/autonomous_ai.py'
change(a, 'import logging\n', 'import logging\nimport math\n')
change(a, 'from .analysis_engine import AnalysisReport, analyze_if_needed', 'from .analysis_engine import AnalysisEvidence, AnalysisReport, analyze_if_needed')
change(a, 'from analysis_engine import AnalysisReport, analyze_if_needed', 'from analysis_engine import AnalysisEvidence, AnalysisReport, analyze_if_needed')
change(a, 'from .timeweb_ai import TimewebAIError', 'from .timeweb_ai import TimewebAIConfig, TimewebAIConfigurationError, TimewebAIError')
change(a, 'from timeweb_ai import TimewebAIError', 'from timeweb_ai import TimewebAIConfig, TimewebAIConfigurationError, TimewebAIError')
change(a, '''    target.cancel()
    try:
        await target
    except asyncio.CancelledError:
        pass
    if target is _scheduler_task:
        _scheduler_task = None''', '''    target.cancel()
    try:
        # wait() observes the child's cancellation without swallowing cancellation
        # of the caller (for example, a server shutdown deadline).
        await asyncio.wait({target})
        if not target.cancelled():
            target.result()
    finally:
        if target is _scheduler_task and target.done():
            _scheduler_task = None''')
change(a, '''    material_changed = force or (
        previous_material is not None and previous_material != material_digest
    )''', '''    # A refresh requests fresh data, never fabricates a portfolio transaction.
    material_changed = previous_material is not None and previous_material != material_digest''')
change(a, '''    portfolio_changed = force or bool(
        previous_features''', '''    portfolio_changed = bool(
        previous_features''')
change(a, 'return run_user_analysis(int(user["id"]), force=True)', 'return run_user_analysis(int(user["id"]), force=False)')
change(a, '''    allocations = _allocation_map(snapshot)
    if allocations:
        title, share = max(allocations.items(), key=lambda item: item[1])
        threshold = min(80.0, float(profile["max_position_percent"]) + 15.0)
        if share >= threshold:
            return True, f"Высокая концентрация: {title} — {share:.1f}%"
    yield_percent = _decimal_value(snapshot.get("expectedYieldPercent"))
    if yield_percent <= -25.0:
        return True, f"Просадка портфеля за всё время: {yield_percent:.1f}%"''', '''    total_money = snapshot.get("totalValue") or {}
    total = _money_value(total_money)
    currency = str(total_money.get("currency") or "").upper()
    values: dict[str, float] = {}
    titles: dict[str, str] = {}
    for account in snapshot.get("accounts") or []:
        if not isinstance(account, dict):
            continue
        for position in account.get("positions") or []:
            if not isinstance(position, dict):
                continue
            identifier = str(position.get("id") or "")
            money = position.get("currentValue") or {}
            if not identifier or identifier.startswith("cash:") or not isinstance(money, dict):
                continue
            # Never add unlike currencies or treat a whole asset class as one issuer.
            if str(money.get("currency") or "").upper() != currency:
                continue
            values[identifier] = values.get(identifier, 0.0) + abs(_money_value(money))
            titles[identifier] = str(position.get("title") or position.get("ticker") or identifier)
    if total > 0 and values:
        identifier, value = max(values.items(), key=lambda item: item[1])
        share = value / total * 100.0
        threshold = min(80.0, float(profile["max_position_percent"]) + 15.0)
        if share >= threshold:
            return True, f"Высокая концентрация позиции: {titles[identifier]} — {share:.1f}%"
    yield_percent = _decimal_value(snapshot.get("expectedYieldPercent"))
    if yield_percent <= -25.0:
        return True, f"Отрицательный результат портфеля по данным API: {yield_percent:.1f}%"''')
change(a, 'Проверьте долю крупнейшего класса активов и допустимый риск в профиле.', 'Проверьте долю крупнейшей позиции и допустимый риск в профиле.')
change(a, '''        evidence=(),
        uncertainties=(''', '''        evidence=(AnalysisEvidence(
            fact=evidence_fact,
            source_id=f"tinvest:portfolio:{int(now.timestamp())}",
            as_of=as_of,
        ),),
        uncertainties=(''')
text = (ROOT / a).read_text(encoding='utf-8')
start = text.index('def _consume_budget(')
end = text.index('\n\ndef _last_analysis(', start)
text = text[:start] + '''def _reserve_budget(user_id: int, now: datetime, tier: AnalysisTier) -> bool:
    """Reserve an attempt atomically before the network call, even if it later fails."""
    limits = {
        AnalysisTier.FAST: ("fast_calls", FAST_DAILY_LIMIT),
        AnalysisTier.STANDARD: ("standard_calls", STANDARD_DAILY_LIMIT),
        AnalysisTier.PREMIUM: ("premium_calls", PREMIUM_DAILY_LIMIT),
    }
    if tier not in limits:
        return False
    column, limit = limits[tier]
    day_key = _analysis_day(now)
    with closing(backend.connect()) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "INSERT OR IGNORE INTO analysis_budget_usage(user_id, day_key) VALUES (?, ?)",
            (user_id, day_key),
        )
        # column comes only from the fixed whitelist above, never from a request.
        cursor = db.execute(
            f"UPDATE analysis_budget_usage SET {column} = {column} + 1 "
            f"WHERE user_id = ? AND day_key = ? AND {column} < ?",
            (user_id, day_key, limit),
        )
        reserved = cursor.rowcount == 1
        db.commit()
    return reserved
''' + text[end:]
(ROOT / a).write_text(text, encoding='utf-8')
change(a, '''    if decision.tier is AnalysisTier.NONE:
        return {
            "state": "skipped",''', '''    if decision.tier is AnalysisTier.NONE and signals.critical_risk:
        # Safety messages do not depend on a paid-model quota.
        decision = AnalysisDecision(AnalysisTier.NONE, AnalysisReason.RISK_EVENT, True, 0)
    elif decision.tier is AnalysisTier.NONE:
        return {
            "state": "skipped",''')
change(a, '''    try:
        result = analyze_if_needed(
            signals=signals,''', '''    try:
        if decision.tier is AnalysisTier.NONE:
            raise TimewebAIConfigurationError("analysis_budget_exhausted")
        # Missing credentials are free; uncertain network failures are not retried
        # for free. Reservation is never rolled back after a model attempt.
        TimewebAIConfig.from_env().model_for(decision.tier)
        if not _reserve_budget(user_id, current_time, decision.tier):
            raise TimewebAIConfigurationError("analysis_budget_exhausted")
        result = analyze_if_needed(
            signals=signals,''')
change(a, '''        if result.report is not None:
            _consume_budget(user_id, current_time, decision.tier)
''', '')
change(a, '''    gaps.sort(key=lambda item: item["gap_percent"], reverse=True)
    return {''', '''    gaps.sort(key=lambda item: item["gap_percent"], reverse=True)
    remaining = math.floor(investable * 10.0) / 10.0
    bounded_gaps = []
    for idea in gaps[:4]:
        suggested = min(float(idea["gap_percent"]), remaining)
        suggested = math.floor(suggested * 10.0) / 10.0
        if suggested <= 0:
            continue
        idea["suggested_max_percent"] = suggested
        bounded_gaps.append(idea)
        remaining = max(0.0, remaining - suggested)
    gaps = bounded_gaps
    return {''')
change(a, '''        db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="analysis_card_not_found")''', '''        changed = cursor.rowcount
        db.commit()
    if changed == 0:
        raise HTTPException(status_code=404, detail="analysis_card_not_found")''')
change('backend/timeweb_ai.py', 'base_url=os.getenv("TIMEWEB_AI_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),', 'base_url=(os.getenv("TIMEWEB_AI_BASE_URL", "").strip() or DEFAULT_BASE_URL).rstrip("/"),')
change('app/build.gradle.kts', 'versionCode = 18\n        versionName = "0.4.0"', 'versionCode = 19\n        versionName = "0.4.1"')
# Correct the fixture and replace the old expectation that refresh invents a trade.
t = 'backend/tests/test_autonomous_ai.py'
change(t, '"units": 50_000, "nano": 0', '"units": int(stock_share * 1000), "nano": 0')
change(t, 'def test_force_refresh_creates_deterministic_card_without_ai_key(self)', 'def test_force_refresh_does_not_invent_a_transaction(self)')
change(t, '''        self.assertEqual(result["state"], "fallback")
        self.assertEqual(result["reason"], "portfolio_changed")
        self.assertIsNotNone(result["card_id"])

        payload = ai.feed(limit=10, user=self.user_row())
        self.assertEqual(payload["unread_count"], 1)
        self.assertEqual(len(payload["cards"]), 1)
        self.assertIn("портфел", payload["cards"][0]["title"].lower())''', '''        self.assertEqual(result["state"], "skipped")
        self.assertIsNone(result["card_id"])
        payload = ai.feed(limit=10, user=self.user_row())
        self.assertEqual(payload["unread_count"], 0)
        self.assertEqual(payload["cards"], [])''')
print('Reliability corrections applied; no production credentials used.')
