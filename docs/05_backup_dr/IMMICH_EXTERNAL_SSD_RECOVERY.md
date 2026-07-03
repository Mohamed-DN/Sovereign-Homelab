# Immich External SSD Recovery

This runbook prepares a 2 TB external SSD as a physically separate recovery medium for Immich. It does not replace local PBS. It adds a second medium that can be disconnected and used after loss of the P710.

The SSD is not currently attached. Do not run initialization commands until its stable device identity has been reviewed twice.

## Recovery Objectives

The SSD must support two independent outcomes:

1. **Full-service restore:** recover VM 110 from a PBS removable datastore onto a fresh Proxmox/PBS installation.
2. **Portable application restore:** recover the Immich database, original assets, and deployment files from an encrypted restic repository without depending on the original PBS database.

The two formats protect against different failures. A full VM restore is fastest. The portable copy is easier to inspect and migrate if the original virtualization layout no longer exists.

## Current Capacity Fit

Verified on 2026-07-03:

| Item | Current value |
|---|---:|
| Immich original/upload tree | about 90 GB |
| VM 110 data disk | 500 GB |
| VM 110 OS disk | 120 GB |
| External SSD target | 2 TB nominal |

The SSD has sufficient initial capacity for several deduplicated PBS snapshots and an encrypted portable copy. Capacity must still be checked before every run; provisioned virtual disk size is not the same as bytes stored on the SSD.

## Safety Rules

- Use only `/dev/disk/by-id/<stable-id>`, never `/dev/sdX` in a saved command.
- Disconnect every other removable disk during initialization.
- Record model, serial, size, and by-id path before formatting.
- Never pass the P710 mirror disks or NVMe boot device to PBS.
- Never mount one external datastore on two PBS instances simultaneously.
- Keep the restic password and PBS encryption key outside the SSD and outside Git.
- Do not use `--remove-vanished` on the external sync job.
- Do not delete phone originals until two independent restores have passed.
- Unmount the datastore through PBS before unplugging the SSD.

## Target Layout

Use one ext4 filesystem on the SSD. Create two non-nested directories on it:

```text
/
|-- pbs/
|   `-- PBS removable datastore for VM 110 snapshots
|-- portable-restic/
|   `-- encrypted Immich application repository
`-- recovery/
    |-- README.txt
    |-- root-ca.crt
    `-- public runbooks and checksums only
```

Do not place secrets in `recovery/`. The restic password and any PBS client-side encryption key need a second recovery location such as a printed sealed copy and the password vault.

## Phase 1: Identify the SSD on Proxmox

Connect the SSD and run on Proxmox:

```bash
lsblk -e7 -o NAME,PATH,SIZE,MODEL,SERIAL,TRAN,FSTYPE,MOUNTPOINTS
ls -l /dev/disk/by-id/
```

Record the intended device in the root-only inventory:

```text
model=<expected model>
serial=<expected serial>
size=<approximately 2 TB>
by_id=/dev/disk/by-id/<stable-id>
```

Stop if any value is unexpected.

## Phase 2: Pass the Whole Device to PBS VM 140

Shut down PBS before adding the raw device. Use the stable by-id path:

```bash
qm shutdown 140 --timeout 120
qm set 140 -scsi2 /dev/disk/by-id/<stable-id>,backup=0,discard=on,ssd=1
qm start 140
```

`backup=0` prevents the removable SSD from being included inside the backup of PBS itself. Confirm inside PBS that the new disk has the expected model, serial, and size before continuing.

Rollback before formatting:

```bash
qm shutdown 140 --timeout 120
qm set 140 -delete scsi2
qm start 140
```

## Phase 3: Create the Removable Datastore

Use the PBS GUI because it clearly shows the selected disk:

1. Open `https://pbs.internal`.
2. Go to **Administration -> Storage/Disks**.
3. Match model, serial, and size with the root-only inventory.
4. Create an ext4 directory filesystem on the unused disk.
5. Add a removable datastore named `immich-offline` with relative path `pbs`.
6. Enable `gc-on-unmount`.
7. Do not configure automatic pruning until the first copy and restore test pass.

PBS supports removable datastores and multiple non-nested datastore paths on one device. The relative path is important when reusing the disk on a fresh PBS installation.

Validate:

```bash
proxmox-backup-manager datastore show immich-offline
proxmox-backup-debug inspect device /dev/disk/by-id/<stable-id>
findmnt /mnt/datastore/immich-offline
```

Create the sibling directories on the mounted filesystem only after confirming the mount source:

```bash
install -d -m 0700 -o backup -g backup \
  /mnt/datastore/immich-offline/portable-restic
install -d -m 0750 -o root -g backup \
  /mnt/datastore/immich-offline/recovery
```

## Phase 4: Add the External PBS Storage to Proxmox

Create a dedicated PBS API token with backup-only access to `/datastore/immich-offline`. Add a new Proxmox storage named `pbs-immich-offline`. Keep its token and optional client-side encryption key root-only.

Do not schedule a normal nightly job against a removable disk. Run the backup only while the datastore is mounted:

```bash
/usr/local/sbin/sovereign-immich-offline-pbs backup
```

The helper refuses to continue unless VM 110 is running, the external storage is active, and the target storage is not the local PBS datastore.

## Phase 5: Configure the Portable Restic Repository

Install restic on VM 110. Provide access to the SSD repository using a dedicated, restricted SFTP account on PBS. The account must be confined to the external repository path and must not have PBS administration access.

Create these VM 110 root-only files:

```text
/root/sovereign-secrets/immich-external/restic-repository
/root/sovereign-secrets/immich-external/restic-password
/root/sovereign-secrets/immich-external/restic-ssh-command
```

Example repository value:

```text
sftp:immich-backup@192.168.1.20:/portable-restic
```

The SSH command file should select a dedicated private key and pin the PBS host key. Initialize once:

```bash
RESTIC_REPOSITORY_FILE=/root/sovereign-secrets/immich-external/restic-repository \
RESTIC_PASSWORD_FILE=/root/sovereign-secrets/immich-external/restic-password \
restic init
```

Install the repository helper from `scripts/sovereign-immich-external-restic.sh` and run:

```bash
/usr/local/sbin/sovereign-immich-external-restic backup
/usr/local/sbin/sovereign-immich-external-restic check
```

The first run performs a live pre-copy, briefly stops only `immich-server`, creates a fresh PostgreSQL dump, and commits a final consistent restic snapshot. A trap restarts the server even if the backup fails. It never deletes or edits the Immich asset tree.

## Phase 6: Verify Before Disconnecting

Full VM copy:

```bash
pvesm list pbs-immich-offline --content backup --vmid 110
```

Portable copy on VM 110:

```bash
/usr/local/sbin/sovereign-immich-external-restic snapshots
/usr/local/sbin/sovereign-immich-external-restic check
```

PBS datastore verification:

```bash
proxmox-backup-manager verify-job list
proxmox-backup-manager datastore show immich-offline
```

Record the snapshot IDs, restic snapshot ID, file count, bytes, and verification result in `/root/sovereign-secrets/HOMELAB_ACCESS_INVENTORY.md`.

Unmount using PBS:

```bash
proxmox-backup-manager datastore unmount immich-offline
```

Confirm no mount remains before unplugging:

```bash
findmnt /mnt/datastore/immich-offline && exit 1 || true
```

Store the SSD disconnected from the P710. A permanently attached disk is a second medium but not an offline copy.

## Full-Service Restore Drill

Never restore over VM 110. Use a temporary VM ID and isolated network:

1. Attach the SSD to PBS and reuse the existing `immich-offline` datastore with the same relative path `pbs`.
2. Add the datastore to Proxmox using a restore-only token.
3. Restore the latest VM 110 snapshot to a temporary VM ID.
4. Set the temporary NIC to `link_down=1` before first boot.
5. Boot, confirm both filesystems, and inspect the Immich containers.
6. Assign a temporary non-production IP only when duplicate identity and route risks are removed.
7. Confirm `/api/server/ping`, database health, and several sample assets.
8. Destroy only the temporary VM after recording evidence.

## Portable Restore Drill

On an isolated Linux VM with enough temporary disk space:

```bash
export RESTIC_REPOSITORY_FILE=/root/recovery/restic-repository
export RESTIC_PASSWORD_FILE=/root/recovery/restic-password
restic snapshots --tag immich-consistent
restic restore latest --tag immich-consistent --target /srv/immich-restore
```

Confirm these paths exist:

```text
mnt/immich-library/upload/library
mnt/immich-library/upload/upload
mnt/immich-library/upload/profile
opt/sovereign-homelab/stacks/immich
root/sovereign-immich-external-staging/database.sql.gz
```

Restore the database only into a fresh, isolated Immich installation using the Immich version matching the snapshot. Validate file counts and sample checksums before declaring the copy usable.

## Retention

Initial conservative policy:

| Format | Retention |
|---|---|
| PBS VM snapshots | last 3, weekly 8, monthly 12 |
| Restic consistent snapshots | last 3, daily 7, weekly 8, monthly 12 |
| Full repository check | after every connection; read-data subset monthly |
| Full isolated restore | quarterly and after major Immich upgrades |

Pruning runs on the backup target, not from a production credential with broad delete rights.

## Failure Handling

| Symptom | Action |
|---|---|
| SSD identity differs | stop; do not initialize or mount |
| PBS datastore does not mount | inspect device and relative datastore path; do not recreate blindly |
| Restic cannot open repository | verify mount, restricted SFTP account, host key, and password file |
| Immich server did not restart | run `docker start immich-server`, inspect logs, send a P0 alert |
| Backup completes but verify fails | keep the previous copy, mark the SSD unsafe, do not prune |
| Capacity exceeds 80% | stop adding retention, obtain a larger target, and keep the newest verified copy |

## Production Gate

The external SSD is accepted only when all are true:

- one full VM 110 snapshot exists on the removable PBS datastore;
- one `immich-consistent` restic snapshot exists;
- PBS verification passes;
- restic check passes;
- an isolated database restore passes;
- sample original assets restore with matching checksums;
- the SSD is unmounted and physically disconnected;
- the password and encryption recovery material exist outside the SSD.

## Sources

- [Immich backup and restore](https://docs.immich.app/administration/backup-and-restore/)
- [Immich backup script guidance](https://docs.immich.app/guides/template-backup-script/)
- [PBS removable datastores](https://pbs.proxmox.com/docs/storage.html#removable-datastores)
- [PBS sync jobs](https://pbs.proxmox.com/docs/managing-remotes.html#sync-jobs)
- [restic documentation](https://restic.readthedocs.io/en/stable/)

---

**Previous:** [PBS Critical Operations](PBS_CRITICAL_OPERATIONS.md)
**Next:** [Operations Manual](../06_operations_security/OPERATIONS_MANUAL.md)
