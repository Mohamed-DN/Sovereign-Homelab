# Immich Deployment Runbook

## 1. Overview & Sizing
Immich is a high-performance photo and video backup solution. It is a **P0 Critical** service due to irreplaceable personal data. It uses machine learning to classify images locally.
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
*Note: The Machine Learning container may take a few minutes to download models on first boot. Monitor with `docker logs -f immich_machine_learning`.*

## 4. Nginx Proxy Manager (NPM) Setup
Log into NPM at `https://npm.internal` and create a new Proxy Host:
- **Domain Names**: `foto.internal`
- **Scheme / Forward IP / Port**: `http` / `VM110_IP` / `2283`
- **Websockets Support**: enabled
- **SSL**: use the current internal TLS approach and enable Force SSL when HTTPS is configured.
- **Advanced**: Ensure Client Max Body Size is set to `0` to allow large video uploads without dropping packets.

## 5. Dashboard & Monitoring
- **Homepage.dev**: Add to `services.yaml` under "Critical Data" pointing to `https://foto.internal`. Add the Immich API widget for stats.
- **Uptime Kuma**: Add an `HTTP(s)` monitor named `app-immich` targeting `https://foto.internal`.

## 6. Backup & Restore
- **Backup**: Run a daily database dump using `docker exec -t immich_postgres pg_dumpall -c -U postgres > dump.sql`. Backup the database dump, `.env`, `docker-compose.yml`, and the entire `IMMICH_UPLOAD_LOCATION` folder via PBS.
- **Restore Drill**:
  1. Mount a snapshot of the upload directory and database on a test VM.
  2. Run the database restore command: `cat dump.sql | docker exec -i immich_postgres psql -U postgres`.
  3. Verify thumbnails load correctly and the timeline matches the backup date.

## 7. Rollback and Troubleshooting
- If machine learning fails, check AVX support on your Proxmox host CPU and verify the `immich_machine_learning` container logs.
- If the mobile app fails to backup in the background, ensure iOS battery restrictions are disabled and check the reverse proxy body limit.
- If an update breaks the database, restore the Postgres volume and `dump.sql` from PBS. Always read Immich release notes before updating!

*Sources: [Immich Docker Compose](https://docs.immich.app/install/docker-compose/) | [Immich Backup and Restore](https://docs.immich.app/administration/backup-and-restore/)*
