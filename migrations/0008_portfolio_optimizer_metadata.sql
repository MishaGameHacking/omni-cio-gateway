BEGIN;

ALTER TABLE instrument_catalog
    ADD COLUMN IF NOT EXISTS min_price_increment numeric(24, 9)
        CHECK (min_price_increment IS NULL OR min_price_increment > 0),
    ADD COLUMN IF NOT EXISTS nominal_value numeric(24, 9)
        CHECK (nominal_value IS NULL OR nominal_value >= 0),
    ADD COLUMN IF NOT EXISTS nominal_currency text,
    ADD COLUMN IF NOT EXISTS aci_value numeric(24, 9)
        CHECK (aci_value IS NULL OR aci_value >= 0),
    ADD COLUMN IF NOT EXISTS aci_currency text,
    ADD COLUMN IF NOT EXISTS maturity_date timestamptz,
    ADD COLUMN IF NOT EXISTS coupon_quantity_per_year integer
        CHECK (coupon_quantity_per_year IS NULL OR coupon_quantity_per_year >= 0),
    ADD COLUMN IF NOT EXISTS floating_coupon boolean,
    ADD COLUMN IF NOT EXISTS perpetual boolean,
    ADD COLUMN IF NOT EXISTS amortization boolean,
    ADD COLUMN IF NOT EXISTS subordinated boolean,
    ADD COLUMN IF NOT EXISTS liquidity boolean,
    ADD COLUMN IF NOT EXISTS exchange text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS real_exchange text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS tax_free boolean,
    ADD COLUMN IF NOT EXISTS collateral boolean,
    ADD COLUMN IF NOT EXISTS risk_level text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS ratings jsonb NOT NULL DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS instrument_catalog_candidate_screen_idx
    ON instrument_catalog (
        provider,
        instrument_type,
        currency,
        api_trade_available,
        buy_available,
        liquidity,
        maturity_date
    );

COMMIT;
