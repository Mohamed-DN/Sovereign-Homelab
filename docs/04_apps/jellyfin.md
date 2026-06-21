# Jellyfin Deployment Runbook

## 1. Overview & Sizing
Jellyfin is a self-hosted media system for movies, TV shows, and music.
- **Target**: VM 150 (`jellyfin`) or LXC 102
- **CPU / RAM**: 4 vCPU / 8 GB (Requires GPU passthrough for hardware transcoding)
- **Storage**: Requires a dedicated large mount for media files.

## 2. Directory & Secrets Setup
Navigate to the dedicated stack directory on your target host:
```bash
cd /opt/sovereign/stacks/jellyfin
cp .env.example .env
nano .env
```
Map the correct paths for your host:
- `JELLYFIN_CONFIG_PATH`: Persistent config folder.
- `JELLYFIN_CACHE_PATH`: Cache folder.
- `JELLYFIN_MEDIA_PATH`: The read-only path to your actual media library.

## 3. Deployment
Validate and start the container:
```bash
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```

## 4. Nginx Proxy Manager (NPM) Setup
Log into NPM (`http://192.168.1.51:81`) and create a Proxy Host:
- **Domain Names**: `media.internal`
- **Scheme / Forward IP / Port**: `http` / `[Target_IP]` / `8096`
- **Websockets Support**: ✅ Enabled (Crucial for playback progress sync)
- **SSL**: Select your wildcard certificate and enable Force SSL.

## 5. Dashboard & Monitoring
- **Homepage.dev**: Add to `services.yaml` pointing to `https://media.internal`. Include the Jellyfin widget for active streams.
- **Uptime Kuma**: Add an `HTTP(s)` monitor targeting `https://media.internal`.

## 6. Backup & Restore
- **Backup**: Backup the `JELLYFIN_CONFIG_PATH` directory. You do not strictly need to backup the cache. Media files should be backed up separately based on your storage strategy.
- **Restore Drill**:
  1. Restore the config directory to a test instance.
  2. Mount a small test media folder and verify metadata and watched status are preserved.

## 7. Rollback and Troubleshooting
- If videos buffer endlessly or fail to play, hardware transcoding (VAAPI/NVENC) may be misconfigured. Ensure `/dev/dri` is correctly mapped into the container.
- If clients fail to sync progress, ensure WebSockets are enabled in NPM.

*Source: [Jellyfin Container Docs](https://jellyfin.org/docs/general/installation/container/)*
