# Paperless-ngx Deployment Runbook

## 1. Overview & Sizing
Paperless-ngx is a document management system that performs OCR on scanned documents. It becomes **P1 Critical** when used for tax or legal documents.
- **Target**: LXC 102 (`apps-light`)
- **CPU / RAM**: 2 vCPU / 4 GB
- **Storage**: Minimum 40GB plus future growth for documents.

## 2. Directory & Secrets Setup
Log into LXC 102 and navigate to the dedicated stack directory:
```bash
cd /opt/sovereign/stacks/paperless
cp .env.example .env
nano .env
```
Update the following values:
- `PAPERLESS_URL=https://paper.internal`
- `PAPERLESS_SECRET_KEY`: Generate a long random string.
- `PAPERLESS_DB_PASSWORD`: Set a strong database password.

## 3. Deployment
Validate the configuration and start the containers (app, redis, db):
```bash
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```
Create the first superuser:
```bash
docker exec -it paperless document_sanitizer manage.py createsuperuser
```

## 4. Nginx Proxy Manager (NPM) Setup
Log into NPM (`http://192.168.1.51:81`) and create a Proxy Host:
- **Domain Names**: `paper.internal`
- **Scheme / Forward IP / Port**: `http` / `192.168.1.52` (LXC 102 IP) / `8000`
- **Websockets Support**: ✅ Enabled
- **SSL**: Select your wildcard certificate and enable Force SSL.

## 5. Dashboard & Monitoring
- **Homepage.dev**: Add to `services.yaml` under "Critical Data" pointing to `https://paper.internal`. Add the Paperless API widget.
- **Uptime Kuma**: Add an `HTTP(s)` monitor named `app-paperless` targeting `https://paper.internal`.

## 6. Backup & Restore
- **Backup**: Include `paperless_data`, `paperless_media`, and `paperless_db` volumes in your PBS backup schedule. Optionally use the document exporter script to dump plain PDFs periodically.
- **Restore Drill**:
  1. Restore all volumes to an isolated test LXC.
  2. Verify OCR search works and previous PDFs are viewable.

## 7. Rollback and Troubleshooting
- If OCR fails or is extremely slow, allocate more vCPUs and verify Redis is running.
- If an update fails, restore all three volumes (data, media, db) from the exact same point in time from PBS.

*Source: [Paperless-ngx Setup Docs](https://docs.paperless-ngx.com/setup/)*
