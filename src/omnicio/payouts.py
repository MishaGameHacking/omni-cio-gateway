"""Read identities for immutable payout evidence and retained workspace aliases."""

# T-Invest defines created_at as record creation time, not revision time:
# https://developer.tbank.ru/invest/services/instruments/methods#dividend
# This timestamp is not unique: also require the unchanged distribution anchors.
# Missing/invalid anchors retain original keys; never merge on a record date alone.
PAYOUT_IDENTITY_SQL = (
    "CASE WHEN pe.provider = 'tbank' AND pe.event_type = 'dividend' "
    "AND pe.record_at IS NOT NULL AND pe.announced_at IS NOT NULL "
    "AND pe.currency IS NOT NULL AND btrim(pe.currency) <> '' "
    "AND jsonb_typeof(pe.payload -> 'regularity') = 'string' "
    "AND btrim(pe.payload ->> 'regularity') <> '' "
    "AND jsonb_typeof(pe.payload -> 'created_at') = 'string' "
    "AND pe.payload ->> 'created_at' ~ "
    "'^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    "([.][0-9]{1,6})?(Z|[+-][0-9]{2}:[0-9]{2})$' "
    "AND pg_input_is_valid(pe.payload ->> 'created_at', 'timestamptz') "
    "THEN 'dividend:' || jsonb_build_array("
    "to_char((pe.payload ->> 'created_at')::timestamptz "
    "AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.US'), "
    "to_char(pe.record_at AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.US'), "
    "to_char(pe.announced_at AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.US'), "
    "lower(btrim(pe.payload ->> 'regularity')), lower(btrim(pe.currency)))::text "
    "ELSE 'key:' || pe.provider_key END"
)

# Callers provide payout_scope(instrument_uid), keeping the receipt scan bounded to
# their visible instruments. Equal observation times disprove safe deduplication;
# they are not a provider batch ID or proof that the response was complete.
PAYOUT_READ_CTES = f"""
    payout_candidates AS (
        SELECT pe.*, {PAYOUT_IDENTITY_SQL} AS anchor_key,
            NULLIF(lower(btrim(pe.payload ->> 'dividend_type')), '') AS distribution_type
        FROM payout_events pe
        WHERE pe.instrument_uid IN (SELECT instrument_uid FROM payout_scope)
    ), payout_ambiguous AS (
        SELECT DISTINCT provider, instrument_uid, event_type, anchor_key
        FROM (
            SELECT pe.provider, pe.instrument_uid, pe.event_type, pe.anchor_key
            FROM payout_candidates pe
            JOIN source_retrievals sr ON sr.source_document_id = pe.source_document_id
            WHERE left(pe.anchor_key, 9) = 'dividend:'
            GROUP BY pe.provider, pe.instrument_uid, pe.event_type,
                pe.anchor_key, sr.retrieved_at
            HAVING count(DISTINCT pe.provider_key) > 1 OR count(DISTINCT pe.status) > 1
                OR count(DISTINCT pe.distribution_type) > 1
        ) co_observed
    ), payout_observations AS (
        SELECT pe.*, sd.source_url, sd.first_retrieved_at, retrieval.retrieved_at,
            ambiguous.anchor_key IS NOT NULL AS identity_ambiguous,
            CASE WHEN ambiguous.anchor_key IS NOT NULL THEN 'observation:' ||
                    jsonb_build_array(pe.provider_key, pe.status, pe.distribution_type)::text
                 ELSE pe.anchor_key END AS logical_key,
            max(retrieval.retrieved_at) OVER (
                PARTITION BY pe.provider, pe.instrument_uid, pe.event_type, pe.anchor_key
            ) AS latest_positive_at
        FROM payout_candidates pe
        JOIN source_documents sd ON sd.id = pe.source_document_id
        JOIN LATERAL (
            SELECT COALESCE(max(sr.retrieved_at), sd.first_retrieved_at) AS retrieved_at
            FROM source_retrievals sr WHERE sr.source_document_id = sd.id
        ) retrieval ON true
        LEFT JOIN payout_ambiguous ambiguous
            ON ambiguous.provider = pe.provider
            AND ambiguous.instrument_uid = pe.instrument_uid
            AND ambiguous.event_type = pe.event_type AND ambiguous.anchor_key = pe.anchor_key
    )
"""


def payout_source_sql(alias: str) -> str:
    """Compare payout facts without treating an equivalent timezone as a correction."""
    if alias not in {"workspace_events", "EXCLUDED"}:
        raise ValueError("unsupported_payout_source_alias")
    source = f"{alias}.source"
    expected = f"{source} ->> 'expected_at'"
    return (
        f"({source} - ARRAY['id', 'superseded_by', 'expected_at']) "
        "|| jsonb_build_object('expected_at', CASE "
        f"WHEN jsonb_typeof({source} -> 'expected_at') = 'string' "
        f"AND {expected} ~ '(Z|[+-][0-9]{{2}}:[0-9]{{2}})$' "
        f"AND pg_input_is_valid({expected}, 'timestamptz') "
        f"THEN to_jsonb(({expected})::timestamptz AT TIME ZONE 'UTC') "
        f"ELSE {source} -> 'expected_at' END)"
    )


def visible_event_sql(alias: str = "") -> str:
    """Hide only server-owned superseded payout aliases, preserving their receipts."""
    if alias not in {"", "e"}:
        raise ValueError("unsupported_workspace_event_alias")
    prefix = f"{alias}." if alias else ""
    return (
        f"NOT ({prefix}kind = 'payout_calendar' "
        f"AND COALESCE({prefix}source ->> 'type', '') = 'payout' "
        f"AND COALESCE({prefix}source ->> 'superseded_by', '') ~ '^[0-9a-f]{{64}}$')"
    )
