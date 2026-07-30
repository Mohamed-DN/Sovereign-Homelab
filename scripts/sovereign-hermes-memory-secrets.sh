#!/usr/bin/env bash
set -euo pipefail

# Generate (once) the credentials for the Hermes memory stores, write the stack
# .env inside LXC 102, and drop the connection files Hermes reads at runtime.
# Run on the Proxmox host as root.
#
# Idempotent by design: regenerating the Postgres password after initdb has run
# would lock Hermes out of its own memory, because POSTGRES_PASSWORD only takes
# effect on an empty data directory.

SECRET_DIR="${SECRET_DIR:-/root/sovereign-secrets/hermes-memory}"
CTID="${CTID:-102}"
STACK_DIR="${STACK_DIR:-/opt/sovereign-homelab/stacks/hermes-memory}"
HERMES_SECRETS="${HERMES_SECRETS:-/root/sovereign-secrets/hermes}"

umask 077
mkdir -p "$SECRET_DIR"
chmod 700 "$SECRET_DIR"

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

# base64 can contain '+' and '/', harmless here, but the Postgres password ends
# up in a URL, so stick to hex for it.
make_secret pg-password       openssl rand -hex 24
make_secret qdrant-api-key    openssl rand -hex 32
make_secret qdrant-read-key   openssl rand -hex 32
make_secret valkey-password   openssl rand -hex 32

read_secret() { tr -d '\r\n' < "$SECRET_DIR/$1"; }

env_body=$(cat <<ENV
HERMES_PG_TAG=${HERMES_PG_TAG:-16-alpine}
HERMES_PG_DB=hermes_memory
HERMES_PG_USER=hermes
HERMES_PG_PORT=5432
HERMES_PG_PASSWORD=$(read_secret pg-password)
HERMES_QDRANT_TAG=${HERMES_QDRANT_TAG:-v1.18.3}
HERMES_QDRANT_PORT=6333
HERMES_QDRANT_API_KEY=$(read_secret qdrant-api-key)
HERMES_QDRANT_READ_KEY=$(read_secret qdrant-read-key)
HERMES_VALKEY_TAG=${HERMES_VALKEY_TAG:-9.1.1-alpine}
HERMES_VALKEY_PORT=6379
HERMES_VALKEY_MAXMEMORY=256mb
HERMES_VALKEY_PASSWORD=$(read_secret valkey-password)
ENV
)

pct exec "$CTID" -- mkdir -p "$STACK_DIR" "$HERMES_SECRETS"
printf '%s\n' "$env_body" | pct exec "$CTID" -- bash -c \
  "install -m 600 /dev/null '$STACK_DIR/.env' && cat > '$STACK_DIR/.env'"

# Hermes reads one file per store, the same way it already reads its CouchDB
# password and its estate token. One secret per file, 0600, never in the JSON.
write_hermes_secret() {
  printf '%s' "$2" | pct exec "$CTID" -- bash -c \
    "install -m 600 /dev/null '$HERMES_SECRETS/$1' && cat > '$HERMES_SECRETS/$1'"
  echo "wrote   LXC $CTID:$HERMES_SECRETS/$1" >&2
}

write_hermes_secret memory-postgres-dsn \
  "postgresql://hermes:$(read_secret pg-password)@127.0.0.1:5432/hermes_memory"
write_hermes_secret memory-qdrant-key "$(read_secret qdrant-api-key)"
write_hermes_secret memory-valkey-password "$(read_secret valkey-password)"

pct exec "$CTID" -- bash -c "ls -l '$STACK_DIR/.env' '$HERMES_SECRETS'/memory-*"
echo "Hermes memory credentials in place" >&2
