package ru.omnicio.app.ui.workspace

import org.junit.Assert.*
import org.junit.Test
import org.json.JSONObject

class StrategyMandateControlsTest {
    @Test fun steppingPreservesCentsAndDoesNotRoundTheLoadedValue() {
        assertEquals("1234.567", steppedStrategyNumber("1234.557", "0.01", 1, "0", "999999"))
        assertEquals("4.9", steppedStrategyNumber("5", "0.1", -1, "0", "100"))
        assertEquals("100", steppedStrategyNumber("99.99", "1", 1, "0", "100"))
        assertEquals("0.01", steppedStrategyNumber("0.02", "1", -1, "0.01", "100"))
        assertNull(steppedStrategyNumber("NaN", "1", 1, "0", "100"))
        assertNull(steppedStrategyNumber("1", "0", 1, "0", "100"))
        assertNull(steppedStrategyNumber("101", "1", -1, "0", "100"))
    }
    @Test fun incompleteProfileIsOnlyADraftAndDoesNotGuessAnAllocation() {
        val draft=newMandateDraft()
        assertFalse(draft.has("asset_mode"))
        assertFalse(draft.has("loss_capacity_percent"))
        assertFalse(validPortfolioMandate(draft))
    }
    @Test fun fractionalAllocationAndZeroRiskRemainValidWithoutFloatConversion() {
        val value=JSONObject("""{"asset_mode":"mixed","base_currency":"RUB","account_id":"account-a",
            "loss_capacity_percent":"0","bond_target_percent":"60.125","share_target_percent":"39.875",
            "minimum_rating_level":9,"max_discretionary_turnover_percent":"0","turnover_window_days":30,
            "max_trade_cost_percent":"0.01","rebalance_cooldown_days":30,"reinvest_coupons":true,
            "reinvest_dividends":false,"allowed_sessions":["main"]}""")
        assertTrue(validPortfolioMandate(value))
        value.put("asset_mode","bonds")
        assertFalse(validPortfolioMandate(value))
        value.put("asset_mode","mixed").put("reinvest_dividends",JSONObject.NULL)
        assertFalse(validPortfolioMandate(value))
    }
}
