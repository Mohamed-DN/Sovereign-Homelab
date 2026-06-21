# Immich Runbook Rewrite Strategy & Research Findings

## 1. Overview
The current `immich.md` runbook is incomplete and does not meet the "exhaustive A-Z" standard defined in `SCOPE.md`. It lacks a comprehensive environment variables deep-dive, misses crucial components of the official disaster recovery (DR) procedure, lacks a deterministic rollback strategy, and skips hardware acceleration details which are vital for Immich's performance.

## 2. Research Findings (Based on Official Immich Documentation)

### Architecture & Components
Immich requires multiple interconnected containers:
- `immich-server`: Main application and API.
- `immich-machine-learning`: Handles object detection, facial recognition, etc.
- `redis`: Caching and background job queueing.
- `database`: PostgreSQL extended with `pgvecto.rs` (essential for ML embeddings).

### Environment Variables Deep-Dive
The new runbook must expand `.env` configurations:
- `UPLOAD_LOCATION`: Absolute path for all media (originals, thumbnails, transcodes). Critical to back up.
- `DB_DATA_LOCATION`: Absolute path for Postgres data.
- `DB_PASSWORD`, `DB_USERNAME`, `DB_DATABASE_NAME`: Database credentials (default `immich`).
- `IMMICH_VERSION`: **Crucial.** Must pin specific releases (e.g., `v1.106.4`) instead of `latest` for safe rollbacks.
- `IMMICH_PORT`: Exposed port (default `2283`).
- `TZ`: Timezone to ensure log timestamps and cron jobs are correct.

### Backup Strategy
Immich officially mandates backing up two things:
1. **The Database:** Live backups using `pg_dumpall`.
   - Command: `docker exec -t immich_postgres pg_dumpall -c -U postgres > dump.sql`
2. **The Filesystem:** The `UPLOAD_LOCATION` folder, `docker-compose.yml`, and `.env`.
   - All files must be synced consistently.

### Restore & Disaster Recovery Procedure
The official DB restore process involves starting a fresh database container and piping the SQL dump into it.
1. Spin up the host and ensure Docker is installed.
2. Restore `UPLOAD_LOCATION`, `.env`, and `docker-compose.yml`.
3. Start *only* the database: `docker compose up -d database` (or `immich_postgres` depending on service name).
4. Drop the existing empty DB and recreate it (or just pipe `pg_dumpall -c` which handles dropping).
   - `cat dump.sql | docker exec -i immich_postgres psql -U postgres`
5. Bring up the rest of the stack: `docker compose up -d`

### Rollback Procedure
If a version upgrade breaks Immich, the official and deterministic rollback requires:
1. `docker compose down`
2. Delete the current corrupted Postgres volume / directory.
3. Re-create the empty Postgres directory.
4. Change `IMMICH_VERSION` in `.env` back to the pre-upgrade version.
5. Start only the DB container, restore `dump.sql` (from the pre-upgrade backup).
6. Run `docker compose up -d`.

### Reverse Proxy (NPM) Settings
- Port: `2283`
- Websockets: **Required** for real-time mobile app sync.
- `client_max_body_size 0;`: **Required** to allow large video uploads.
- Proxy Read Timeout: Should be increased (e.g., 600s) to prevent timeouts during large batch uploads.

## 3. Concrete Strategy for the Worker

1. **Section 1: Overview & Architecture**
   - Define Immich as a P0 Critical service.
   - Detail the required containers (`server`, `ml`, `redis`, `database`).
   - Mention hardware acceleration (Intel QuickSync / NVENC) passing through LXC/VM as an advanced but recommended setup.

2. **Section 2: Environment Variables Deep-Dive**
   - Provide a template `.env` block.
   - Exhaustively explain each variable (`UPLOAD_LOCATION`, `DB_PASSWORD`, `IMMICH_VERSION`, etc.) as per the research.

3. **Section 3: Deployment Steps (A-Z)**
   - VM/LXC Setup (CPU, RAM, Disk).
   - Docker Compose configuration (providing the standard `docker-compose.yml` structure matching official docs).
   - Container startup and initial admin account creation logic.

4. **Section 4: Reverse Proxy & Monitoring**
   - Detail NPM settings including custom Nginx configurations (`proxy_read_timeout 600s;`, `client_max_body_size 0;`).
   - Detail Homepage and Uptime Kuma monitoring targeting `https://foto.internal/api/server-info/ping`.

5. **Section 5: Backup, Disaster Recovery & Rollback**
   - Provide the cron job command for daily `pg_dumpall`.
   - Provide the exact step-by-step verified DR procedure.
   - Provide the deterministic Rollback procedure (down, drop volume, restore DB, revert tag, up).

6. **Section 6: Troubleshooting**
   - Address ML container AVX instruction set issues.
   - Address mobile app background sync issues.
   - Address database connection issues.

By following this strategy, the Worker agent can rewrite `immich.md` to perfectly match the professional, exhaustive format established by `vaultwarden.md` and satisfy the `SCOPE.md` contracts.
