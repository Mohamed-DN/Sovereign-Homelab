# Paperless-ngx Documentation & Disaster Recovery Runbook

## 1. Architecture & Prerequisites

Paperless-ngx is a document management system that performs OCR on scanned documents. It becomes **P1 Critical** when used for tax or legal documents.

- **Target**: LXC 102 (`apps-light`) - IP: `192.168.1.52`
- **CPU / RAM**: Minimum 2 vCPU / 4 GB RAM. Recommend **8 GB RAM** for intensive OCR tasks.
- **Storage**:
  - Fast SSD storage required for PostgreSQL, Redis, and the app database.
  - Mass storage required for the `media` volume where actual PDFs and documents are kept. Minimum 40GB plus future growth.

## 2. Directory & File Structure

Create a dedicated stack directory for Paperless:
```bash
mkdir -p /opt/sovereign/stacks/paperless
cd /opt/sovereign/stacks/paperless
```

Your `docker-compose.yml` should define the complete architecture:
- **paperless**: The main Django application.
- **paperless-db**: PostgreSQL 15+ database.
- **paperless-redis**: Redis for Celery message queues.

### Required Volumes
Ensure these volumes/directories are mapped properly in the compose file:
- `data`: Database and app data.
- `media`: Document storage (mass storage).
- `consume`: Hot-folder for dropping new files to be ingested automatically.
- `export`: Directory used for disaster recovery and document exports.

## 3. Deep-Dive Environment Variables

Create and edit the `.env` file (e.g., `cp .env.example .env`):
```bash
nano .env
```

Define the following critical parameters to ensure smooth operation:

**Core Configuration:**
- `PAPERLESS_REDIS=redis://paperless-redis:6379`: Connects app to the Redis broker.
- `PAPERLESS_DBHOST=paperless-db`: Connects app to the PostgreSQL container.
- `PAPERLESS_DB`: The database name (e.g., paperless).
- `PAPERLESS_DB_USER`: The database user (e.g., paperless).
- `PAPERLESS_DB_PASSWORD`: The database password.
- `PAPERLESS_SECRET_KEY`: Must be a long, cryptographically secure random string.

**Web/Network Configuration:**
- `PAPERLESS_URL=https://paper.internal`: Base URL for the application.
- `PAPERLESS_PORT=8010`: Port exposed to the host.
- `PAPERLESS_CSRF_TRUSTED_ORIGINS=https://paper.internal`: Required to prevent CSRF errors when behind a reverse proxy.
- `PAPERLESS_CORS_ALLOWED_ORIGINS=https://paper.internal`: Required for WebUI access and API requests behind proxies.

**OCR Configuration:**
- `PAPERLESS_OCR_LANGUAGE=eng`: Default language for Tesseract OCR.
- `PAPERLESS_OCR_MODE=skip`: Modes include `skip` (don't OCR if text exists), `force` (always OCR), or `redo` (re-run OCR).
- `PAPERLESS_THREADS=2`: Number of parallel OCR tasks. Adjust based on vCPU allocation.

## 4. Step-by-Step Deployment

Once the `docker-compose.yml` and `.env` files are correctly set up, deploy the stack:

```bash
docker compose --env-file .env config
docker compose --env-file .env pull
docker compose --env-file .env up -d
docker compose ps
```

**Create the initial Admin User:**
```bash
docker compose exec paperless manage.py createsuperuser
```

## 5. Reverse Proxy Configuration (NPM)

Access Nginx Proxy Manager (NPM) at `http://192.168.1.51:81` and create a Proxy Host.

- **Domain Names**: `paper.internal`
- **Scheme / Forward IP / Port**: `http` / `192.168.1.52` (LXC 102 IP) / `8010`
- **Websockets Support**: ✅ **Enabled** (Crucial for live UI updates during document consumption).
- **SSL**: Select your wildcard certificate and enable Force SSL.

**Critical NGINX Custom Configuration:**
Go to the **Advanced** tab in the proxy host settings and add:
```nginx
client_max_body_size 100M;
```
*Why?* Without this, NPM limits upload sizes to 1MB/5MB by default, causing uploads of large PDFs to fail consistently.

## 6. Monitoring

Paperless exposes a web interface that can be used for monitoring. Set up an HTTP health check using a tool like Uptime Kuma targeting the Paperless web interface.
- **Check URL**: `http://<docker-host-ip>:8010` or the configured `PAPERLESS_URL` (`https://paper.internal`).
- **Expected Response**: HTTP 200 OK or 302 Found (redirecting to login).

## 7. Comprehensive Disaster Recovery (DR)

A multi-layered backup strategy is required since losing tax or legal documents is catastrophic.

- **Level 1 (Snapshots)**: Proxmox Backup Server (PBS) full VM/LXC snapshots for rapid complete-system rollback.
- **Level 2 (Database/Files)**: Daily `pg_dump` of the postgres container to ensure database integrity. Run the exact dump command:
  ```bash
  docker compose exec paperless-db pg_dump -U paperless paperless > paperless_db_backup.sql
  ```
- **Level 3 (Native Export)**: Use the native `document_exporter` to generate decrypted plain PDFs and a `manifest.json`.
  ```bash
  docker compose exec paperless document_exporter ../export
  ```
  This creates a portable, software-agnostic archive of all your files.

**Restore Drill (Migration to a Fresh Instance):**
1. Deploy a fresh Paperless-ngx instance.
2. Mount the exported archive into the `export` volume.
3. Run the importer:
   ```bash
   docker compose exec paperless document_importer ../export
   ```
4. Verify OCR search works and all previous PDFs are viewable in the fresh instance.

## 8. Troubleshooting & Maintenance

If the system experiences indexing issues or missing search results, regenerate the search index:
```bash
docker compose exec paperless manage.py document_index reindex
```

If database schema mismatches occur after an update, manually trigger migrations:
```bash
docker compose exec paperless manage.py migrate
```

**Fixing Stuck Queues:**
If documents remain in the "consuming" state without progress, the workers may have crashed. Restart the Redis and paperless containers, and check logs:
```bash
docker compose restart paperless-redis paperless
docker compose logs -f paperless paperless-redis
```

*Source: [Paperless-ngx Setup Docs](https://docs.paperless-ngx.com/setup/)*
