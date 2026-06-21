# FreshRSS Deployment Runbook

## 1. Overview & Sizing
FreshRSS is a lightweight self-hosted RSS feed aggregator.
- **Target**: LXC 102 (`apps-light`)
- **CPU / RAM**: 1 vCPU / 1 GB

## 2. Environment & Pre-requisites
Log into LXC 102 and navigate to the pre-configured FreshRSS stack directory:
```bash
cd /opt/sovereign/stacks/freshrss
```

## 3. Docker Compose & Environment Variables
The `stacks/freshrss` project is already set up to use Docker named volumes (`freshrss_data` and `freshrss_extensions`), ensuring optimal file permissions and performance. 

Start by copying the example environment file:
```bash
cp .env.example .env
nano .env
```

### Environment Variables Deep Dive
The `.env` file exposes the following variables for customization:
- `TZ`: Crucial for correct feed timestamps (e.g., `Europe/Rome`).
- `FRESHRSS_TAG`: Specifies the Docker image tag (e.g., `latest`).
- `FRESHRSS_PORT`: The host port exposed for the web interface (default: `8087`).
- `FRESHRSS_BASE_URL`: The URL where FreshRSS will be reachable (e.g., `https://rss.internal`).

Within the `docker-compose.yml`, the following variable is hardcoded for the stack:
- `CRON_MIN: "3,33"`: Defines the background feed refresh rate via the internal cron job (runs every 30 minutes at minute 3 and 33).

Bring up the stack:
```bash
docker compose up -d
docker compose ps
```

## 4. Nginx Proxy Manager (NPM) Setup
Log into NPM at `https://npm.internal` and create a Proxy Host:
- **Domain Names**: `rss.internal`
- **Scheme / Forward IP / Port**: `http` / `LXC102_IP` / `8087`
- **Websockets Support**: disabled; FreshRSS does not need it.
- **SSL**: use the current internal TLS approach and enable Force SSL when HTTPS is configured.

## 5. Initial Configuration & API Access
Access the web UI at `https://rss.internal` and complete the initialization:
1. **Language**: Choose your preferred language.
2. **DB Setup**: Stick with SQLite (default) unless you specifically configured PostgreSQL.
3. **Admin user**: Set up your primary admin account.

### Mobile App API Setup (Essential)
To use mobile clients like Reeder or FeedMe, API access is required:
1. Go to **Settings -> Authentication**.
2. **Enable API access** (allow API access for clients).
3. Go to **Profile** (top right corner).
4. Set an **API password** (this should be different from your web login).
5. Use the API URL in your client: `https://rss.internal/api/greader.php`

## 6. Dashboard & Monitoring
- **Homepage.dev**: Add to `services.yaml` pointing to `https://rss.internal`.
- **Uptime Kuma**: Add an `HTTP(s)` monitor targeting `https://rss.internal`.

## 7. Comprehensive Disaster Recovery
Disaster recovery should be approached in layers. *Crucial Note:* OPML only saves feed subscriptions and categories, it does **not** retain read/unread history or starred articles. A DB restore is required for full state retention.

- **Level 1: Host Backup** 
  - Proxmox Backup Server (PBS) full LXC snapshot.
- **Level 2: File-level Backup**
  - Safely backup the Docker named data volume by attaching to the stopped container:
    ```bash
    docker compose stop
    docker run --rm --volumes-from freshrss -v $(pwd):/backup alpine tar -czvf /backup/freshrss_data.tar.gz -C /var/www/FreshRSS/data .
    docker compose start
    ```
- **Level 3: Application CLI Export**
  - Export the SQLite database cleanly via FreshRSS CLI tools:
    ```bash
    docker exec -u www-data freshrss php /var/www/FreshRSS/cli/export-sqlite-for-user.php --user admin --filename /var/www/FreshRSS/data/admin-backup.sqlite
    ```
- **Level 4: OPML Export (Lossy)**
  - Web UI export from `https://rss.internal`. Use this for migrating feeds between different RSS platforms, but understand it loses read/unread state.

## 8. Troubleshooting
- **Database Locked Errors (SQLite):** 
  - *Emphasize:* Do NOT place the `data` volume on SMB/NFS network shares. SQLite requires local/block I/O or it will corrupt/lock. If networked storage is required, deploy a PostgreSQL container instead.
- **Feeds not updating in background:** 
  - Trigger a manual update to view errors directly:
    ```bash
    docker exec -u www-data freshrss php /var/www/FreshRSS/app/actualize_script.php
    ```
- **Permissions Error in logs:** 
  - Fix ownership if files were created by root (this native container command safely resolves Alpine vs. Debian UID mismatches without relying on host-level hardcoded UIDs):
    ```bash
    docker exec -u root freshrss chown -R www-data:www-data /var/www/FreshRSS/data /var/www/FreshRSS/extensions
    ```
- **API Connection Failing:** 
  - Ensure the reverse proxy isn't blocking `/api/` paths and the user specifically set an *API password* (which is distinct from the web login password).

*Source: [FreshRSS Docker Image](https://hub.docker.com/r/freshrss/freshrss)*
