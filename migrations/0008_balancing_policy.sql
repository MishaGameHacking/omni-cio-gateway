BEGIN;

ALTER TABLE instrument_catalog
    ADD COLUMN IF NOT EXISTS nominal_value numeric(24, 9),
    ADD COLUMN IF NOT EXISTS nominal_currency text,
    ADD COLUMN IF NOT EXISTS maturity_date timestamptz,
    ADD COLUMN IF NOT EXISTS floating_coupon boolean,
    ADD COLUMN IF NOT EXISTS perpetual boolean,
    ADD COLUMN IF NOT EXISTS amortization boolean,
    ADD COLUMN IF NOT EXISTS subordinated boolean,
    ADD COLUMN IF NOT EXISTS liquidity boolean;

ALTER TABLE portfolio_snapshot_positions
    ADD COLUMN IF NOT EXISTS quantity_lots numeric(38, 9),
    ADD COLUMN IF NOT EXISTS average_price_fifo_value numeric(24, 9),
    ADD COLUMN IF NOT EXISTS average_price_fifo_currency text;

CREATE TABLE IF NOT EXISTS balancing_policy_versions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    version integer NOT NULL CHECK (version > 0),
    max_instrument_percent numeric(7, 4) NOT NULL CHECK (
        max_instrument_percent >= 0 AND max_instrument_percent <= 100
    ),
    max_sector_percent numeric(7, 4) NOT NULL CHECK (
        max_sector_percent >= 0 AND max_sector_percent <= 100
    ),
    max_issuer_percent numeric(7, 4) NOT NULL CHECK (
        max_issuer_percent >= 0 AND max_issuer_percent <= 100
    ),
    max_group_percent numeric(7, 4) NOT NULL CHECK (
        max_group_percent >= 0 AND max_group_percent <= 100
    ),
    max_share_percent numeric(7, 4) NOT NULL CHECK (
        max_share_percent >= 0 AND max_share_percent <= 100
    ),
    max_bond_percent numeric(7, 4) NOT NULL CHECK (
        max_bond_percent >= 0 AND max_bond_percent <= 100
    ),
    max_etf_percent numeric(7, 4) NOT NULL CHECK (
        max_etf_percent >= 0 AND max_etf_percent <= 100
    ),
    max_below_grade_percent numeric(7, 4) NOT NULL CHECK (
        max_below_grade_percent >= 0 AND max_below_grade_percent <= 100
    ),
    max_unknown_percent numeric(7, 4) NOT NULL CHECK (
        max_unknown_percent >= 0 AND max_unknown_percent <= 100
    ),
    max_term_months integer NOT NULL CHECK (max_term_months BETWEEN 0 AND 1200),
    turnover_budget_percent numeric(7, 4) NOT NULL CHECK (
        turnover_budget_percent >= 0 AND turnover_budget_percent <= 100
    ),
    max_daily_turnover_participation_percent numeric(7, 4) NOT NULL CHECK (
        max_daily_turnover_participation_percent >= 0
        AND max_daily_turnover_participation_percent <= 100
    ),
    securities_tax_rate_percent numeric(7, 4) NOT NULL CHECK (
        securities_tax_rate_percent >= 0 AND securities_tax_rate_percent <= 100
    ),
    no_trade_band_percent numeric(7, 4) NOT NULL CHECK (
        no_trade_band_percent >= 0 AND no_trade_band_percent <= 100
    ),
    min_replace_benefit_rub numeric(24, 8) NOT NULL CHECK (
        min_replace_benefit_rub >= 0
    ),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, version)
);

CREATE INDEX IF NOT EXISTS balancing_policy_versions_user_version_idx
    ON balancing_policy_versions (user_id, version DESC);

ALTER TABLE balancing_policy_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE balancing_policy_versions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS balancing_policy_versions_tenant ON balancing_policy_versions;
CREATE POLICY balancing_policy_versions_tenant
    ON balancing_policy_versions
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);

COMMIT;
