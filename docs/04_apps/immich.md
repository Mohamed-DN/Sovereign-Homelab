# Immich Deployment Runbook

## 1. Overview & Sizing
Immich is a high-performance photo and video backup solution. It is a **P0 Critical** service due to irreplaceable personal data.
- **Target**: VM 110 (`immich`)
- **CPU / RAM**: 6 vCPU / 16 GB
- **Storage**: OS Disk (120GB) + Dedicated Mount (1TB+) for `/usr/src/app/upload`.

## 2. Directory & Secrets Setup
Log into VM 110 and navigate to the dedicated stack directory:
```bash
cd /opt/sovereign/stacks/immich
cp .env.example .env
nano .env
```
Update the following critical values:
- `IMMICH_UPLOAD_LOCATION`: Set this to your dedicated large storage mount (e.g., `/mnt/photos`).
- `IMMICH_DB_DATA_LOCATION`: Local VM disk path for PostgreSQL.
- `IMMICH_DB_PASSWORD`: Generate a strong password using `openssl rand -base64 36`.

## 3. Deployment
Validate the configuration and start the database, redis, ML, and server containers:
```bash
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```
*Note: The Machine Learning container may take a few minutes to download models on first boot.*

## 4. Nginx Proxy Manager (NPM) Setup
Log into NPM (`http://192.168.1.51:81`) and create a new Proxy Host:
- **Domain Names**: `foto.internal`
- **Scheme / Forward IP / Port**: `http` / `192.168.1.60` (VM 110 IP) / `2283`
- **Websockets Support**: ✅ Enabled
- **SSL**: Select your wildcard certificate and enable Force SSL.
- **Advanced**: Ensure Client Max Body Size is set to `0` to allow large video uploads.

## 5. Dashboard & Monitoring
- **Homepage.dev**: Add to `services.yaml` under "Critical Data" pointing to `https://foto.internal`. Add the Immich API widget.
- **Uptime Kuma**: Add an `HTTP(s)` monitor named `app-immich` targeting `https://foto.internal`.

## 6. Backup & Restore
- **Backup**: Run a daily database dump. Backup the database dump, `.env`, `docker-compose.yml`, and the entire `IMMICH_UPLOAD_LOCATION` folder via PBS.
- **Restore Test**: Mount a snapshot of the upload directory and database on a test VM. Run the database restore command and verify thumbnails load correctly.
