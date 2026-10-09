-- A current-position snapshot is useful even when prices or collateral
-- reservations are unavailable. NULL preserves that uncertainty.
ALTER TABLE portfolio_snapshots
    ALTER COLUMN nav_rub DROP NOT NULL,
    ALTER COLUMN rub_cash_total DROP NOT NULL,
    ALTER COLUMN rub_cash_blocked DROP NOT NULL;
