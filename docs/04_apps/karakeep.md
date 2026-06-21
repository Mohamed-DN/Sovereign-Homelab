# Karakeep Deployment Runbook

## 1. Overview & Sizing
Karakeep is a modern bookmarking and web archiving tool.
- **Target**: LXC 102 (`apps-light`)
- **CPU / RAM**: 2 vCPU / 4 GB

## 2. Directory & Secrets Setup
Log into LXC 102 and navigate to the dedicated stack directory:
```bash
cd /opt/sovereign/stacks/karakeep
cp .env.example .env
nano .env
```
Set the following security values:
- `KARAKEEP_NEXTAUTH_SECRET`: Strong random key.
- `KARAKEEP_MEILI_MASTER_KEY`: Strong random key for the Meilisearch database.

## 3. Deployment
Validate the configuration and start the containers (app, meilisearch, headless chrome):
```bash
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```

## 4. Nginx Proxy Manager (NPM) Setup
Log into NPM (`http://192.168.1.51:81`) and create a Proxy Host:
- **Domain Names**: `bookmarks.internal`
- **Scheme / Forward IP / Port**: `http` / `192.168.1.52` (LXC 102 IP) / `3010`
- **Websockets Support**: ✅ Enabled
- **SSL**: Select your wildcard certificate and enable Force SSL.

## 5. Dashboard & Monitoring
- **Homepage.dev**: Add to `services.yaml` pointing to `https://bookmarks.internal`.
- **Uptime Kuma**: Add an `HTTP(s)` monitor targeting `https://bookmarks.internal`.

## 6. Backup & Restore
- **Backup**: Include the `karakeep_data` and `karakeep_meili` volumes in PBS backups.
- **Restore Test**: Restore the volumes and verify that a previously saved page and its metadata load correctly.
