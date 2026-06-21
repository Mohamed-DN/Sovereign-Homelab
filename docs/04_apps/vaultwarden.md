# Vaultwarden Deployment Runbook

## 1. Overview & Sizing
Vaultwarden is the self-hosted password manager (Bitwarden compatible). It is a **P0 Critical** service because losing it can lock you out of the rest of the lab.
Use it when you want secure password storage. Do not expose it publicly by default.
- **Target**: LXC 102 (`apps-light`)
- **CPU / RAM**: 1 vCPU / 1 GB
- **Access**: VPN / Internal Network only.

## 2. Directory & Secrets Setup
Log into LXC 102 and navigate to the dedicated stack directory:
```bash
cd /opt/sovereign/stacks/vaultwarden
cp .env.example .env
nano .env
```
Update the following critical values:
- `VAULTWARDEN_DOMAIN=https://pwd.internal`
- `VAULTWARDEN_ADMIN_TOKEN`: Generate a strong Argon2 hash via `docker run --rm -it vaultwarden/server /vaultwarden hash`

## 3. Deployment
Validate the configuration and start the container:
```bash
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```
*Note: Verify the container is running without errors using `docker logs -f vaultwarden`. After creating the first user, keep signups disabled.*

## 4. Nginx Proxy Manager (NPM) Setup
Log into NPM (`http://192.168.1.51:81`) and create a new Proxy Host:
- **Domain Names**: `pwd.internal`
- **Scheme / Forward IP / Port**: `http` / `192.168.1.52` (LXC 102 IP) / `8082`
- **Websockets Support**: ✅ Enabled (Critical for live sync)
- **SSL**: Select your wildcard certificate and enable Force SSL.

## 5. Dashboard & Monitoring
- **Homepage.dev**: Add to `services.yaml` under "Critical Data" group pointing to `https://pwd.internal`.
- **Uptime Kuma**: Add an `HTTP(s)` monitor named `app-vaultwarden` targeting `https://pwd.internal`.

## 6. Backup & Restore
- **Backup**: Include the `vaultwarden_data` Docker volume and the `.env` file in your PBS backup schedule. Generate an encrypted Bitwarden export after major password changes.
- **Restore Drill**: 
  1. Restore the volume to an isolated test LXC.
  2. Restore `.env` and admin token.
  3. Start Vaultwarden.
  4. Verify login, attachments, organizations, and export.

## 7. Rollback and Troubleshooting
- If an upgrade breaks the login, stop the container and restore the previous volume snapshot from PBS.
- If attachments fail to upload or download, verify that `VAULTWARDEN_DOMAIN` strictly matches `https://pwd.internal`.
- If WebSocket sync fails between devices, confirm NPM WebSocket support is checked.

*Source: [Vaultwarden Docker Compose Wiki](https://github.com/dani-garcia/vaultwarden/wiki/Using-Docker-Compose)*
