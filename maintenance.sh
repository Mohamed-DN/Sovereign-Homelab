#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./maintenance.sh [--apply]

Default mode is a non-destructive check. Use --apply only after PBS/restic coverage is verified.

Optional environment variables:
  ZFS_DATASET       Dataset to snapshot before updates, for example rpool/data.
  SKIP_DOCKER_PULL  Set to 1 to skip image pulls in --apply mode.

Safety rules:
  - This script never prunes Docker volumes.
  - This script never deletes app data.
  - ZFS snapshots are skipped unless ZFS_DATASET is explicitly set.
USAGE
}

APPLY=0
if [[ "${1:-}" == "--apply" ]]; then
  APPLY=1
elif [[ $# -gt 0 ]]; then
  usage
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACKS_DIR="$ROOT_DIR/stacks"
SNAP_NAME="maintenance-$(date +%F-%H%M)"

echo "Sovereign Homelab maintenance"
echo "Mode: $([[ "$APPLY" -eq 1 ]] && echo apply || echo check-only)"

if [[ -n "${ZFS_DATASET:-}" ]]; then
  if command -v zfs >/dev/null 2>&1; then
    echo "Checking ZFS dataset: $ZFS_DATASET"
    zfs list "$ZFS_DATASET" >/dev/null
    if [[ "$APPLY" -eq 1 ]]; then
      echo "Creating recursive ZFS snapshot: ${ZFS_DATASET}@${SNAP_NAME}"
      sudo zfs snapshot -r "${ZFS_DATASET}@${SNAP_NAME}"
    else
      echo "Would create recursive ZFS snapshot: ${ZFS_DATASET}@${SNAP_NAME}"
    fi
  else
    echo "ERROR: ZFS_DATASET is set but zfs command is not available." >&2
    exit 1
  fi
else
  echo "ZFS_DATASET not set; skipping ZFS snapshot."
fi

for dir in "$STACKS_DIR"/*/; do
  [[ -f "${dir}docker-compose.yml" ]] || continue
  stack_name="$(basename "$dir")"
  env_file="${dir}.env"

  echo "========================================"
  echo "Stack: $stack_name"

  if [[ ! -f "$env_file" ]]; then
    echo "Skipping: .env is missing. Copy .env.example and fill secrets before deployment."
    continue
  fi

  (
    cd "$dir"
    docker compose --env-file "$env_file" config --quiet

    if [[ "$APPLY" -eq 1 ]]; then
      if [[ "${SKIP_DOCKER_PULL:-0}" != "1" ]]; then
        docker compose --env-file "$env_file" pull
      fi
      docker compose --env-file "$env_file" up -d --remove-orphans
    else
      docker compose --env-file "$env_file" ps
    fi
  )
done

echo "========================================"
echo "Docker cleanup guidance:"
echo "  Safe image cleanup, manual only: docker image prune"
echo "  Do not run docker volume prune unless every anonymous volume has been audited."
echo "Maintenance complete."
