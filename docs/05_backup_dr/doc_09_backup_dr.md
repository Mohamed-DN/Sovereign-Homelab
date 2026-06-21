# Runbook 09: Backup and Disaster Recovery

Backup does not mean only having files. Backup means being able to restore.

Goal:

- PBS for VM/LXC;
- periodic restore test;
- retention and verify jobs;
- optional restic offsite backup for critical data.

---

## Phase A: What to Protect

| Data | Primary method | Optional method |
|---|---|---|
| LXC 100 core-network | PBS | config export |
| App VM/LXC | PBS | restic for volumes |
| Docker Compose | Git repo | copy `/opt/sovereign-homelab` |
| Real `.env` files | offline vault/encrypted restic | printed recovery |
| Immich uploads | PBS + restic | external disk |
| Vaultwarden data | PBS + restic | encrypted export |
| Authentik DB | PBS + dump | restic |

Rule: personal app data has double protection.

---

## Phase B: Proxmox Backup Server

PBS should be installed as a dedicated VM or separate appliance.

Minimum configuration:

1. Create datastore.
2. Add PBS to Proxmox VE as storage.
3. Create backup jobs for:
   - LXC 100;
   - service LXC/VMs;
   - Home Assistant VM;
   - PBS VM excluded or protected differently.
4. Enable verify job.
5. Configure prune/retention.

Recommended homelab retention:

```text
keep-last: 7
keep-daily: 14
keep-weekly: 8
keep-monthly: 6
```

Adjust based on available space.

PBS maintenance:

- prune removes old snapshot references;
- garbage collection frees chunks that are no longer referenced;
- verify job checks that backups are readable;
- an unverified backup is an assumption, not a guarantee.

---

## Phase C: Restore Test

Run a restore test every quarter.

Procedure:

1. Choose a non-critical VM/LXC or clone the backup to a new ID.
2. Restore from PBS.
3. Start the system isolated or with a temporary IP.
4. Verify:
   - boot;
   - filesystem;
   - main service;
   - logs without severe errors.
5. Document date, backup used, result, and restore time.

Note template:

```text
Restore test
Date:
Source backup:
Target VM/CT ID:
Service:
Result:
Issues:
Next action:
```

---

## Phase D: Optional restic Offsite Backup

restic is useful for encrypted backups of application folders.

Example local/offsite repository:

```bash
export RESTIC_REPOSITORY=/mnt/backup/restic/sovereign
export RESTIC_PASSWORD_FILE=/root/.config/restic/sovereign.pass
restic init
```

Backup:

```bash
restic backup /opt/sovereign-homelab /opt/core-network
restic snapshots
restic check
```

Retention:

```bash
restic forget --keep-daily 14 --keep-weekly 8 --keep-monthly 6 --prune
```

Do not put `RESTIC_PASSWORD` in shell history. Use `RESTIC_PASSWORD_FILE`.

---

## Phase E: Sensitive App Backups

### Vaultwarden

Protect:

- database volume;
- attachments;
- `ADMIN_TOKEN`;
- optional periodic encrypted export.

### Immich

Protect:

- upload directory;
- PostgreSQL database;
- `.env`;
- Compose file.

Immich requires attention: photos and database must be consistent. Prefer snapshot/PBS or the official procedure.

### Authentik

Protect:

- PostgreSQL;
- media;
- `.env`;
- admin recovery codes.

---

## Phase F: Production Checklist

Before adding real data:

- backup job created;
- first backup completed;
- verify job completed;
- restore test executed on at least one service;
- real `.env` files saved outside Git;
- Uptime Kuma monitors the service;
- you know how to stop and restore the container.

Quick verification commands: [VALIDATION_COMMANDS.md](../99_reference/VALIDATION_COMMANDS.md).

---

## Reference

- Proxmox VE backup: <https://pve.proxmox.com/wiki/Backup_and_Restore>
- Proxmox Backup Server: <https://pbs.proxmox.com/docs/>
- PBS maintenance: <https://pbs.proxmox.com/docs/maintenance.html>
- restic: <https://restic.net/>
- Immich backup: <https://docs.immich.app/administration/backup-and-restore>

---

**Previous:** [Runbook 08: Observability](../03_platform_services/doc_08_observability_dashboard.md)
**Next:** [PBS Critical Operations](PBS_CRITICAL_OPERATIONS.md)
