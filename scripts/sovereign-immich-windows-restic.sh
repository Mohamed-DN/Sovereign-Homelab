#!/usr/bin/env bash
set -Eeuo pipefail

# Temporary encrypted Immich mirror to a Windows PC over SFTP.
#
# This is TEMPORARY risk reduction, not a full 3-2-1 backup. It exists only
# until the external SSD and a real offsite restore test have passed. It runs
# on VM 110 and pushes to a restic repository that lives on an occasionally
# online Windows PC (C:\Sovereign-Backups\immich-restic).
#
# Design rules honoured here:
#   - VM 110 never polls the Windows PC on a schedule. The run is event
#     triggered (Windows logon/startup task) or manual.
#   - Reachability is checked once with a short timeout; if the Windows PC is
#     offline the run exits cleanly instead of hanging or restarting Immich.
#   - Every run creates a fresh PostgreSQL dump so the database and the file
#     tree always match in the same consistent snapshot.
#   - Only immich-server is briefly stopped. A trap restarts it even on error.
#   - The Immich asset tree is only ever read, never edited or deleted.

mode="${1:-preflight}"
restore_target="${2:-}"

secret_dir="${IMMICH_WINDOWS_SECRET_DIR:-/root/sovereign-secrets/immich-windows}"
repository_file="${IMMICH_WINDOWS_RESTIC_REPOSITORY_FILE:-$secret_dir/restic-repository}"
password_file="${IMMICH_WINDOWS_RESTIC_PASSWORD_FILE:-$secret_dir/restic-password}"
ssh_command_file="${IMMICH_WINDOWS_RESTIC_SSH_COMMAND_FILE:-$secret_dir/restic-ssh-command}"
endpoint_file="${IMMICH_WINDOWS_ENDPOINT_FILE:-$secret_dir/target-endpoint}"
state_dir="${IMMICH_WINDOWS_STATE_DIR:-$secret_dir/state}"
state_file="$state_dir/last-mirror.json"

stack_dir="${IMMICH_STACK_DIR:-/opt/sovereign-homelab/stacks/immich}"
upload_root="${IMMICH_UPLOAD_ROOT:-/mnt/immich-library/upload}"
stage_dir="${IMMICH_WINDOWS_STAGE_DIR:-/root/sovereign-immich-windows-staging}"
database_container="${IMMICH_DATABASE_CONTAINER:-immich-database}"
server_container="${IMMICH_SERVER_CONTAINER:-immich-server}"
reach_timeout="${IMMICH_WINDOWS_REACH_TIMEOUT:-6}"
lock_file="/run/lock/sovereign-immich-windows-restic.lock"

server_stopped=0

exec 9>"$lock_file"
if ! flock -n 9; then
  echo "another Windows Immich mirror operation is running" >&2
  exit 1
fi

cleanup() {
  local exit_code=$?
  if [[ "$server_stopped" -eq 1 ]]; then
    docker start "$server_container" >/dev/null || true
    server_stopped=0
  fi
  exit "$exit_code"
}
trap cleanup EXIT INT TERM

require_secret_file() {
  local path="$1"
  [[ -s "$path" ]] || { echo "required root-only file is missing: $path" >&2; exit 1; }
  local mode_bits
  mode_bits="$(stat -c '%a' "$path")"
  [[ "$mode_bits" == "600" || "$mode_bits" == "400" ]] || {
    echo "secret file must have mode 600 or 400: $path" >&2
    exit 1
  }
}

load_config() {
  [[ "$EUID" -eq 0 ]] || { echo "run as root on VM 110" >&2; exit 1; }
  command -v restic >/dev/null
  command -v docker >/dev/null
  require_secret_file "$repository_file"
  require_secret_file "$password_file"
  require_secret_file "$ssh_command_file"
  require_secret_file "$endpoint_file"

  export RESTIC_REPOSITORY_FILE="$repository_file"
  export RESTIC_PASSWORD_FILE="$password_file"
  restic_repository="$(<"$repository_file")"
  restic_ssh_command="$(<"$ssh_command_file")"
  read -r target_host target_port < <(tr ',' ' ' < "$endpoint_file")
  target_port="${target_port:-22}"

  [[ "$restic_repository" == sftp:* ]] || {
    echo "the Windows mirror repository must use the SFTP target on the Windows PC" >&2
    exit 1
  }
  [[ "$restic_ssh_command" == ssh\ * ]] || {
    echo "restic SSH command must start with ssh" >&2
    exit 1
  }
  [[ -n "$target_host" ]] || { echo "target-endpoint must contain the Windows host" >&2; exit 1; }
}

restic_run() {
  restic -o "sftp.command=$restic_ssh_command" "$@"
}

target_reachable() {
  # Single short-timeout TCP probe. This is not a background poll; it runs only
  # when the operator or the Windows logon task triggers a mirror run.
  timeout "$reach_timeout" bash -c "exec 3<>/dev/tcp/$target_host/$target_port" 2>/dev/null
}

require_sources() {
  [[ -d "$stack_dir" ]]
  [[ -d "$upload_root" ]]
  docker inspect "$database_container" "$server_container" >/dev/null
  [[ "$(docker inspect -f '{{.State.Status}}' "$database_container")" == "running" ]]
  [[ "$(docker inspect -f '{{.State.Status}}' "$server_container")" == "running" ]]
}

preflight() {
  load_config
  require_sources
  if ! target_reachable; then
    echo "Windows PC $target_host:$target_port is offline; mirror skipped (this is expected when the PC is off)"
    exit 0
  fi
  restic_run cat config >/dev/null
  echo "Windows Immich mirror preflight passed"
}

create_database_dump() {
  install -d -m 0700 "$stage_dir"
  local dump_tmp="$stage_dir/database.sql.gz.tmp"
  local dump="$stage_dir/database.sql.gz"
  docker exec "$database_container" sh -lc \
    'pg_dump --clean --if-exists --dbname="$POSTGRES_DB" --username="$POSTGRES_USER"' \
    | gzip -9 > "$dump_tmp"
  gzip -t "$dump_tmp"
  mv "$dump_tmp" "$dump"
  chmod 600 "$dump"
}

write_recovery_metadata() {
  local metadata_tmp="$stage_dir/recovery-metadata.txt.tmp"
  {
    printf 'created_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'hostname=%s\n' "$(hostname -f 2>/dev/null || hostname)"
    printf 'immich_server_image=%s\n' "$(docker inspect -f '{{.Config.Image}}' "$server_container")"
    printf 'immich_database_image=%s\n' "$(docker inspect -f '{{.Config.Image}}' "$database_container")"
    printf 'upload_files=%s\n' "$(find "$upload_root" -xdev -type f | wc -l)"
    printf 'upload_bytes=%s\n' "$(find "$upload_root" -xdev -type f -printf '%s\n' | awk '{n+=$1} END {printf "%.0f", n}')"
  } > "$metadata_tmp"
  mv "$metadata_tmp" "$stage_dir/recovery-metadata.txt"
  chmod 600 "$stage_dir/recovery-metadata.txt"
}

write_state() {
  # Aggregate-only status for the weekly report. No personal filenames.
  local check_result="$1"
  install -d -m 0700 "$state_dir"
  local snapshot_id snapshot_time files bytes tmp
  snapshot_id="$(restic_run snapshots --tag immich-windows-consistent --latest 1 --json 2>/dev/null \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d[-1]["short_id"] if d else "")' 2>/dev/null || true)"
  snapshot_time="$(restic_run snapshots --tag immich-windows-consistent --latest 1 --json 2>/dev/null \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d[-1]["time"] if d else "")' 2>/dev/null || true)"
  files="$(grep -oP '^upload_files=\K.*' "$stage_dir/recovery-metadata.txt" 2>/dev/null || echo "")"
  bytes="$(grep -oP '^upload_bytes=\K.*' "$stage_dir/recovery-metadata.txt" 2>/dev/null || echo "")"
  tmp="$state_file.tmp"
  python3 - "$snapshot_id" "$snapshot_time" "$files" "$bytes" "$check_result" > "$tmp" <<'PY'
import json
import sys
from datetime import datetime, timezone

snapshot_id, snapshot_time, files, bytes_, check_result = sys.argv[1:6]
print(json.dumps({
    "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "snapshot_id": snapshot_id or None,
    "snapshot_time": snapshot_time or None,
    "upload_files": int(files) if files.isdigit() else None,
    "upload_bytes": int(bytes_) if bytes_.isdigit() else None,
    "check_result": check_result,
}, indent=2, sort_keys=True))
PY
  mv "$tmp" "$state_file"
  chmod 600 "$state_file"
}

backup() {
  load_config
  require_sources
  if ! target_reachable; then
    echo "Windows PC $target_host:$target_port is offline; mirror skipped (this is expected when the PC is off)"
    exit 0
  fi
  restic_run cat config >/dev/null

  echo "Pre-copying the live asset tree to reduce the final maintenance window..."
  restic_run backup \
    --host immich-vm110 \
    --tag immich-windows-precopy \
    --exclude-caches \
    "$upload_root" "$stack_dir"

  echo "Stopping only the Immich server for a consistent final snapshot..."
  docker stop --time 120 "$server_container" >/dev/null
  server_stopped=1

  create_database_dump
  write_recovery_metadata

  restic_run backup \
    --host immich-vm110 \
    --tag immich-windows-consistent \
    --exclude-caches \
    "$upload_root" "$stack_dir" "$stage_dir"

  docker start "$server_container" >/dev/null
  server_stopped=0
  for _ in $(seq 1 60); do
    if [[ "$(docker inspect -f '{{.State.Status}}' "$server_container")" == "running" ]]; then
      break
    fi
    sleep 2
  done
  [[ "$(docker inspect -f '{{.State.Status}}' "$server_container")" == "running" ]]

  restic_run forget --tag immich-windows-precopy --keep-last 2
  restic_run forget --tag immich-windows-consistent \
    --keep-last 3 --keep-daily 7 --keep-weekly 8 --keep-monthly 12

  echo "Running a light integrity check on the mirror repository..."
  local check_result="passed"
  if ! restic_run check; then
    check_result="failed"
  fi
  write_state "$check_result"

  restic_run snapshots --tag immich-windows-consistent --latest 1
  if [[ "$check_result" == "failed" ]]; then
    echo "WARNING: mirror snapshot was written but restic check failed; investigate before trusting this copy" >&2
    exit 1
  fi
  echo "Windows Immich mirror completed and light check passed"
}

check_repository() {
  load_config
  if ! target_reachable; then
    echo "Windows PC $target_host:$target_port is offline; cannot check the mirror now"
    exit 0
  fi
  restic_run check --read-data-subset=5%
  restic_run snapshots --tag immich-windows-consistent --latest 3
}

show_snapshots() {
  load_config
  if ! target_reachable; then
    echo "Windows PC $target_host:$target_port is offline; cannot list snapshots now"
    exit 0
  fi
  restic_run snapshots --tag immich-windows-consistent
}

restore_copy() {
  load_config
  [[ -n "$restore_target" ]] || { echo "restore-check requires an empty target path" >&2; exit 2; }
  [[ ! -e "$restore_target" ]] || { echo "restore target already exists: $restore_target" >&2; exit 1; }
  target_reachable || { echo "Windows PC is offline; connect it before a restore check" >&2; exit 1; }
  install -d -m 0700 "$restore_target"
  restic_run restore latest --tag immich-windows-consistent --target "$restore_target"
  [[ -s "$restore_target$stage_dir/database.sql.gz" ]]
  [[ -d "$restore_target$upload_root" ]]
  echo "Windows mirror restore copy completed at $restore_target; do not start it as production"
}

case "$mode" in
  preflight) preflight ;;
  backup) backup ;;
  check) check_repository ;;
  snapshots) show_snapshots ;;
  restore-check) restore_copy ;;
  *) echo "usage: $0 {preflight|backup|check|snapshots|restore-check <empty-target>}" >&2; exit 2 ;;
esac
