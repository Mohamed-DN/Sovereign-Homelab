# Forgejo Deployment Runbook

## 1. Overview & Sizing
Forgejo is a lightweight, self-hosted Git service. It becomes **P1 Critical** when storing infrastructure-as-code or this homelab repository.
- **Target**: LXC 102 (`apps-light`)
- **CPU / RAM**: 2 vCPU / 4 GB

## 2. Directory & Secrets Setup
Log into LXC 102 and navigate to the dedicated stack directory:
```bash
cd /opt/sovereign/stacks/forgejo
cp .env.example .env
nano .env
```
Ensure the correct configuration parameters:
- `FORGEJO_DB_PASSWORD`: Strong database password.
- Verify ports `FORGEJO_HTTP_PORT=3003` and `FORGEJO_SSH_PORT=2222`.

## 3. Deployment
Validate and start the database and the Forgejo container:
```bash
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```

## 4. Nginx Proxy Manager (NPM) Setup
Log into NPM (`http://192.168.1.51:81`) and create a Proxy Host for HTTPS:
- **Domain Names**: `git.internal`
- **Scheme / Forward IP / Port**: `http` / `192.168.1.52` (LXC 102 IP) / `3003`
- **Websockets Support**: ✅ Enabled
- **SSL**: Select your wildcard certificate and enable Force SSL.

*(SSH traffic on port 2222 goes directly to the LXC IP and does not pass through NPM).*

## 5. Dashboard & Monitoring
- **Homepage.dev**: Add to `services.yaml` pointing to `https://git.internal`.
- **Uptime Kuma**: 
  - Add an `HTTP(s)` monitor targeting `https://git.internal`.
  - Add a `TCP` monitor targeting `192.168.1.52:2222` to ensure SSH clones are working.

## 6. Backup & Restore
- **Backup**: Include `forgejo_db` and `forgejo_data` volumes in PBS backups.
- **Restore Test**: Restore the database and data volumes. Verify you can clone a repository over both HTTPS and SSH, and push a test commit successfully.
