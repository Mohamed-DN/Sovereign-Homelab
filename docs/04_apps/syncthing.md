# Syncthing Deployment Runbook

## 1. Overview & Sizing
Syncthing is a continuous file synchronization program. It synchronizes files between devices in real-time. It is NOT a backup system.
- **Target**: LXC 102 (`apps-light`)
- **CPU / RAM**: 1 vCPU / 1 GB
- **Access**: UI restricted to Admin/VPN only. Sync ports reachable via VPN.

## 2. Directory & Secrets Setup
Log into LXC 102 and navigate to the dedicated stack directory:
```bash
cd /opt/sovereign/stacks/syncthing
cp .env.example .env
nano .env
```
Update the timezone and verify ports (Default UI: `8384`, Sync: `22000` TCP/UDP).

## 3. Deployment
Validate the configuration and start the container:
```bash
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```

## 4. Nginx Proxy Manager (NPM) Setup
Log into NPM (`http://192.168.1.51:81`) to expose the Administrative Web UI securely:
- **Domain Names**: `sync.internal`
- **Scheme / Forward IP / Port**: `http` / `192.168.1.52` (LXC 102 IP) / `8384`
- **Websockets Support**: ✅ Enabled
- **SSL**: Select your wildcard certificate and enable Force SSL.

## 5. Dashboard & Monitoring
- **Homepage.dev**: Add to `services.yaml` under "Critical Data" pointing to `https://sync.internal`.
- **Uptime Kuma**: 
  - Add an `HTTP(s)` monitor targeting `https://sync.internal` for the UI.
  - Add a `TCP` monitor targeting `192.168.1.52:22000` to verify the sync engine is listening.

## 6. Backup & Restore
- **Backup**: Backup the `syncthing_config` volume. File versioning should be enabled inside the Syncthing UI for critical folders.
- **Restore Test**: Restore the config volume. Verify Device IDs are intact before reconnecting production peers.
