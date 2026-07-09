# Immich Recovery Runbook

This is the single, canonical guide for **bringing Immich (the photo history)
back** after any failure. It is written to be usable from zero, under stress,
even if the original Proxmox host no longer exists.

Read the golden rules first, then pick the recovery path that matches your
situation.

## Golden Rules

- **Never restore on top of the live VM 110.** Always recover into a temporary
  VM, container, or PC first, validate, and only then decide.
- **The database and the files must match.** An Immich database dump only
  contains metadata (albums, users, positions, face data). The actual photos
  and videos live in the **upload tree**. A dump is only usable together with an
  upload tree from about the same moment. Always recover both.
- **Never delete the phone originals** until at least two independent restores
  have succeeded.
- **Use the matching Immich version.** Restoring a dump into a different major
  Immich version can fail after database migrations. The version is recorded in
  `recovery-metadata.txt` and pinned in the stack `.env`.

## What Protects the Photo History Today

| Layer | What it is | Where | Proven |
|---|---|---|---|
| PBS full VM snapshots | complete VM 110 (OS + DB + files), restorable | PBS VM 140 datastore | daily; latest verified |
| App-aware protection | daily DB dump, weekly capacity, quarterly SHA-256 manifest, isolated restore test | VM 110 `/root/sovereign-secrets/immich-protection` | daily timers + restore-test marker |
| Temporary Windows mirror | encrypted restic copy of DB dump + upload tree | Windows PC (when online) | see [Windows Mirror](IMMICH_WINDOWS_MIRROR.md) |
| External SSD (planned) | portable PBS + restic copy | removable SSD | see [External SSD Recovery](IMMICH_EXTERNAL_SSD_RECOVERY.md) |

The first two layers are the primary safety net and are always on.

## Key Locations

| Item | Location |
|---|---|
| Live upload tree (host) | `/mnt/immich-library/upload` on VM 110 |
| Upload tree (container path) | `/data` inside `immich-server` |
| Live stack | `/opt/sovereign-homelab/stacks/immich` on VM 110 |
| Daily DB dumps | `/root/sovereign-secrets/immich-protection/daily/immich-db-*.sql.gz` on VM 110 |
| Recovery metadata (version, counts) | inside each mirror/protection snapshot |
| Emergency stack (repo) | `stacks/immich-restore/` |
| Pinned version | `IMMICH_VERSION` in the stack `.env` (currently `v3.0.1`) |

The upload tree contains these subfolders, all of which must be recovered
together: `library/`, `upload/`, `profile/`, `thumbs/`, `encoded-video/`,
`backups/`.

---

## Path A: Full VM Restore from PBS (fastest, most complete)

Use when the VM is lost or corrupted but PBS is available. This restores the
whole VM (OS, database, and files) in one operation.

1. In the Proxmox UI (or CLI), pick the latest good VM 110 snapshot:

   ```bash
   pvesm list pbs-p710 --content backup | grep vm/110
   ```

2. **Restore to a NEW temporary VM id** (for example 910), never over 110:

   ```bash
   qmrestore pbs-p710:backup/vm/110/<TIMESTAMP> 910 --storage <target-storage>
   ```

3. Before first boot, isolate the network so it cannot clash with live 110:

   ```bash
   qm set 910 --net0 <model>,bridge=<bridge>,link_down=1
   ```

4. Boot 910, confirm the Immich containers start, then validate (see
   Validation). Only after validation, decide whether to promote it or copy data
   out. Destroy the temporary VM when finished.

This path needs no manual database import; the database is already inside the
snapshot.

---

## Path B: Application Restore from Upload Tree + a Separate DB Dump

**This is the "files plus the dump on the side" recovery.** Use it when you have
the upload tree and a database dump but not a full VM image (for example from the
Windows mirror, the app-aware protection folder, or a copied SSD). It works on
any Docker host, including a Windows PC with Docker Desktop.

### B1. Gather the two ingredients

You need:

1. **The upload tree** (the folder that contains `library/`, `upload/`,
   `profile/`, `thumbs/`, `encoded-video/`).
2. **One database dump** `immich-db-*.sql.gz` (or `database.sql.gz`) taken at
   about the same time as that tree.

Sources for a dump:

- App-aware protection on VM 110 (newest is best):

  ```bash
  ls -t /root/sovereign-secrets/immich-protection/daily/immich-db-*.sql.gz | head -1
  ```

- Or make a fresh one from a running database:

  ```bash
  docker exec immich-database sh -lc \
    'pg_dump --clean --if-exists --dbname="$POSTGRES_DB" --username="$POSTGRES_USER"' \
    | gzip -9 > immich-db-fresh.sql.gz
  ```

- Or the Windows restic mirror (`Restore-ImmichLatest.ps1` writes both the tree
  and `database.sql.gz`).

### B2. Bring up a clean, isolated Immich stack

Use the emergency stack in `stacks/immich-restore/` (or a copy of
`stacks/immich`). It starts an **empty** PostgreSQL, so the dump imports cleanly.

```bash
cd stacks/immich-restore
cp .env.example .env
# Set in .env:
#   IMMICH_VERSION       -> the version from recovery-metadata.txt (e.g. v3.0.1)
#   IMMICH_UPLOAD_LOCATION -> path to the recovered upload tree
#   IMMICH_DB_USERNAME/NAME -> same as production (postgres / immich)
docker compose up -d
```

Wait until the database container is healthy before importing.

### B3. Import the database dump (with the official Immich fix)

Immich requires a `search_path` adjustment during restore. Apply it while
streaming the dump into the empty database:

```bash
gzip -dc immich-db-<TIMESTAMP>.sql.gz \
  | sed "s/SELECT pg_catalog.set_config('search_path', '', false);/SELECT pg_catalog.set_config('search_path', 'public, pg_catalog', true);/g" \
  | docker exec -i immich-restore-database \
      psql --dbname=immich --username=postgres --single-transaction --set ON_ERROR_STOP=on
```

`--single-transaction` and `ON_ERROR_STOP=on` mean the import either fully
succeeds or leaves the database untouched, so a bad dump cannot half-load.

### B4. Restart the server and validate

```bash
docker restart immich-restore-server
```

Then run the Validation section below.

---

## Path C: From the Temporary Windows Mirror

Use [Immich Windows Mirror](IMMICH_WINDOWS_MIRROR.md). In short:
`Restore-ImmichLatest.ps1` restores the newest consistent snapshot (upload tree
plus `database.sql.gz`) locally on the Windows PC, then you follow **Path B**
from step B2 using `stacks/immich-restore/`.

---

## Validation (all paths)

Run every check before trusting a recovery:

```bash
# API is alive
curl -fsS http://localhost:2283/api/server/ping        # expect {"res":"pong"}
# version matches the dump
curl -fsS http://localhost:2283/api/server/version
```

Then, logged into the temporary Immich:

- confirm the expected users and albums exist;
- open several photos and one video from different years;
- compare the asset/file counts against `recovery-metadata.txt` or the newest
  protection `summary-*.json` (`file_count`, `total_bytes`);
- if you have a quarterly SHA-256 manifest, spot-check a few files.

Record the snapshot id, counts, and result before destroying any temporary
environment.

---

## Isolated Database-Only Test (no photos at risk)

To prove a dump is loadable without touching the live library, the protection
system already does this daily. To run it manually on VM 110:

```bash
/usr/local/sbin/sovereign-immich-protection restore-test
cat /root/sovereign-secrets/immich-protection/state/last-database-restore-test
```

It creates a throwaway database, imports the newest dump, counts the restored
tables, and drops the throwaway database. It never touches production data.

---

## Rollback and Cleanup

- Temporary recovery VMs/stacks are disposable: `qm destroy <tempid>` or
  `docker compose down -v` in the emergency stack when finished.
- The live VM 110 is never modified by any recovery path here.
- Keep the recovered copy until you have recorded evidence and confirmed the
  live system (or its replacement) is healthy.

## Troubleshooting

| Symptom | Action |
|---|---|
| `psql` import aborts | Confirm the `search_path` sed fix is applied and the DB is empty; check the Immich version matches. |
| Photos missing but albums present | The upload tree does not match the dump; recover a tree from the same moment. |
| Version mismatch errors | Set `IMMICH_VERSION` to the value in `recovery-metadata.txt`; do not use a newer image against an older dump. |
| API pong but blank library | Wait for background jobs, confirm `IMMICH_UPLOAD_LOCATION` points at the real tree (not an empty folder). |
| Everything healthy | Record evidence, then decide on promotion; keep phone originals regardless. |

## Sources

- [Immich backup and restore](https://docs.immich.app/administration/backup-and-restore/)
- [Proxmox Backup Server restore](https://pbs.proxmox.com/docs/)
- [restic restore](https://restic.readthedocs.io/en/stable/050_restore.html)

---

**Previous:** [Immich Windows Mirror](IMMICH_WINDOWS_MIRROR.md)
**Next:** [PBS Critical Operations](PBS_CRITICAL_OPERATIONS.md)
