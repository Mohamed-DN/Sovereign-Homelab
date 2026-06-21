# Paperless-ngx Documentation Rewrite Strategy & Research Findings

## 1. Observation
The current `paperless.md` at `C:\home_server\Sovereign-Homelab\docs\04_apps\paperless.md` is a brief, 55-line runbook. It contains basic VM specifications, a minimal `.env` overview, standard Docker Compose commands, basic Nginx Proxy Manager setup, and surface-level backup/restore instructions. 

It is missing:
- **VM Setup & Requirements**: Precise OS tuning, dependency prerequisites, and advanced sizing considerations.
- **Docker Architecture Details**: Missing configuration for Gotenberg & Tika (required for advanced Office document parsing), and volume mapping details (`consume`, `export`, etc.).
- **Deep-Dive Environment Variables**: Missing critical configurations for OCR tuning, workers, security (CSRF/CORS), and timezones.
- **Proxy Specifics**: Missing guidance on `client_max_body_size` which is a common failure point for large PDF uploads.
- **Comprehensive Disaster Recovery**: No mention of the native `document_exporter` and `document_importer` tools, or `pg_dump` strategies. The current drill only mentions PBS volume restores.
- **Advanced Troubleshooting**: Missing commands for reindexing, database migrations, restarting worker queues, and checking container logs.

## 2. Logic Chain
To fulfill the requirement for an "A-Z deployment, config, backup, and troubleshooting steps" and a "deep-dive env vars explanation", the rewritten document must be restructured into the following comprehensive sections:

1. **Architecture & Prerequisites**: 
   - Define exact resources: Minimum 2 vCPU / 4GB RAM (recommend 8GB for intensive OCR).
   - Storage requirements: Fast SSD for PostgreSQL/Redis/app, mass storage for media.
2. **Directory & File Structure**:
   - Explicitly detail the `docker-compose.yml` including `webserver`, `db` (Postgres 15+), `broker` (Redis), `gotenberg`, and `tika`.
   - Volumes needed: `data` (db), `media` (documents), `consume` (hot-folder), `export`.
3. **Deep-Dive Environment Variables**:
   - *Core*: `PAPERLESS_REDIS`, `PAPERLESS_DBHOST`, `PAPERLESS_SECRET_KEY`.
   - *Web/Network*: `PAPERLESS_URL`, `PAPERLESS_CSRF_TRUSTED_ORIGINS`, `PAPERLESS_CORS_ALLOWED_ORIGINS` (critical for WebUI access behind proxies).
   - *OCR*: `PAPERLESS_OCR_LANGUAGE`, `PAPERLESS_OCR_MODE` (skip, force, redo), `PAPERLESS_THREADS`.
   - *Integration*: `PAPERLESS_TIKA_ENABLED`, endpoints for Tika and Gotenberg.
4. **Step-by-Step Deployment**:
   - `docker compose pull` & `up -d`.
   - Admin user creation: `docker compose exec webserver document_sanitizer manage.py createsuperuser`.
5. **Reverse Proxy Configuration (NPM/Traefik)**:
   - Must emphasize: Enable WebSockets (for live UI updates).
   - Must emphasize: Add custom NGINX config `client_max_body_size 100M;` to prevent upload errors on large PDFs.
6. **Comprehensive Disaster Recovery (DR)**:
   - **Level 1 (Snapshots)**: Proxmox Backup Server (PBS) full VM/LXC snapshots.
   - **Level 2 (Database/Files)**: Daily `pg_dump` of the postgres container.
   - **Level 3 (Native Export)**: Using `docker compose exec webserver document_exporter ../export` to generate decrypted PDFs and `manifest.json`.
   - **Restore drill**: Explaining the `document_importer` command for migrating to a fresh instance.
7. **Troubleshooting & Maintenance**:
   - Command to regenerate search index: `manage.py document_index reindex`.
   - Command to manually trigger migrations: `manage.py migrate`.
   - Fixing stuck queues by restarting the Redis and webserver containers.

## 3. Caveats
- Since this environment is CODE_ONLY, the recommendations are based on standard best practices and the official Paperless-ngx architecture up to mid-2024.
- Specific IP addresses (e.g., `192.168.1.52`) and domain names (`paper.internal`) are retained from the original document for consistency.

## 4. Conclusion
The implementation agent should completely rewrite `C:\home_server\Sovereign-Homelab\docs\04_apps\paperless.md` using the structured outline provided in the Logic Chain above. The new document should transition from a basic runbook to a full-fledged enterprise-grade deployment and disaster recovery manual, ensuring no steps are missed from initial VM provisioning down to database restoration and index recreation.

## 5. Verification Method
- **File Inspection**: Check `C:\home_server\Sovereign-Homelab\docs\04_apps\paperless.md` after the rewrite to ensure all 7 sections from the Logic Chain are present.
- **Content Check**: Verify that `client_max_body_size`, `document_exporter`, `document_importer`, and the `gotenberg`/`tika` stack are explicitly mentioned and explained.
