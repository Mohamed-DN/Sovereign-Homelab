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

Live state as of 2026-06-23:

| Item | Value |
|---|---|
| VM | `140` `pbs` |
| IP | `192.168.1.20` |
| Datastore | `p710-local` |
| Datastore path | `/mnt/datastore/p710-local` |
| PVE storage ID | `pbs-p710` |
| Integration auth | dedicated PBS user/token stored only on the server |
| Scheduled job | `sovereign-core-nightly`, guests `100,101,102,103,110,120,130`, daily `03:00` |
| Completed backups | LXC 101, LXC 102, LXC 103, VM 110, VM 120, VM 130 |
| Restore drills | LXC 101 restored to temporary CT `901`, LXC 102 restored to temporary CT `902`, LXC 103 restored to temporary CT `903`, VM 110 restored to temporary VM `910`, VM 120 restored to temporary VM `920`, and VM 130 restored to temporary VM `930`; all temporary restore targets were verified and destroyed |
| File-level VM validation | VM 110 `immich` was inspected with `proxmox-file-restore` and expected app/data paths were visible |
| App-aware baseline drills | LXC102 Vaultwarden SQLite integrity, Paperless temporary DB restore, Forgejo temporary DB restore, LXC102 volume manifests, and VM110 Immich temporary DB restore plus library manifests completed |
| Pending restore drills | representative production-data restore rehearsals and offsite disaster-recovery restore |

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
| Core | LXC 100, LXC 101, LXC 102, LXC 103 | daily night | snapshot |
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

### Safe LXC Restore Drill Without IP Conflict

Use this pattern for LXC 102 or LXC 103 when you want to verify the backup contents without starting a clone that has the same static IP as production:

```bash
TMPID=903
SOURCE_VMID=103

if pct status "$TMPID" >/dev/null 2>&1 || qm status "$TMPID" >/dev/null 2>&1; then
  echo "temporary ID $TMPID already exists"
  exit 1
fi

BACKUP=$(pvesm list pbs-p710 --vmid "$SOURCE_VMID" \
  | awk "/backup\\/ct\\/${SOURCE_VMID}\\// {print \\$1}" \
  | sort \
  | tail -n 1)

pct restore "$TMPID" "$BACKUP" --storage local-zfs --unique 1
pct mount "$TMPID"

ROOT=/var/lib/lxc/$TMPID/rootfs
find "$ROOT/opt" -maxdepth 4 -type f \( -name 'docker-compose.yml' -o -name '.env' \) | sort
find "$ROOT/var/lib/docker/volumes" -maxdepth 2 -mindepth 1 -type d | sort | head -80

pct unmount "$TMPID"
pct destroy "$TMPID" --purge 1
```

Accepted result:

- the backup restores into the temporary ID;
- the stack path exists;
- Docker volumes are present;
- the temporary CT is unmounted and destroyed;
- production CT remains untouched.

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
| 2026-06-23 | LXC 102 `apps-light` | restore drill completed | temporary CT `902` restored, mounted, stack files and Docker volumes verified, destroyed |
| 2026-06-23 | VM 110 `immich` | file-level restore validation completed | OS disk, Immich upload tree, backups directory, generated media directories, and PostgreSQL data visible |
| 2026-06-23 | VM 110 `immich` | full boot/service restore drill completed | temporary VM `910` restored on `local-zfs`, booted on `192.168.1.241`, `/mnt/immich-library` mounted, all Immich containers healthy, API returned `{"res":"pong"}`, VM `910` destroyed |
| 2026-06-23 | VM 120 `nextcloud-aio` | file-level restore validation completed | OS stack path and Nextcloud data directory visible |
| 2026-06-23 | VM 120 `nextcloud-aio` | full boot/service restore drill completed | temporary VM `920` restored on `local-zfs`, first boot isolated with `link_down=1`, then moved to temporary IP `192.168.1.240`; all AIO containers healthy, `occ status` clean, local Apache returned login redirect, VM `920` destroyed |
| 2026-06-23 | VM 130 `home-assistant-os` | file-level restore validation completed | HAOS data partition and supervisor/Home Assistant directories visible |
| 2026-06-23 | VM 130 `home-assistant-os` | full boot/service restore drill completed | temporary VM `930` restored on `local-zfs`, NIC isolated with `link_down=1`, HA Core and Supervisor verified healthy through the guest agent, then VM `930` destroyed |
| 2026-06-23 | VM 130 `home-assistant-os` | native HA backup created | `sovereign-preproduction-2026-06-23`, slug `2b41594a`, full backup including database |
| 2026-06-23 | LXC 102 app-aware baseline | completed | output `/root/sovereign-app-restore-drills/20260623T153506Z`; Vaultwarden SQLite integrity `ok`; Paperless temp DB restore found 72 public tables; Forgejo temp DB restore found 121 public tables; critical Docker volume manifests and `SHA256SUMS` created |
| 2026-06-23 | VM 110 Immich app-aware baseline | completed | output `/root/sovereign-app-restore-drills/20260623T153701Z`; Immich PostgreSQL dump restored into a temporary DB with 61 public tables; manifests created for `/mnt/immich-library` with 32852 files and `/opt/sovereign-homelab` with 3 files; `SHA256SUMS` created |

Do not treat VM backups as fully production-ready for irreplaceable personal data until a boot/service restore drill proves that the guest and application data are usable, and an app-aware restore proves that the database and data directory can be recovered together. The 2026-06-23 app-aware baselines prove the mechanics on current data; repeat them with representative real datasets and an offsite copy before trusting the lab with irreplaceable photos, passwords, documents, or repositories.

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
