# PBS Critical Operations Runbook

Proxmox Backup Server is the recovery backbone for the lab. It must be configured before Immich, Vaultwarden, Nextcloud, or Paperless contain real data.

Target VM:

| Field | Value |
|---|---|
| VM ID | `140` |
| Name | `pbs` |
| CPU | 4 vCPU |
| RAM | 8 GB |
| OS disk | 64 GB |
| Datastore | dedicated disk or dedicated storage path |
| Access | LAN/VPN only |

If PBS runs on the same P710 mirror, it protects against bad updates and accidental deletion. It does not protect against full host loss. Add offsite restic or a second PBS later.

## Phase A: Install PBS

1. Create VM 140 with [Create VM Runbook](../01_proxmox_foundation/CREATE_VM_RUNBOOK.md).
2. Install PBS from the official ISO.
3. Set static IP from the infrastructure range.
4. Update packages.
5. Enable MFA for admin access if available.

## Phase B: Create Datastore

In PBS UI:

1. Go to **Datastore**.
2. Create datastore, for example `p710-local`.
3. Put datastore on the dedicated data disk/path.
4. Record path in [Inventory and IP Plan](../99_reference/INVENTORY_AND_IP_PLAN.md).

## Phase C: Add PBS Storage to Proxmox VE

In Proxmox VE:

```text
Datacenter -> Storage -> Add -> Proxmox Backup Server
```

Recommended settings:

| Setting | Value |
|---|---|
| ID | `pbs-p710-local` |
| Server | PBS IP |
| Datastore | `p710-local` |
| Username | dedicated backup user if available |
| Fingerprint | paste PBS fingerprint |
| Content | VZDump backup file |

## Phase D: Backup Jobs

Create jobs:

| Job | Guests | Schedule | Mode |
|---|---|---|---|
| Core | LXC 100, LXC 101, LXC 102 | daily night | snapshot |
| Critical apps | VM 110, VM 120, VM 130 | daily night | snapshot |
| PBS excluded | VM 140 | separate export/offsite plan | manual |
| Media | VM 150 | weekly or daily metadata | depends on data size |

Do not back up PBS to itself as your only backup.

## Phase E: Retention, Verify, and Garbage Collection

Recommended starting retention:

```text
keep-last: 7
keep-daily: 14
keep-weekly: 8
keep-monthly: 6
```

Schedule:

| Task | Frequency |
|---|---|
| Backup | daily |
| Verify | weekly |
| Prune | after backup window |
| Garbage collection | after prune |

Verify is not optional for critical data.

## Phase F: Restore Drill

Quarterly minimum:

1. Pick one guest, preferably LXC 101 or a test copy of Immich.
2. Restore to a new VM/CT ID.
3. Boot isolated or with temporary IP.
4. Verify login, files, service health, and logs.
5. Record restore time and result.

Record:

```text
Date:
Source backup:
Target VM/CT:
Restore duration:
Validation:
Issues:
Next action:
```

## Phase G: App-Aware Critical Backups

PBS is not enough for every application failure. Add app-aware/offsite backup for:

| App | App-aware backup |
|---|---|
| Vaultwarden | encrypted export + data volume |
| Immich | DB dump + upload directory from same point |
| Paperless | DB dump + media/export/consume |
| Authentik | PostgreSQL + media + `.env` |
| Forgejo | DB + repositories |

## Phase H: Offsite Path

Minimum restic command pattern:

```bash
export RESTIC_REPOSITORY=/mnt/offsite/sovereign
export RESTIC_PASSWORD_FILE=/root/.config/restic/sovereign.pass
restic init
restic backup /opt/sovereign /opt/core-network
restic check
restic forget --keep-daily 14 --keep-weekly 8 --keep-monthly 6 --prune
```

Keep the restic password outside Git and outside the server if possible.

---

**Previous:** [Runbook 09: Backup and DR](doc_09_backup_dr.md)
**Next:** [Runbook 10: Core Apps](../04_apps/doc_10_core_apps.md)
