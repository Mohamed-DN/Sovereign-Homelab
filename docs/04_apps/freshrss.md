# FreshRSS Deployment Runbook

## 1. Overview & Sizing
FreshRSS is a lightweight self-hosted RSS feed aggregator.
- **Target**: LXC 102 (`apps-light`)
- **CPU / RAM**: 1 vCPU / 1 GB

## 2. Directory & Secrets Setup
Log into LXC 102 and navigate to the dedicated stack directory:
```bash
cd /opt/sovereign/stacks/freshrss
cp .env.example .env
nano .env
```
Ensure the URL matches the reverse proxy:
- `FRESHRSS_BASE_URL=https://rss.internal`

## 3. Deployment
Validate and start the container:
```bash
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```

## 4. Nginx Proxy Manager (NPM) Setup
Log into NPM (`http://192.168.1.51:81`) and create a Proxy Host:
- **Domain Names**: `rss.internal`
- **Scheme / Forward IP / Port**: `http` / `192.168.1.52` (LXC 102 IP) / `8087`
- **Websockets Support**: ❌ Disabled (Not needed for FreshRSS)
- **SSL**: Select your wildcard certificate and enable Force SSL.

## 5. Dashboard & Monitoring
- **Homepage.dev**: Add to `services.yaml` pointing to `https://rss.internal`.
- **Uptime Kuma**: Add an `HTTP(s)` monitor targeting `https://rss.internal`.

## 6. Backup & Restore
- **Backup**: Backup the `freshrss_data` volume via PBS. Optionally, perform an OPML export from the Web UI after major feed additions.
- **Restore Drill**:
  1. Import an OPML file into a fresh instance.
  2. Confirm feeds update correctly.

## 7. Rollback and Troubleshooting
- If updates fail, check cron settings and container logs.
- If feeds disappear, restore data volume from PBS or import OPML.

*Source: [FreshRSS Docker Image](https://hub.docker.com/r/freshrss/freshrss)*
