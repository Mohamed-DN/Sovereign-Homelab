# Immich Research & Strategy Analysis

## 1. Overview
The goal is to produce an exhaustive, A-Z runbook for Immich (`immich.md`) that satisfies the acceptance criteria defined in `SCOPE.md`.
The current `immich.md` is too brief. It lacks a deep dive into environment variables, a fully verified and safe disaster recovery process matching the official docs, and the detailed end-to-end VM/LXC setup steps.

## 2. Findings from Local Files
1. **Docker Compose (`stacks/immich/docker-compose.yml`)**:
   - Services: `immich-server`, `immich-machine-learning`, `immich-redis` (using `valkey:8-alpine`), and `immich-database` (using `postgres:14-vectorchord`).
   - Volumes: `IMMICH_UPLOAD_LOCATION` mapped to `/usr/src/app/upload` on server, and `IMMICH_DB_DATA_LOCATION` mapped to `/var/lib/postgresql/data` on database.
   - Env variables injected via `.env` file containing `TZ`, `IMMICH_VERSION`, `IMMICH_PORT`, `IMMICH_UPLOAD_LOCATION`, `IMMICH_DB_DATA_LOCATION`, `IMMICH_DB_PASSWORD`, `IMMICH_DB_USERNAME`, `IMMICH_DB_DATABASE_NAME`.

2. **Current Runbook (`docs/04_apps/immich.md`)**:
   - Skips OS prep / Docker installation.
   - Minimal explanation of variables.
   - Backup/restore mentions `docker exec -t immich_postgres pg_dumpall`, but the container name is `immich-database` in the docker-compose file! This is a **critical bug** in the current runbook.

## 3. Recommended Strategy for Worker

### A. Prerequisites & VM/LXC Setup
- Explicitly state OS requirements (e.g., Debian 12 / Ubuntu 24.04).
- Add steps for updating the system, installing Docker and Docker Compose plugin.
- Add steps for creating the dedicated application directory (`/opt/sovereign/stacks/immich`) and required storage mounts.

### B. Deep-Dive Environment Variables
Expand the `.env` explanation section into a comprehensive table:
- `IMMICH_VERSION`: Set to `release` or a specific version (e.g., `v1.106.4`). Emphasize pinning versions to prevent accidental breakage.
- `IMMICH_UPLOAD_LOCATION`: The core data directory. Must have significant space. Includes `library`, `upload`, `encoded-video`, and `profile` subdirectories.
- `IMMICH_DB_DATA_LOCATION`: Database volume directory.
- `IMMICH_DB_PASSWORD`, `IMMICH_DB_USERNAME`, `IMMICH_DB_DATABASE_NAME`: Database credentials. Highlight the need to generate a secure 36+ char password.
- `IMMICH_PORT`: Port mapping for the host (default `2283`).
- `TZ`: Timezone to ensure log timestamps and localized task runs are correct.

*Hardware Acceleration (Optional but recommended)*:
- If hardware acceleration (QuickSync/NVENC) is desired, instruct adding `devices: - /dev/dri:/dev/dri` to `immich-server` and `immich-machine-learning` (if using OpenVINO).

### C. Deployment & Initialization
- Step-by-step: `docker compose up -d`, verifying logs with `docker compose logs -f`.
- Include the initial setup step: Navigating to `http://<IP>:2283` and creating the initial admin account.

### D. Reverse Proxy (Nginx Proxy Manager)
- The current settings in `immich.md` are mostly correct: `http`, port `2283`, websockets enabled.
- **Critical addition**: Client Max Body Size must be `0` (or disabled) to allow large video uploads.

### E. Disaster Recovery (Backup & Restore)
Based on official Immich documentation, the backup process must cover the database AND the upload directory.

**Database Backup**:
```bash
docker compose exec -T immich-database pg_dumpall -c -U postgres > "immich_db_dump.sql"
```
*(Note: Replace `-U postgres` with `-U ${IMMICH_DB_USERNAME}` if the user is different, but pg_dumpall often requires the superuser).*

**Files Backup**:
- The entire `IMMICH_UPLOAD_LOCATION` folder.
- The `.env` and `docker-compose.yml` files.

**Restore Procedure**:
1. Restore `.env`, `docker-compose.yml`, and `IMMICH_UPLOAD_LOCATION` to the correct paths.
2. Start only the database: `docker compose up -d immich-database`
3. Wait for DB to be ready, then restore the dump:
```bash
docker compose exec -T immich-database psql -U ${IMMICH_DB_USERNAME} -d ${IMMICH_DB_DATABASE_NAME} < "immich_db_dump.sql"
```
4. Start remaining containers: `docker compose up -d`

### F. Troubleshooting
- Add steps for viewing logs: `docker compose logs --tail=100 -f`.
- Machine learning issues (e.g., AVX CPU support).
- Upgrades: Emphasize reading the release notes before bumping `IMMICH_VERSION`, as breaking changes happen frequently in Immich.

## 4. Execution Plan
1. The Implementer/Worker agent should read this analysis.
2. Open `docs/04_apps/immich.md`.
3. Rewrite the entire document using the detailed sections proposed above.
4. Ensure the container names in backup commands exactly match `stacks/immich/docker-compose.yml` (`immich-database` instead of `immich_postgres`).
