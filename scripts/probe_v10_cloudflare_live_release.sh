#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: probe_v10_cloudflare_live_release.sh <sha>" >&2
  exit 2
fi

sha="$1"
origin="$(python scripts/check_v10_cloudflare_live_release.py origin)"

curl_flags=(
  --silent
  --show-error
  --fail-with-body
  --proto '=https'
  --tlsv1.2
  --connect-timeout 10
  --max-time 20
  --max-redirs 0
  --max-filesize 65536
  --header 'Accept: application/json'
)

curl "${curl_flags[@]}" "${origin}/api/v10/release" \
  | python scripts/check_v10_cloudflare_live_release.py release "$sha"

curl "${curl_flags[@]}" "${origin}/healthz" \
  | python scripts/check_v10_cloudflare_live_release.py health "$sha"

echo "Cloudflare live release accepted: ${origin}"
echo "Exact source SHA: ${sha}"
