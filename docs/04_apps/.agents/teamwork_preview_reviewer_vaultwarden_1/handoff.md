# Handoff Report: Vaultwarden Runbook Review

## 1. Observation
- The runbook in `vaultwarden.md` section 5.3 ("Restore Drill") instructs the user to restore the `vw-data` directory and rename `db.sqlite3.bak` to `db.sqlite3`.
- The instructions do not explicitly tell the user to delete or move the `db.sqlite3-wal` and `db.sqlite3-shm` files that were captured in the folder-level backup.
- In Section 3.2 ("Docker Compose Configuration"), the variable `WEBSOCKET_ENABLED=true` is included, despite the note in the same section correctly stating that from Vaultwarden 1.29.0+ websockets are merged to port 80.
- Section 5.2 ("Critical Files to Backup") explicitly lists files like `db.sqlite3`, `rsa_key*`, and `.env`, but omits `config.json`. 

## 2. Logic Chain
1. **Disaster Recovery Integrity (Critical)**: Vaultwarden uses SQLite in WAL (Write-Ahead Logging) mode by default. A Proxmox folder backup captures the live, potentially inconsistent `db.sqlite3` along with its active `db.sqlite3-wal` and `db.sqlite3-shm` files. The nightly cron job creates a clean, consistent `db.sqlite3.bak` without WAL dependencies. During a restore, if a user overwrites `db.sqlite3` with the `.bak` file but leaves the backed-up `-wal` file in the directory, SQLite will attempt to recover using the incompatible WAL file on startup. This causes the mismatched WAL transactions to be applied to the `.bak` file, resulting in immediate database corruption (`database disk image is malformed`).
2. **Environment Variable Deprecation (Minor)**: If Websockets are handled on port 80 as of 1.29.0+, the `WEBSOCKET_ENABLED` variable is obsolete and ignored by the application. Including it in `docker-compose.yml` contradicts the explanatory note and violates the "exhaustive deep-dive" criterion by propagating legacy configuration.
3. **Missing Critical File (Major)**: When an administrator modifies settings via the Vaultwarden `/admin` page, those settings are saved in `vw-data/config.json`. These settings take precedence over the `.env` file. Omitting `config.json` from the critical files list risks losing all UI-based configurations during a selective file restore.

## 3. Caveats
- I am assuming the Vaultwarden container runs with WAL mode enabled, which has been the default for a long time. Even if WAL is disabled, standard SQLite backup hygiene mandates clearing `-wal` and `-shm` files to prevent accidental corruption.
- The `sqlite3` CLI tool inside `vaultwarden/server:latest` was assumed to be present based on official docs (it is included in the default Debian-based image), which is why the cron job command itself was not flagged.

## 4. Conclusion
**Verdict: REQUEST_CHANGES (INTEGRITY VIOLATION)**

The work product contains a critical flaw in the disaster recovery procedure that will lead to database corruption.

### Review Summary
**Verdict**: REQUEST_CHANGES

### Findings

#### [Critical] Finding 1: SQLite WAL Corruption on Restore
- **What**: The Restore Drill does not instruct users to delete SQLite WAL files.
- **Where**: Section 5.3 (Restore Drill), Step 3.
- **Why**: SQLite will apply the old `db.sqlite3-wal` file to the newly restored `db.sqlite3.bak` file, corrupting the database on startup.
- **Suggestion**: Add a step to explicitly delete `db.sqlite3-wal` and `db.sqlite3-shm` before starting the container.

#### [Major] Finding 2: Missing config.json in Backups
- **What**: `config.json` is missing from the list of critical files.
- **Where**: Section 5.2 (Critical Files to Backup).
- **Why**: Settings changed in the `/admin` UI are saved to `config.json` and override `.env`. Losing this file means losing critical configuration.
- **Suggestion**: Add `config.json` to the list of critical files.

#### [Minor] Finding 3: Deprecated Environment Variable
- **What**: `WEBSOCKET_ENABLED=true` is used in docker-compose.yml.
- **Where**: Section 3.2 (Docker Compose Configuration).
- **Why**: As noted in the runbook itself, 1.29.0+ merges websockets. This variable is obsolete.
- **Suggestion**: Remove `WEBSOCKET_ENABLED=true` from the compose file.

## 5. Verification Method
- **SQLite WAL**: Refer to official SQLite backup documentation. Restoring a backup while leaving an unrelated/old WAL file in the same directory will cause the database engine to attempt recovery on the wrong base file.
- **Vaultwarden config.json**: Verify via Vaultwarden documentation that `/admin` settings are saved to `data/config.json` and supersede `.env` settings.
- **Websockets**: Verify Vaultwarden 1.29.0 release notes confirming the deprecation of `WEBSOCKET_ENABLED`.
