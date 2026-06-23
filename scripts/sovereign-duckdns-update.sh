#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${DUCKDNS_DOMAIN:-yourdomain}"
CREDENTIALS_FILE="${DUCKDNS_CREDENTIALS_FILE:-/opt/core-network/npm/letsencrypt/credentials/credentials-1}"
IP_SERVICE="${DUCKDNS_IP_SERVICE:-https://api.ipify.org}"

if [ ! -r "$CREDENTIALS_FILE" ]; then
  echo "duckdns_update_failed reason=credentials_file_not_readable file=$CREDENTIALS_FILE" >&2
  exit 1
fi

TOKEN="$(
  awk -F= '/duckdns.*token/ {print $2; exit}' "$CREDENTIALS_FILE" \
    | tr -d '[:space:]' \
    | sed -E "s/^[\"']//; s/[\"']$//"
)"

if [ -z "$TOKEN" ]; then
  echo "duckdns_update_failed reason=missing_token" >&2
  exit 1
fi

PUBLIC_IP="$(curl -fsS4 "$IP_SERVICE")"
if [ -z "$PUBLIC_IP" ]; then
  echo "duckdns_update_failed reason=missing_public_ip" >&2
  exit 1
fi

RESPONSE="$(
  curl -fsS --get \
    --data-urlencode "domains=$DOMAIN" \
    --data-urlencode "token=$TOKEN" \
    --data-urlencode "ip=$PUBLIC_IP" \
    --data-urlencode "verbose=true" \
    https://www.duckdns.org/update
)"

if printf '%s' "$RESPONSE" | grep -qi '^OK'; then
  echo "duckdns_update_ok domain=$DOMAIN ip=$PUBLIC_IP"
else
  echo "duckdns_update_failed domain=$DOMAIN response=$(printf '%s' "$RESPONSE" | sed -E 's/[0-9a-fA-F-]{24,}/REDACTED/g')" >&2
  exit 1
fi
