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
