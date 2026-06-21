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

Live state as of 2026-06-22:

| Item | Value |
|---|---|
| VM | `140` `pbs` |
| IP | `192.168.1.20` |
| Datastore | `p710-local` |
| Datastore path | `/mnt/datastore/p710-local` |
| PVE storage ID | `pbs-p710` |
| Integration auth | dedicated PBS user/token stored only on the server |
| Scheduled job | `sovereign-core-nightly`, guests `100,101,102,110`, daily `03:00` |
| Completed backups | LXC 101, LXC 102, VM 110 |
| Restore drill | LXC 101 restored to temporary CT `901`, mounted, verified, destroyed |
| Pending restore drills | LXC 102 `apps-light`, VM 110 `immich`, and app-aware critical data restores |

## Phase A: Install PBS

1. Create VM 140 with [Create VM Runbook](../01_proxmox_foundation/CREATE_VM_RUNBOOK.md).
2. Install PBS either from the official ISO or from Debian using the official PBS repository.
3. Set static IP from the infrastructure range.
4. Update packages.
5. Enable MFA for admin access if available.

Debian-based install pattern used in the live build:

```bash
apt-get update
apt-get install -y wget ca-certificates gnupg qemu-guest-agent
wget -q https://enterprise.proxmox.com/debian/proxmox-archive-keyring-trixie.gpg \
  -O /usr/share/keyrings/proxmox-archive-keyring.gpg

cat >/etc/apt/sources.list.d/proxmox.sources <<'EOF'
Types: deb
URIs: http://download.proxmox.com/debian/pbs
Suites: trixie
Components: pbs-no-subscription
Signed-By: /usr/share/keyrings/proxmox-archive-keyring.gpg
EOF

apt-get update
apt-get install -y proxmox-backup-server
```

## Phase B: Create Datastore

In PBS UI:

1. Go to **Datastore**.
2. Create datastore, for example `p710-local`.
3. Put datastore on the dedicated data disk/path.
4. Record path in [Inventory and IP Plan](../99_reference/INVENTORY_AND_IP_PLAN.md).

CLI pattern:

```bash
mkfs.ext4 -L pbs-p710-local /dev/sdb
mkdir -p /mnt/datastore/p710-local
UUID=$(blkid -s UUID -o value /dev/sdb)
echo "UUID=$UUID /mnt/datastore/p710-local ext4 defaults,noatime 0 2" >> /etc/fstab
mount -a
chown backup:backup /mnt/datastore/p710-local
proxmox-backup-manager datastore create p710-local /mnt/datastore/p710-local
```

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

Live storage ID is `pbs-p710`. The token requires enough datastore rights for the selected retention behavior. In PBS 4.2, `DatastorePowerUser` plus `DatastoreReader` on the datastore allowed PVE backup, read, verify, and prune of owned backups.

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

Live restore drill record:

```text
Date: 2026-06-21
Source backup: pbs-p710:backup/ct/101/2026-06-21T18:18:54Z
Target VM/CT: temporary CT 901
Restore duration: under 2 minutes
Validation: restored config, mounted rootfs, verified /opt/sovereign-homelab/stacks files
Issues: restored CT retained original static IP, so it was not started to avoid conflict
Next action: repeat with an app VM before importing critical data
```

Additional live backup evidence:

| Date | Guest | Result | Notes |
|---|---|---|---|
| 2026-06-22 | LXC 102 `apps-light` | backup completed | restore drill still pending |
| 2026-06-22 | VM 110 `immich` | backup completed | valid after correcting the Immich data disk to 500 GB |

Do not treat these backups as production-ready for personal data until a restore drill proves that the guest and application data are usable.

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
restic backup /opt/sovereign-homelab /opt/core-network
restic check
restic forget --keep-daily 14 --keep-weekly 8 --keep-monthly 6 --prune
```

Keep the restic password outside Git and outside the server if possible.

---

**Previous:** [Runbook 09: Backup and DR](doc_09_backup_dr.md)
**Next:** [Runbook 10: Core Apps](../04_apps/doc_10_core_apps.md)
