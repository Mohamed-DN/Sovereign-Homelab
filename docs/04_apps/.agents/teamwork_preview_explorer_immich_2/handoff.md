# Handoff Report: Immich Runbook Analysis

## 1. Observation
- `SCOPE.md` lines 17-20 require: "Deep-dive explanation of environment variables," "Verified disaster recovery and rollback procedure based on official docs," and "No missing logical steps from VM/LXC setup to monitoring."
- `docs/04_apps/immich.md` lines 42-46 show a backup command: `docker exec -t immich_postgres pg_dumpall -c -U postgres > dump.sql`.
- `stacks/immich/docker-compose.yml` lines 36-39 define the database service as `container_name: immich-database` and image as `postgres:14-vectorchord0.4.3-pgvectors0.2.0`.
- `stacks/immich/docker-compose.yml` lines 11-17 and 40-44 show environment variables passed from the `.env` file (e.g., `IMMICH_DB_USERNAME`, `IMMICH_DB_PASSWORD`).
- `docs/04_apps/immich.md` lacks steps for OS/Docker prerequisites and doesn't explain what subfolders live in `IMMICH_UPLOAD_LOCATION`.

## 2. Logic Chain
1. The current `immich.md` fails the `SCOPE.md` acceptance criteria because it skips VM/Docker setup steps and provides minimal environment variable explanations.
2. The current `immich.md` contains a critical error in its backup procedure: it references a container named `immich_postgres`, but the actual container running the database (per `docker-compose.yml`) is `immich-database`. Running the current backup command will fail with "No such container".
3. To provide a "Verified disaster recovery" procedure, the runbook must provide a correct `docker compose exec -T immich-database ...` command that uses the actual `.env` variables (or defaults to `postgres` user) to dump and restore the database safely.
4. The rewrite must include an A-Z deployment flow (OS Prep -> Docker Install -> Config/Env -> Compose Up -> Reverse Proxy -> Init Account -> Monitor).

## 3. Caveats
- Hardware acceleration (QuickSync/NVENC) is highly hardware-specific. I recommend adding a note about it, but not strictly enforcing it as a requirement in the runbook since the `docker-compose.yml` does not currently map `/dev/dri`.
- I have not tested the Postgres restore command directly on the live server to avoid data disruption, but the proposed `docker compose exec -T immich-database psql -U <user> -d <db> < dump.sql` strictly aligns with the official Immich backup and restore documentation.

## 4. Conclusion
The Worker agent must rewrite `docs/04_apps/immich.md` from scratch using the A-Z structure outlined in my `analysis.md`. The rewrite must fix the incorrect container name in the DB backup script, expand the `.env` variable definitions into a deep-dive table, and detail the complete flow from Docker installation to Nginx Proxy Manager setup (Max Body Size = 0) and Uptime Kuma monitoring.

## 5. Verification Method
- **Verify Runbook**: Inspect the newly written `docs/04_apps/immich.md` to ensure no steps are skipped between VM deployment and monitoring.
- **Verify Backup Script**: Dry-run the new backup command `docker compose exec -T immich-database pg_dumpall -c -U postgres > test_dump.sql` in `stacks/immich` to confirm it successfully generates a SQL dump without container naming errors.
- **Invalidation**: If the backup command fails or if the environment variables listed in the runbook don't match the keys in `stacks/immich/.env.example`, the runbook is invalid.
