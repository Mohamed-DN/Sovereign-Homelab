# Handoff Report: Karakeep Deployment Runbook Analysis

## 1. Observation
- **Target File Analyzed**: `docs/04_apps/karakeep.md`
- **Compose Analyzed**: `stacks/karakeep/docker-compose.yml`
- **Env Analyzed**: `stacks/karakeep/.env.example`
- **Key Architecture Details**:
  - The stack consists of three containers: `karakeep` (Next.js app, mapping port 3000), `karakeep-meilisearch` (search engine, v1.13), and `karakeep-chrome` (headless Chrome v124).
  - Volumes defined: `karakeep_data` (mapped to `/data` in main app) and `karakeep_meili` (mapped to `/meili_data` in Meilisearch).
  - Environment variables in compose explicitly map configuration: `MEILI_ADDR`, `MEILI_MASTER_KEY`, `NEXTAUTH_SECRET`, `NEXTAUTH_URL`, `BROWSER_WEB_URL`.
- **Existing Runbook Gaps**: 
  - `karakeep.md` lacks detailed VM preparation (e.g., Docker prerequisite, directory creation).
  - It does not explain how to properly generate the secrets (`NEXTAUTH_SECRET`).
  - Disaster recovery (DR) is vague ("Restore DB/data/search index").
  - Troubleshooting lacks specifics on NextAuth session issues and Meilisearch index desyncs.

## 2. Logic Chain
- **VM Setup & Prerequisites**: A complete runbook must specify the prerequisite state. LXC 102 must have Docker installed. The `/opt/sovereign/stacks/karakeep` directory must be created before copying `.env`.
- **Environment Variables Deep-Dive**:
  - `KARAKEEP_NEXTAUTH_SECRET`: Used by NextAuth to encrypt JWT/sessions. If lost, users must re-authenticate. Should be generated using `openssl rand -base64 32`.
  - `KARAKEEP_MEILI_MASTER_KEY`: Protects the Meilisearch API. 
  - `NEXTAUTH_URL`: Must match the exact external domain (e.g. `https://bookmarks.internal`). If mismatched, NextAuth logins fail with CSRF or callback errors.
  - `KARAKEEP_PORT`: The host port mapped to the container's 3000 port for NPM.
- **Disaster Recovery Strategy**: 
  - The stack relies on `/data` (SQLite DB + archived assets) and `/meili_data` (search index).
  - Meilisearch indices and SQLite databases can corrupt if copied while active. It is critical to document that containers *must be stopped* (`docker compose down`) before performing manual file-level backups or restores.
- **Troubleshooting**:
  - Chrome archiving failures: The Chrome container uses `--disable-dev-shm-usage`, but if OOM occurs on heavy sites, the container will restart. Users should check `docker logs karakeep-chrome`.
  - Search desync: If search breaks, the meili volume may need to be cleared and re-indexed (if the app supports auto-reindex) or restored from backup.

## 3. Caveats
- Operating in a `CODE_ONLY` mode restricts external web access. I cannot verify the official Karakeep/Hoarder documentation for specific hidden CLI commands (e.g., forcing a Meilisearch reindex from the main container).
- The analysis assumes the main app uses SQLite stored in `/data` as there is no Postgres/MySQL container provided.

## 4. Conclusion
The existing runbook is a skeleton. The Worker should completely rewrite `docs/04_apps/karakeep.md` with the following sections:
1. **Prerequisites & VM Setup**: Define LXC requirements, Docker setup, and directory scaffolding.
2. **Configuration Deep-Dive**: Detail every env var, explicitly providing generation commands like `openssl rand -base64 32`.
3. **Deployment**: Keep compose commands but add health check validation steps.
4. **Proxy & Security**: Expand NPM configuration details.
5. **Disaster Recovery (A-Z)**: Step-by-step procedures for stopping containers (`docker compose down`), backing up `/data` and `/meili_data` safely without corruption, and restoring them.
6. **Troubleshooting**: Add sections for NextAuth login failures (check `NEXTAUTH_URL`), Chrome OOM crashes, and Meilisearch recovery.

## 5. Verification Method
- **To verify the env vars**: Review `stacks/karakeep/docker-compose.yml` to ensure all described vars match the file exactly.
- **To verify DR procedure**: Deploy the stack with `docker compose up -d`, add a bookmark, stop the stack with `docker compose down`, copy the Docker volumes (or their backing directories in `/var/lib/docker/volumes/`) to a backup location, delete the volumes, and test the restore to confirm no corruption occurs.
