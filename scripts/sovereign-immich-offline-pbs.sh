#!/usr/bin/env bash
set -Eeuo pipefail

mode="${1:-status}"
vmid="${IMMICH_VMID:-110}"
storage_id="${IMMICH_EXTERNAL_PBS_STORAGE:-pbs-immich-offline}"
local_storage_id="${IMMICH_LOCAL_PBS_STORAGE:-pbs-p710}"
lock_file="/run/lock/sovereign-immich-offline-pbs.lock"

exec 9>"$lock_file"
if ! flock -n 9; then
  echo "another offline Immich PBS operation is running" >&2
  exit 1
fi

require_root() {
  [[ "$EUID" -eq 0 ]] || { echo "run as root on the Proxmox host" >&2; exit 1; }
}

require_target() {
  [[ "$storage_id" != "$local_storage_id" ]] || {
    echo "external storage ID must differ from local PBS storage" >&2
    exit 1
  }
  qm status "$vmid" | grep -q 'status: running'
  pvesm status --storage "$storage_id" | awk -v id="$storage_id" '$1 == id && $3 == "active" {found=1} END {exit !found}'
  pvesm status --storage "$storage_id" | grep -q 'pbs'
}

show_status() {
  echo "VM ${vmid}:"
  qm status "$vmid"
  echo
  echo "External storage ${storage_id}:"
  pvesm status --storage "$storage_id" || true
  echo
  echo "Existing external snapshots:"
  pvesm list "$storage_id" --content backup --vmid "$vmid" || true
}

run_backup() {
  require_target

  echo "Running the VM110 app-aware database and metadata checkpoint..."
  qm guest exec "$vmid" --timeout 7200 -- \
    systemctl start sovereign-immich-protection@daily.service >/dev/null

  echo "Creating a full VM snapshot on ${storage_id}..."
  vzdump "$vmid" \
    --storage "$storage_id" \
    --mode snapshot \
    --remove 0 \
    --notes-template 'Immich external SSD recovery {{guestname}} {{vmid}}'

  echo "External snapshots after backup:"
  pvesm list "$storage_id" --content backup --vmid "$vmid"
  echo "Backup completed. Run PBS verification before unmounting the SSD."
}

require_root
case "$mode" in
  status) show_status ;;
  backup) run_backup ;;
  *) echo "usage: $0 {status|backup}" >&2; exit 2 ;;
esac
