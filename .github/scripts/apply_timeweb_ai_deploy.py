from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    content = target.read_text(encoding="utf-8")
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor, found {count}")
    target.write_text(content.replace(old, new, 1), encoding="utf-8")


replace_once(
    ".github/workflows/timeweb-backend.yml",
    """      TELEGRAM_CLIENT_ID: ${{ vars.TELEGRAM_CLIENT_ID }}
""",
    """      TELEGRAM_CLIENT_ID: ${{ vars.TELEGRAM_CLIENT_ID }}
      TIMEWEB_AI_TOKEN: ${{ secrets.TIMEWEB_AI_TOKEN }}
      TIMEWEB_AI_BASE_URL: ${{ vars.TIMEWEB_AI_BASE_URL }}
      AI_MODEL_FAST: ${{ vars.AI_MODEL_FAST }}
      AI_MODEL_STANDARD: ${{ vars.AI_MODEL_STANDARD }}
      AI_MODEL_PREMIUM: ${{ vars.AI_MODEL_PREMIUM }}
""",
)

replace_once(
    ".github/scripts/deploy_timeweb_backend.sh",
    """cat > "$UPLOAD_ENV" <<EOF
TELEGRAM_CLIENT_ID=$TELEGRAM_CLIENT_ID
TELEGRAM_CLIENT_SECRET=$TELEGRAM_CLIENT_SECRET
BACKEND_PUBLIC_URL=https://$BACKEND_HOST
APP_DEEP_LINK=analystai://auth
DATABASE_PATH=/var/lib/analyst-ai/backend.db
EOF
chmod 600 "$UPLOAD_ENV"
""",
    """for value in \
  "$TELEGRAM_CLIENT_ID" \
  "$TELEGRAM_CLIENT_SECRET" \
  "${TIMEWEB_AI_TOKEN:-}" \
  "${TIMEWEB_AI_BASE_URL:-}" \
  "${AI_MODEL_FAST:-}" \
  "${AI_MODEL_STANDARD:-}" \
  "${AI_MODEL_PREMIUM:-}"; do
  if [[ "$value" == *$'\\n'* || "$value" == *$'\\r'* ]]; then
    echo "::error::Deployment environment values must not contain newlines." >&2
    exit 1
  fi
done

{
  printf 'TELEGRAM_CLIENT_ID=%s\\n' "$TELEGRAM_CLIENT_ID"
  printf 'TELEGRAM_CLIENT_SECRET=%s\\n' "$TELEGRAM_CLIENT_SECRET"
  printf 'BACKEND_PUBLIC_URL=https://%s\\n' "$BACKEND_HOST"
  printf 'APP_DEEP_LINK=analystai://auth\\n'
  printf 'DATABASE_PATH=/var/lib/analyst-ai/backend.db\\n'

  if [[ -n "${TIMEWEB_AI_TOKEN:-}" ]]; then
    printf 'TIMEWEB_AI_TOKEN=%s\\n' "$TIMEWEB_AI_TOKEN"
    printf 'TIMEWEB_AI_BASE_URL=%s\\n' "${TIMEWEB_AI_BASE_URL:-https://api.timeweb.ai/v1}"
    printf 'AI_MODEL_FAST=%s\\n' "${AI_MODEL_FAST:-}"
    printf 'AI_MODEL_STANDARD=%s\\n' "${AI_MODEL_STANDARD:-}"
    printf 'AI_MODEL_PREMIUM=%s\\n' "${AI_MODEL_PREMIUM:-}"
  fi
} > "$UPLOAD_ENV"
chmod 600 "$UPLOAD_ENV"
""",
)

print("Timeweb AI deployment environment wiring applied")
