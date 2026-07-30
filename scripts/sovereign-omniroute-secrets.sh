#!/usr/bin/env bash
set -euo pipefail

# Generate (once) the OmniRoute secrets and write the stack .env inside LXC 102.
# Run on the Proxmox host as root.
#
# Idempotent on purpose: STORAGE_ENCRYPTION_KEY and API_KEY_SECRET must never
# be regenerated once the database exists - a new key means the SQLite file and
# every stored provider key become unreadable. The script therefore only
# creates what is missing and reuses what is already there.

SECRET_DIR="${SECRET_DIR:-/root/sovereign-secrets/omniroute}"
CTID="${CTID:-102}"
STACK_DIR="${STACK_DIR:-/opt/sovereign-homelab/stacks/omniroute}"
COMMON_PASSWORD_FILE="${COMMON_PASSWORD_FILE:-/root/sovereign-secrets/common-app-password}"

umask 077
mkdir -p "$SECRET_DIR"
chmod 700 "$SECRET_DIR"

# make_secret <file> <generator...> - create with 0600 only if absent.
make_secret() {
  local file="$SECRET_DIR/$1"; shift
  if [[ -s "$file" ]]; then
    echo "keep    $file" >&2
  else
    ( umask 077; "$@" > "$file" )
    chmod 600 "$file"
    echo "created $file" >&2
  fi
}

make_secret jwt-secret              openssl rand -base64 48
make_secret api-key-secret          openssl rand -hex 32
make_secret storage-encryption-key  openssl rand -hex 32
make_secret machine-id-salt         openssl rand -hex 16

# The dashboard password is the estate's shared app password, so the owner does
# not have to learn a new one. If that file is missing, generate a dedicated one.
if [[ ! -s "$SECRET_DIR/initial-password" ]]; then
  if [[ -s "$COMMON_PASSWORD_FILE" ]]; then
    ( umask 077; tr -d '\r\n' < "$COMMON_PASSWORD_FILE" > "$SECRET_DIR/initial-password" )
    echo "created $SECRET_DIR/initial-password (from common-app-password)" >&2
  else
    ( umask 077; openssl rand -base64 24 > "$SECRET_DIR/initial-password" )
    echo "created $SECRET_DIR/initial-password (generated)" >&2
  fi
  chmod 600 "$SECRET_DIR/initial-password"
else
  echo "keep    $SECRET_DIR/initial-password" >&2
fi

read_secret() { tr -d '\r\n' < "$SECRET_DIR/$1"; }

env_body=$(cat <<ENV
OMNIROUTE_TAG=${OMNIROUTE_TAG:-3.8.48}
OMNIROUTE_PORT=20128
OMNIROUTE_LIVE_WS_PORT=20132
OMNIROUTE_JWT_SECRET=$(read_secret jwt-secret)
OMNIROUTE_API_KEY_SECRET=$(read_secret api-key-secret)
OMNIROUTE_STORAGE_ENCRYPTION_KEY=$(read_secret storage-encryption-key)
OMNIROUTE_MACHINE_ID_SALT=$(read_secret machine-id-salt)
OMNIROUTE_INITIAL_PASSWORD=$(read_secret initial-password)
ENV
)

pct exec "$CTID" -- mkdir -p "$STACK_DIR"
# Write through a 0600 file created inside the container, never via a
# world-readable temporary path.
printf '%s\n' "$env_body" | pct exec "$CTID" -- bash -c \
  "install -m 600 /dev/null '$STACK_DIR/.env' && cat > '$STACK_DIR/.env'"

pct exec "$CTID" -- bash -c "ls -l '$STACK_DIR/.env'"
echo "OmniRoute .env written inside LXC $CTID" >&2
