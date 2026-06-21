# Nextcloud AIO Deployment Runbook

## 1. Overview & Sizing
Nextcloud All-in-One (AIO) provides file hosting, calendar, contacts, and collaboration tools. It uses a Mastercontainer architecture to manage its own sub-containers. It is a **P1 Critical** service.
- **Target**: VM 120 (`nextcloud-aio`)
- **CPU / RAM**: 4 vCPU / 8-12 GB
- **Storage**: OS Disk (120GB) + Dedicated Mount for `/opt/sovereign/data/nextcloud`.

## 2. Directory & Secrets Setup
Log into VM 120 and navigate to the dedicated stack directory:
```bash
cd /opt/sovereign/stacks/nextcloud
cp .env.example .env
nano .env
```
Ensure the datadir is set to your large mount:
- `NEXTCLOUD_DATADIR=/opt/sovereign/data/nextcloud`

## 3. Deployment (Mastercontainer)
Nextcloud AIO uses a Mastercontainer to spawn the other containers automatically.
```bash
docker compose --env-file .env config
docker compose --env-file .env up -d
docker compose ps
```
Access `https://[VM120_IP]:8080` (bypass the SSL warning) to reach the AIO Setup Interface and enter the provided setup password.

## 4. Nginx Proxy Manager (NPM) Setup
Before completing the AIO setup, configure the reverse proxy:
Log into NPM (`http://192.168.1.51:81`) and create a Proxy Host:
- **Domain Names**: `files.internal`
- **Scheme / Forward IP / Port**: `http` / `192.168.1.70` (VM 120 IP) / `11000`
- **Websockets Support**: ✅ Enabled
- **SSL**: Select your wildcard certificate and enable Force SSL.

*Note: Port 11000 is the Apache container port spawned by AIO, NOT 8080!*

Return to the AIO Setup Interface at `https://[VM120_IP]:8080` and enter `files.internal` as your domain. Nextcloud will verify the proxy and spin up the remaining containers.

## 5. Dashboard & Monitoring
- **Homepage.dev**: Add to `services.yaml` pointing to `https://files.internal`.
- **Uptime Kuma**: Add an `HTTP(s)` monitor named `app-nextcloud` targeting `https://files.internal`.

## 6. Backup & Restore
- **Backup**: Use the built-in Nextcloud AIO backup system (Borg backup) through the `8080` interface to a local or remote directory. Additionally, include the whole VM in your PBS schedules.
- **Restore Drill**:
  1. Spin up a clean test VM.
  2. Restore the AIO built-in backup.
  3. Verify files, calendars, and users are intact before switching DNS.

## 7. Rollback and Troubleshooting
- If updates fail, rely on the AIO backup restore mechanism; manual container rollback is not supported by AIO.
- If domain validation fails during setup, ensure NPM is correctly forwarding to port `11000` and `APACHE_PORT` is set to `11000` in the Compose file.
- If memory crashes occur during large file syncs, allocate more RAM to the VM and adjust PHP memory limits in AIO settings.

*Source: [Nextcloud AIO Reverse Proxy Docs](https://github.com/nextcloud/all-in-one/blob/main/reverse-proxy.md)*
