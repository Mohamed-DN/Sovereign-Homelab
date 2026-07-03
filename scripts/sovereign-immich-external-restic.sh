#!/usr/bin/env bash
set -Eeuo pipefail

mode="${1:-preflight}"
restore_target="${2:-}"
repository_file="${IMMICH_RESTIC_REPOSITORY_FILE:-/root/sovereign-secrets/immich-external/restic-repository}"
password_file="${IMMICH_RESTIC_PASSWORD_FILE:-/root/sovereign-secrets/immich-external/restic-password}"
ssh_command_file="${IMMICH_RESTIC_SSH_COMMAND_FILE:-/root/sovereign-secrets/immich-external/restic-ssh-command}"
stack_dir="${IMMICH_STACK_DIR:-/opt/sovereign-homelab/stacks/immich}"
upload_root="${IMMICH_UPLOAD_ROOT:-/mnt/immich-library/upload}"
stage_dir="${IMMICH_EXTERNAL_STAGE_DIR:-/root/sovereign-immich-external-staging}"
database_container="${IMMICH_DATABASE_CONTAINER:-immich-database}"
server_container="${IMMICH_SERVER_CONTAINER:-immich-server}"
lock_file="/run/lock/sovereign-immich-external-restic.lock"

server_stopped=0

exec 9>"$lock_file"
if ! flock -n 9; then
  echo "another external Immich restic operation is running" >&2
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

  export RESTIC_REPOSITORY_FILE="$repository_file"
  export RESTIC_PASSWORD_FILE="$password_file"
  restic_repository="$(<"$repository_file")"
  restic_ssh_command="$(<"$ssh_command_file")"
  [[ "$restic_repository" == sftp:* ]] || {
    echo "the portable repository must use the external PBS SFTP target" >&2
    exit 1
  }
  [[ "$restic_ssh_command" == ssh\ * ]] || {
    echo "restic SSH command must start with ssh" >&2
    exit 1
  }
}

restic_run() {
  restic -o "sftp.command=$restic_ssh_command" "$@"
}

require_sources() {
  [[ -d "$stack_dir" ]]
  [[ -d "$upload_root" ]]
  [[ "$(findmnt -n -o FSTYPE --target "$upload_root")" == "ext4" ]]
  docker inspect "$database_container" "$server_container" >/dev/null
  [[ "$(docker inspect -f '{{.State.Status}}' "$database_container")" == "running" ]]
  [[ "$(docker inspect -f '{{.State.Status}}' "$server_container")" == "running" ]]
}

preflight() {
  load_config
  require_sources
  restic_run cat config >/dev/null
  echo "external Immich restic preflight passed"
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

backup() {
  load_config
  require_sources
  restic_run cat config >/dev/null

  echo "Pre-copying the live asset tree to reduce the final maintenance window..."
  restic_run backup \
    --host immich-vm110 \
    --tag immich-precopy \
    --exclude-caches \
    "$upload_root" "$stack_dir"

  echo "Stopping only the Immich server for a consistent final snapshot..."
  docker stop --time 120 "$server_container" >/dev/null
  server_stopped=1

  create_database_dump
  write_recovery_metadata

  restic_run backup \
    --host immich-vm110 \
    --tag immich-consistent \
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

  restic_run forget --tag immich-precopy --keep-last 2
  restic_run forget --tag immich-consistent \
    --keep-last 3 --keep-daily 7 --keep-weekly 8 --keep-monthly 12

  restic_run snapshots --tag immich-consistent --latest 1
  echo "portable Immich backup completed; run the check mode before disconnecting the SSD"
}

check_repository() {
  load_config
  restic_run check --read-data-subset=5%
  restic_run snapshots --tag immich-consistent --latest 3
}

show_snapshots() {
  load_config
  restic_run snapshots --tag immich-consistent
}

restore_copy() {
  load_config
  [[ -n "$restore_target" ]] || { echo "restore-check requires an empty target path" >&2; exit 2; }
  [[ ! -e "$restore_target" ]] || { echo "restore target already exists: $restore_target" >&2; exit 1; }
  install -d -m 0700 "$restore_target"
  restic_run restore latest --tag immich-consistent --target "$restore_target"
  [[ -s "$restore_target$stage_dir/database.sql.gz" ]]
  [[ -d "$restore_target$upload_root" ]]
  echo "portable restore copy completed at $restore_target; do not start it as production"
}

case "$mode" in
  preflight) preflight ;;
  backup) backup ;;
  check) check_repository ;;
  snapshots) show_snapshots ;;
  restore-check) restore_copy ;;
  *) echo "usage: $0 {preflight|backup|check|snapshots|restore-check <empty-target>}" >&2; exit 2 ;;
esac
