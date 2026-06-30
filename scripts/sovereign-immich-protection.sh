#!/usr/bin/env bash
set -Eeuo pipefail

mode="${1:-daily}"
upload_root="${IMMICH_UPLOAD_ROOT:-/mnt/immich-library/upload}"
backup_root="${IMMICH_BACKUP_ROOT:-/root/sovereign-secrets/immich-protection}"
database_container="${IMMICH_DATABASE_CONTAINER:-immich-database}"
server_container="${IMMICH_SERVER_CONTAINER:-immich-server}"
daily_retention_days="${IMMICH_DAILY_RETENTION_DAYS:-21}"
quarterly_retention_days="${IMMICH_QUARTERLY_RETENTION_DAYS:-730}"
relay_url="${IMMICH_ALERT_RELAY_URL:-http://192.168.1.51:8099/webhook}"
relay_token_file="${IMMICH_ALERT_RELAY_TOKEN_FILE:-/root/sovereign-secrets/immich-alert-relay-token}"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
daily_dir="$backup_root/daily"
weekly_dir="$backup_root/weekly"
quarterly_dir="$backup_root/quarterly"
state_dir="$backup_root/state"
lock_file="$state_dir/immich-protection.lock"
restore_database=""

mkdir -p "$daily_dir" "$weekly_dir" "$quarterly_dir" "$state_dir"
chmod 700 "$backup_root" "$daily_dir" "$weekly_dir" "$quarterly_dir" "$state_dir"
umask 077

exec 9>"$lock_file"
if ! flock -n 9; then
  echo "another Immich protection job is running" >&2
  exit 1
fi

send_relay_event() {
  local status="$1"
  local message="$2"
  [[ -s "$relay_token_file" ]] || return 0

  local payload curl_config
  payload="$(mktemp "$state_dir/relay-payload.XXXXXX")"
  curl_config="$(mktemp "$state_dir/relay-curl.XXXXXX")"
  python3 - "$status" "$message" "$mode" > "$payload" <<'PY'
import json
import sys

status, message, mode = sys.argv[1:]
print(json.dumps({
    "monitor": {"id": "immich-protection", "name": "Immich backup protection"},
    "heartbeat": {
        "status": 1 if status == "up" else 0,
        "msg": f"{mode}: {message}"[:800],
    },
}))
PY
  printf 'silent\nshow-error\nfail\nconnect-timeout = 5\nmax-time = 20\nheader = "Content-Type: application/json"\nheader = "Authorization: Bearer %s"\n' \
    "$(<"$relay_token_file")" > "$curl_config"
  curl --config "$curl_config" --data-binary "@$payload" "$relay_url" >/dev/null || true
  rm -f "$payload" "$curl_config"
}

cleanup_restore_database() {
  if [[ -n "$restore_database" ]]; then
    docker exec -e RESTORE_DATABASE="$restore_database" "$database_container" \
      sh -lc 'dropdb --if-exists --force --username="$POSTGRES_USER" "$RESTORE_DATABASE"' >/dev/null 2>&1 || true
  fi
}

on_error() {
  local exit_code=$?
  cleanup_restore_database
  send_relay_event down "job failed with exit code $exit_code"
  exit "$exit_code"
}
trap on_error ERR
trap cleanup_restore_database EXIT

require_live_immich() {
  [[ -d "$upload_root" ]]
  docker inspect "$database_container" >/dev/null
  docker inspect "$server_container" >/dev/null
  [[ "$(docker inspect -f '{{.State.Status}}' "$database_container")" == "running" ]]
  [[ "$(docker inspect -f '{{.State.Status}}' "$server_container")" == "running" ]]
}

latest_daily_summary() {
  find "$daily_dir" -maxdepth 1 -type f -name 'summary-*.json' -printf '%T@ %p\n' \
    | sort -n | tail -n 1 | cut -d' ' -f2-
}

run_daily() {
  require_live_immich

  local dump_tmp dump inventory_tmp inventory summary_tmp summary count bytes
  dump="$daily_dir/immich-db-${timestamp}.sql.gz"
  inventory="$daily_dir/library-metadata-${timestamp}.tsv.gz"
  summary="$daily_dir/summary-${timestamp}.json"
  dump_tmp="${dump}.tmp"
  inventory_tmp="${inventory}.tmp"
  summary_tmp="${summary}.tmp"

  docker exec "$database_container" sh -lc \
    'pg_dump --clean --if-exists --dbname="$POSTGRES_DB" --username="$POSTGRES_USER"' \
    | gzip -9 > "$dump_tmp"
  gzip -t "$dump_tmp"
  mv "$dump_tmp" "$dump"

  find "$upload_root" -xdev -type f -printf '%P\t%s\t%T@\n' \
    | LC_ALL=C sort | gzip -9 > "$inventory_tmp"
  gzip -t "$inventory_tmp"
  mv "$inventory_tmp" "$inventory"

  read -r count bytes < <(
    find "$upload_root" -xdev -type f -printf '%s\n' \
      | awk '{count += 1; bytes += $1} END {printf "%d %.0f\n", count, bytes}'
  )

  python3 - "$timestamp" "$count" "$bytes" "$dump" "$inventory" > "$summary_tmp" <<'PY'
import json
import os
import sys

timestamp, count, total_bytes, dump, inventory = sys.argv[1:]
print(json.dumps({
    "timestamp_utc": timestamp,
    "file_count": int(count),
    "total_bytes": int(total_bytes),
    "database_dump": os.path.basename(dump),
    "database_dump_bytes": os.path.getsize(dump),
    "metadata_inventory": os.path.basename(inventory),
    "metadata_inventory_bytes": os.path.getsize(inventory),
}, indent=2, sort_keys=True))
PY
  mv "$summary_tmp" "$summary"
  chmod 600 "$dump" "$inventory" "$summary"

  find "$daily_dir" -maxdepth 1 -type f \
    \( -name 'immich-db-*.sql.gz' -o -name 'library-metadata-*.tsv.gz' -o -name 'summary-*.json' \) \
    -mtime "+$daily_retention_days" -delete

  printf '%s\n' "$timestamp" > "$state_dir/last-daily-success"
  chmod 600 "$state_dir/last-daily-success"
  send_relay_event up "database dump and metadata inventory completed"
  echo "Immich daily protection completed: files=$count bytes=$bytes"
}

run_weekly() {
  require_live_immich
  local current previous destination
  current="$(latest_daily_summary)"
  [[ -n "$current" && -s "$current" ]]
  previous="$(find "$weekly_dir" -maxdepth 1 -type f -name 'weekly-summary-*.json' -printf '%T@ %p\n' | sort -n | tail -n 1 | cut -d' ' -f2-)"
  destination="$weekly_dir/weekly-summary-${timestamp}.json"

  python3 - "$current" "$previous" "$destination" <<'PY'
import json
import pathlib
import sys

current_path = pathlib.Path(sys.argv[1])
previous_path = pathlib.Path(sys.argv[2]) if sys.argv[2] else None
destination = pathlib.Path(sys.argv[3])
current = json.loads(current_path.read_text())
previous = json.loads(previous_path.read_text()) if previous_path and previous_path.exists() else None

result = dict(current)
result["comparison"] = {
    "previous_timestamp_utc": previous.get("timestamp_utc") if previous else None,
    "file_count_delta": current["file_count"] - previous["file_count"] if previous else None,
    "total_bytes_delta": current["total_bytes"] - previous["total_bytes"] if previous else None,
}
destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
PY
  chmod 600 "$destination"
  find "$weekly_dir" -maxdepth 1 -type f -name 'weekly-summary-*.json' -mtime +180 -delete
  printf '%s\n' "$timestamp" > "$state_dir/last-weekly-success"
  chmod 600 "$state_dir/last-weekly-success"
  send_relay_event up "weekly file-count and capacity comparison completed"
  echo "Immich weekly comparison completed"
}

run_quarterly() {
  require_live_immich
  local manifest_tmp manifest checksum
  manifest="$quarterly_dir/library-sha256-${timestamp}.txt.gz"
  checksum="$manifest.sha256"
  manifest_tmp="${manifest}.tmp"

  find "$upload_root" -xdev -type f -print0 \
    | LC_ALL=C sort -z \
    | xargs -0 -r sha256sum \
    | gzip -9 > "$manifest_tmp"
  gzip -t "$manifest_tmp"
  mv "$manifest_tmp" "$manifest"
  sha256sum "$manifest" > "$checksum"
  chmod 600 "$manifest" "$checksum"
  find "$quarterly_dir" -maxdepth 1 -type f \
    \( -name 'library-sha256-*.txt.gz' -o -name 'library-sha256-*.txt.gz.sha256' \) \
    -mtime "+$quarterly_retention_days" -delete
  printf '%s\n' "$timestamp" > "$state_dir/last-quarterly-success"
  chmod 600 "$state_dir/last-quarterly-success"
  send_relay_event up "full SHA-256 library manifest completed"
  echo "Immich quarterly SHA-256 manifest completed"
}

run_restore_test() {
  require_live_immich
  local dump table_count
  dump="$(find "$daily_dir" -maxdepth 1 -type f -name 'immich-db-*.sql.gz' -printf '%T@ %p\n' | sort -n | tail -n 1 | cut -d' ' -f2-)"
  [[ -n "$dump" && -s "$dump" ]]
  gzip -t "$dump"

  restore_database="immich_restore_test_$(date -u +%Y%m%d%H%M%S)"
  docker exec -e RESTORE_DATABASE="$restore_database" "$database_container" \
    sh -lc 'createdb --username="$POSTGRES_USER" "$RESTORE_DATABASE"'
  gzip -dc "$dump" \
    | sed "s/SELECT pg_catalog.set_config('search_path', '', false);/SELECT pg_catalog.set_config('search_path', 'public, pg_catalog', true);/g" \
    | docker exec -i -e RESTORE_DATABASE="$restore_database" "$database_container" \
      sh -lc 'psql --dbname="$RESTORE_DATABASE" --username="$POSTGRES_USER" --single-transaction --set ON_ERROR_STOP=on' \
      >/dev/null
  table_count="$(docker exec -e RESTORE_DATABASE="$restore_database" "$database_container" \
    sh -lc 'psql --dbname="$RESTORE_DATABASE" --username="$POSTGRES_USER" --tuples-only --no-align -c "select count(*) from information_schema.tables where table_schema='\''public'\'';"')"
  [[ "$table_count" =~ ^[0-9]+$ && "$table_count" -gt 0 ]]
  cleanup_restore_database
  restore_database=""
  printf '%s tables=%s\n' "$timestamp" "$table_count" > "$state_dir/last-database-restore-test"
  chmod 600 "$state_dir/last-database-restore-test"
  send_relay_event up "isolated database restore test completed"
  echo "Immich isolated database restore test completed: tables=$table_count"
}

case "$mode" in
  daily) run_daily ;;
  weekly) run_weekly ;;
  quarterly) run_quarterly ;;
  restore-test) run_restore_test ;;
  *) echo "usage: $0 {daily|weekly|quarterly|restore-test}" >&2; exit 2 ;;
esac
