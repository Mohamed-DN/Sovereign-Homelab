# Emergency Immich Restore Stack

This is a **temporary emergency** Immich stack used only to recover the Windows
restic mirror on a Windows PC (Docker Desktop / WSL2). It is not a production
deployment and must never run alongside or against the live VM 110.

Full procedure: [Immich Windows Mirror runbook](../../docs/05_backup_dr/IMMICH_WINDOWS_MIRROR.md).

## What it does

- Brings up Immich server, PostgreSQL, and Valkey pinned to the production
  versions so an imported database dump matches.
- Serves the restored original assets so you can validate a sample photo.
- Omits machine learning on purpose; existing assets are served without it.

## Quick use

1. Restore the mirror with `scripts/windows/Restore-ImmichLatest.ps1`.
2. `copy .env.example .env` and set `IMMICH_UPLOAD_LOCATION` to the restored
   `...\mnt\immich-library\upload` folder and `IMMICH_VERSION` to the value in
   the restored `recovery-metadata.txt`.
3. `docker compose up -d` and wait for the database to become healthy.
4. Import the dump (see the runbook for the exact `psql` command).
5. Restart `immich-restore-server` and open `http://localhost:2283`.
6. Validate `http://localhost:2283/api/server/ping` returns `{"res":"pong"}`.
7. Tear down with `docker compose down` when the drill is finished. Keep the
   restored files until the drill evidence is recorded.

## Safety

- Fresh empty PostgreSQL volume; the dump is imported after startup.
- Throwaway local DB password; this stack is isolated to the Windows PC.
- Never expose this stack to the network or the `.internal` namespace.
