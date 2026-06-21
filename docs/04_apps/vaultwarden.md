# Vaultwarden Deployment Runbook

## 1. Overview & Sizing
Vaultwarden is the self-hosted password manager (Bitwarden compatible). It is a **P0 Critical** service.
- **Target**: LXC 102 (`apps-light`)
- **CPU / RAM**: 1 vCPU / 1 GB
- **Access**: VPN / Internal Network only. Do NOT expose publicly.

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
*Note: Verify the container is running without errors using `docker logs -f vaultwarden`.*

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
- **Backup**: Include the `vaultwarden_data` Docker volume and the `.env` file in your PBS backup schedule.
- **Restore Test**: Spin up a fresh test LXC, restore the volume and `.env` file, start the container, and verify successful login and password retrieval.
