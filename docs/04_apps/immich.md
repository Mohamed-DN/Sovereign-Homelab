# Immich Critical-Data Runbook

Immich is the private photo and video library. It is a P0 critical service because the source assets are irreplaceable and the database contains the metadata that makes those assets usable. A database dump without the files is incomplete; a file copy without the matching database is also incomplete.

## Target and Sizing

| Field | Live value |
|---|---|
| Guest | VM 110 `immich` at `VM110_IP` |
| CPU / RAM | 6 vCPU / 16 GB |
| OS disk | 120 GB |
| Data disk | 500 GB ext4 mounted at `/mnt/immich-library` |
| Stack | `/opt/sovereign-homelab/stacks/immich` |
| Alias | `https://foto.internal` |
| NPM upstream | `http://VM110_IP:2283` |
| Access | LAN/VPN only |

Capacity is not redundancy. The data disk, OS disk, and local PBS datastore are on the same physical server and can all be lost in one hardware or site incident.

## Install from an Empty VM

1. Create the Debian VM using the sizing above and install Docker Engine plus the Compose plugin.
2. Format and mount the data disk persistently at `/mnt/immich-library` using its filesystem UUID.
3. Create the stack directory and copy the repository template.
4. Keep the database password only in the real mode-`0600` `.env` file.

```bash
install -d -m 0750 /opt/sovereign-homelab/stacks/immich
cd /opt/sovereign-homelab/stacks/immich
cp .env.example .env
chmod 600 .env
```

Required values:

```text
UPLOAD_LOCATION=/mnt/immich-library/upload
DB_DATA_LOCATION=/mnt/immich-library/postgres
DB_PASSWORD=<RANDOM_DATABASE_PASSWORD>
```

Validate mounts before starting Immich:

```bash
findmnt /mnt/immich-library
df -hT /mnt/immich-library
docker compose --env-file .env config --quiet
docker compose --env-file .env up -d
docker compose --env-file .env ps
curl -fsS http://127.0.0.1:2283/api/server/ping
```

The machine-learning container can take longer to become healthy on its first start while it downloads models. Do not change ownership or manually edit files inside the Immich upload tree.

## DNS, NPM, Homepage, and Kuma

Create `foto.internal` as an NPM database-managed Proxy Host. Do not create a manual numbered Nginx file.

| NPM field | Value |
|---|---|
| Domain | `foto.internal` |
| Scheme | `http` |
| Forward host / port | `VM110_IP:2283` |
| WebSockets | yes |
| Certificate | `Sovereign Internal Wildcard` |
| Force SSL / HTTP2 | yes / yes |
| Access | LAN/VPN only |

Set the advanced upload limit only when required by the deployed NPM version:

```nginx
client_max_body_size 0;
proxy_read_timeout 600s;
proxy_send_timeout 600s;
```

Homepage uses a Critical Data card at `https://foto.internal`. Uptime Kuma monitor `app-immich` checks `https://foto.internal/api/server/ping` with private-CA verification enabled.

## Protection Layers

The production gate requires all of these layers:

1. Immich automatic database backups under `UPLOAD_LOCATION/backups`.
2. Root-only daily PostgreSQL dump and metadata inventory.
3. Weekly count/size comparison and quarterly SHA-256 manifest.
4. Nightly PBS snapshot of VM 110.
5. Separate local encrypted storage.
6. Encrypted offsite storage through a second location.

Layers 1 through 4 protect the current live build. Layers 5 and 6 remain required before the design qualifies as 3-2-1 disaster recovery.

### Install the App-Aware Job

Copy the repository script and units to VM 110:

```bash
install -m 0750 scripts/sovereign-immich-protection.sh \
  /usr/local/sbin/sovereign-immich-protection
install -m 0644 scripts/systemd/sovereign-immich-protection@.service \
  /etc/systemd/system/
install -m 0644 scripts/systemd/sovereign-immich-daily.timer \
  scripts/systemd/sovereign-immich-weekly.timer \
  scripts/systemd/sovereign-immich-quarterly.timer \
  /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now sovereign-immich-daily.timer \
  sovereign-immich-weekly.timer \
  sovereign-immich-quarterly.timer
```

The script writes only below `/root/sovereign-secrets/immich-protection` with mode `0600`/`0700`. Metadata and SHA-256 manifests contain personal filenames and therefore must never be committed or copied into normal logs.

Schedules:

| Job | Schedule | Output |
|---|---|---|
| Daily | 03:15 with randomized delay | compressed PostgreSQL dump, metadata inventory, count/size summary |
| Weekly | Sunday 05:15 | current-versus-previous count/size comparison |
| Quarterly | day 7 of Jan/Apr/Jul/Oct | compressed full-library SHA-256 manifest |

Run and validate manually:

```bash
/usr/local/sbin/sovereign-immich-protection daily
/usr/local/sbin/sovereign-immich-protection weekly
/usr/local/sbin/sovereign-immich-protection restore-test
systemctl list-timers 'sovereign-immich-*'
```

The isolated database test creates a temporary database in the existing PostgreSQL container, restores the latest dump in one transaction, verifies public tables, and removes the temporary database. It never replaces the production database.

## Backup Ordering

For a consistent external copy, stop `immich-server` while copying the database and asset filesystem. If downtime is not possible, capture the database first and the filesystem second. This ordering can leave harmless extra files, while the reverse order can leave database rows pointing at missing assets.

Do not stop containers during the normal PBS snapshot unless a separate maintenance window is approved. Use the app-aware dump as the consistency anchor and PBS as the guest-level recovery layer.

## Restore Drills

### Database Only

Run the scripted isolated test:

```bash
/usr/local/sbin/sovereign-immich-protection restore-test
```

### PBS File-Level Sample

Use Proxmox file restore against the newest VM110 snapshot, browse the data disk, and restore one sample asset into a root-only temporary directory. Hash and size-check the restored sample, then delete only the temporary copy. Never restore over VM 110.

### Full Isolated VM

1. Restore VM110 to an unused VM ID and isolated IP.
2. Disconnect or firewall external access before boot.
3. Verify `/mnt/immich-library` and all four Immich containers.
4. Confirm the API ping and review a representative timeline sample.
5. Record the result and destroy the temporary VM only after validation.

## Current Live Safety State

On 2026-06-30, the live library baseline contained 31,367 files totaling about 95.36 GB. A fresh PBS snapshot, compressed database dump, metadata inventory, and full SHA-256 manifest were created before this runbook update. The bundle is held root-only on VM110 and duplicated into the Proxmox backup vault with checksum verification.

This is still not full 3-2-1 protection because PBS and VM110 share the P710. Do not delete the phone originals until an encrypted separate local copy, encrypted offsite copy, and restores from both have passed.

## Rollback and Troubleshooting

| Symptom | Check | Safe response |
|---|---|---|
| API works but assets are missing | Immich system-integrity screen, mount, `.immich` markers | stop changes and verify the data-disk mount; do not create/delete markers blindly |
| Database dump fails | `immich-database` health and free space | keep production running, repair the backup job, then rerun the dump |
| NPM returns 413 or times out | body-size and proxy timeouts | update only the `foto.internal` Proxy Host and retest one large upload |
| Mobile background backup stalls | mobile OS permissions, battery policy, VPN state | keep foreground test active and verify AdGuard/NPM/Immich logs |
| Update breaks Immich | pinned image tag and latest app-aware/PBS backups | roll back the image tag first; restore into an isolated target before touching production data |
| Timer fails | `journalctl -u sovereign-immich-protection@daily.service` | fix the job, rerun it manually, and confirm the relay closes the failure incident |

## Official Sources

- Immich Docker Compose: <https://docs.immich.app/install/docker-compose/>
- Immich backup and restore: <https://docs.immich.app/administration/backup-and-restore/>
- Immich system integrity: <https://docs.immich.app/administration/system-integrity/>
- Proxmox Backup Server: <https://pbs.proxmox.com/docs/>

---

**Previous:** [Vaultwarden](vaultwarden.md)

**Next:** [Nextcloud AIO](nextcloud.md)
