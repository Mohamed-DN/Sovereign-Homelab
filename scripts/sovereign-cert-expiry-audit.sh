#!/usr/bin/env bash
set -euo pipefail

WARN_DAYS="${WARN_DAYS:-30}"
PUBLIC_VPN_HOST="${PUBLIC_VPN_HOST:-vpn.casca-certosa.duckdns.org}"
NPM_IP="${NPM_IP:-192.168.1.50}"
RENEW_INTERNAL_CMD="${RENEW_INTERNAL_CMD:-/usr/local/sbin/sovereign-renew-npm-internal-certs}"

warn_seconds=$((WARN_DAYS * 24 * 60 * 60))
failures=0
renewed=0

log() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

cert_pem_for() {
  local connect_host="$1"
  local port="$2"
  local sni="$3"
  timeout 15 openssl s_client \
    -connect "${connect_host}:${port}" \
    -servername "${sni}" \
    -showcerts </dev/null 2>/dev/null |
    openssl x509 -outform PEM
}

check_endpoint() {
  local label="$1"
  local connect_host="$2"
  local port="$3"
  local sni="$4"
  local allow_internal_renew="${5:-false}"

  local pem end_date
  if ! pem="$(cert_pem_for "$connect_host" "$port" "$sni")"; then
    log "FAIL ${label}: cannot read certificate from ${connect_host}:${port} with SNI ${sni}"
    failures=$((failures + 1))
    return
  fi

  end_date="$(printf '%s\n' "$pem" | openssl x509 -noout -enddate | sed 's/^notAfter=//')"
  if printf '%s\n' "$pem" | openssl x509 -checkend "$warn_seconds" -noout >/dev/null 2>&1; then
    log "PASS ${label}: certificate valid beyond ${WARN_DAYS} days, expires ${end_date}"
    return
  fi

  log "WARN ${label}: certificate expires within ${WARN_DAYS} days, expires ${end_date}"
  if [[ "$allow_internal_renew" == "true" && "$renewed" -eq 0 && -x "$RENEW_INTERNAL_CMD" ]]; then
    log "ACTION running ${RENEW_INTERNAL_CMD}"
    "$RENEW_INTERNAL_CMD"
    renewed=1
    pem="$(cert_pem_for "$connect_host" "$port" "$sni")"
    end_date="$(printf '%s\n' "$pem" | openssl x509 -noout -enddate | sed 's/^notAfter=//')"
    if printf '%s\n' "$pem" | openssl x509 -checkend "$warn_seconds" -noout >/dev/null 2>&1; then
      log "PASS ${label}: certificate renewed, expires ${end_date}"
      return
    fi
  fi

  log "FAIL ${label}: certificate still expires within ${WARN_DAYS} days"
  failures=$((failures + 1))
}

check_endpoint "public-headscale" "$PUBLIC_VPN_HOST" 443 "$PUBLIC_VPN_HOST" false
check_endpoint "proxmox-internal" "$NPM_IP" 443 "proxmox.internal" true
check_endpoint "pbs-internal" "$NPM_IP" 443 "pbs.internal" true
check_endpoint "nextcloud-internal" "$NPM_IP" 443 "files.internal" false

if [[ "$failures" -gt 0 ]]; then
  log "RESULT failed=${failures}"
  exit 1
fi

log "RESULT ok"
