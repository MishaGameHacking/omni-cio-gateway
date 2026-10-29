"""Fund checks from typed T-Invest assets, without invented diversification.

Without verified look-through every fund is conservatively treated as full
exposure to the most concentrated issuer/group/sector. No diversification
credit is assigned from a ticker, marketing text or an LLM conclusion.
"""
try:
    from .volume_contract import decimal
except ImportError:
    from volume_contract import decimal


def fund_reasons(meta: dict) -> list[str]:
    evidence = meta.get("fund_policy") or {}
    fund = evidence.get("details")
    if evidence.get("asset_uid") != meta.get("assetUid") or not isinstance(fund, dict):
        return ["fund_terms_unverified"]
    reasons = []
    if fund.get("leveragedFlag", False) is not False:
        reasons.append("leveraged_fund_not_allowed")
    expense = decimal(fund.get("totalExpense"))
    if expense is None or not 0 <= expense <= 1.5:
        reasons.append("fund_total_expense_unknown_or_high")
    if not fund.get("primaryIndex") or not fund.get("focusType"):
        reasons.append("fund_benchmark_or_focus_unknown")
    return reasons
