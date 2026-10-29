package ru.omnicio.app.ui.workspace

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import ru.omnicio.app.ui.spectrum.SpectrumSymbol

class CompactStrategyInputTest {
    @Test fun decimalsUseExactTextAndAcceptTheRussianSeparator() {
        assertEquals("0.25", strategyNumberInput("0,25", "0", "100", false))
        assertEquals("999999999999999.99", strategyNumberInput("999999999999999.99", "0", "999999999999999.99", false))
        assertEquals("120", strategyNumberInput("120.00", "1", "600", true))
    }
    @Test fun incompleteOutOfRangeAndFractionalMonthsNeverCommit() {
        for (raw in listOf("", "-1", "1e2", "NaN", "1.2.3", "1,", "601", "12.5"))
            assertNull(raw, strategyNumberInput(raw, "1", "600", true))
        assertNull(strategyNumberInput("1000000000000000", "0", "999999999999999.99", false))
    }
    private fun legacy() = JSONObject("""{"goal":"income","risk_level":"moderate","horizon_months":120,
        "reserve":{"amount":"0","currency":"RUB"},"limits":{"position_percent":"100","issuer_percent":"100",
        "group_percent":"100","sector_percent":"100","currency_percent":"100"}}""")
    @Test fun partialMandateReportsHiddenMandatoryFieldsInsteadOfAnUnexplainedError() {
        val config = legacy().put("mandate", JSONObject("""{"account_id":"owner-account","asset_mode":"mixed",
            "base_currency":"RUB","loss_capacity_percent":"5","bond_target_percent":"80","share_target_percent":"20"}"""))
        val issues = strategyValidationIssues(config)
        assertFalse(validStrategy(config))
        assertTrue(issues.any { it.startsWith("Минимальный рейтинг:") })
        assertTrue(issues.any { it.startsWith("Период учёта оборота:") })
        assertTrue(issues.any { it.startsWith("Купоны:") })
        assertEquals("5", config.getJSONObject("mandate").getString("loss_capacity_percent"))
    }
    @Test fun legacyConfigRemainsValidAndNewProfileMustSatisfyTheWholeContract() {
        assertTrue(validStrategy(legacy()))
        val mandate = JSONObject("""{"asset_mode":"mixed","base_currency":"RUB","account_id":"a",
            "loss_capacity_percent":"5","bond_target_percent":"80","share_target_percent":"20",
            "minimum_rating_level":3,"rebalance_cooldown_days":30,"turnover_window_days":30,
            "max_discretionary_turnover_percent":"5","max_trade_cost_percent":"0.25",
            "reinvest_coupons":false,"reinvest_dividends":false,"allowed_sessions":["main"]}""")
        assertTrue(validStrategy(legacy().put("mandate", mandate)))
        mandate.put("share_target_percent", "30")
        assertFalse(validStrategy(legacy().put("mandate", mandate)))
    }
    @Test fun everyServerProfileHasADistinctSemanticIcon() {
        val icons = listOf("capital", "coupon", "balanced", "growth", "equity").map(::strategyProfileSymbol)
        assertEquals(5, icons.toSet().size)
        assertFalse(icons.contains(SpectrumSymbol.Strategy))
        assertEquals(SpectrumSymbol.Strategy, strategyProfileSymbol("future-profile"))
    }
}
