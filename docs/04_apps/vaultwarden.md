# Vaultwarden Deployment Runbook

## 1. Overview & Architecture
Vaultwarden is a lightweight, alternative implementation of the Bitwarden server API written in Rust.
It provides secure password management for self-hosted environments.
As a **P0 Critical** service, its availability and integrity are paramount.
- **Target**: LXC 102 (`apps-light`)
- **CPU / RAM**: 1 vCPU / 1 GB
- **Networking**: Proxied via NPM (`pwd.internal`), internal network only. No direct internet exposure.

## 2. Environment Variables Deep-Dive
Vaultwarden relies heavily on environment variables for configuration. Create an `.env` file with these values:
- `DOMAIN`: (e.g. `https://pwd.internal`) Crucial for U2F/FIDO2 authentication, attachments, and email links. Must match the exact URL served by the reverse proxy.
- `ADMIN_TOKEN`: Argon2 hashed token to access the `/admin` interface. (See Section 3.1 for instructions on generating this token).
- `SIGNUPS_ALLOWED`: Should be `true` initially, then set to `false` after creating your account to prevent unauthorized users.
- `INVITATIONS_ALLOWED`: Set to `false` unless you plan to invite other users via email.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_SECURITY`: Required for email functionality (e.g., verifying device logins or user invitations).
- `LOG_FILE` / `LOG_LEVEL`: For debugging. Set `LOG_LEVEL=warn` in production.

## 3. Deployment Steps (A-Z)
### 3.1 VM / LXC Preparation
1. Create LXC 102 (`apps-light`) using a Debian/Ubuntu template.
2. Install Docker and Docker Compose.
3. Generate the `ADMIN_TOKEN` hash (this requires Docker to be installed first). Use the pinned tag from `stacks/vaultwarden/.env.example`:
```bash
VAULTWARDEN_TAG=$(grep '^VAULTWARDEN_TAG=' .env.example | cut -d= -f2)
docker run --rm -it "vaultwarden/server:${VAULTWARDEN_TAG}" /vaultwarden hash
```
Copy the generated Argon2 hash to use in your `.env` file later.
4. Create the deployment directory:
```bash
mkdir -p /opt/sovereign-homelab/stacks/vaultwarden/vw-data
cd /opt/sovereign-homelab/stacks/vaultwarden
```

### 3.2 Docker Compose Configuration
Create `docker-compose.yml`:
```yaml
services:
  vaultwarden:
    image: vaultwarden/server:${VAULTWARDEN_TAG}
    container_name: vaultwarden
    restart: always
    env_file:
      - .env
    volumes:
      - ./vw-data:/data
    ports:
      - 8082:80
```
*Note: As of Vaultwarden 1.29.0+, WebSocket traffic runs on the main HTTP port (80) rather than a separate port (3012). The proxy should point to port 8082.*

### 3.3 Launch Container
```bash
nano .env  # Populate with the variables defined in Section 2, including ADMIN_TOKEN
docker compose config
docker compose up -d
docker logs -f vaultwarden
```

## 4. Reverse Proxy & Monitoring (NPM & Uptime Kuma)

AdGuard resolves `pwd.internal` to NPM through the private wildcard rewrite. No public DuckDNS application hostname or router port forward is created for Vaultwarden.
### 4.1 Nginx Proxy Manager (NPM)
1. Add a Proxy Host in NPM targeting `LXC102_IP` on port `8082`.
2. **Websockets Support**: must be enabled for live synchronization across apps.
3. **SSL**: use the current internal TLS approach and enable Force SSL when HTTPS is configured. Vaultwarden requires HTTPS for WebAuthn.

### 4.2 Monitoring
- **Uptime Kuma**: Create an `HTTP(s)` monitor targeting `https://pwd.internal`. Wait for an HTTP 200 response.
- **Homepage.dev**: Add an entry under the "Critical Data" group.

## 5. Backup, Disaster Recovery & Rollback
### 5.1 SQLite Live Backups
Backing up a live SQLite database file directly can result in corruption. Use the SQLite online backup tool via a cron job:
```bash
# Add this to crontab on the LXC (runs daily at 2 AM)
0 2 * * * docker exec vaultwarden sqlite3 /data/db.sqlite3 ".backup '/data/db.sqlite3.bak'"
```
The `./vw-data` folder should then be backed up by Proxmox Backup Server (PBS).

### 5.2 Critical Files to Backup
- `db.sqlite3` or `db.sqlite3.bak`
- `config.json` (Stores settings configured via the `/admin` interface).
- `rsa_key.der`, `rsa_key.pem`, `rsa_key.pub.der` (Critical for JWT tokens; if lost, all users must re-authenticate).
- `attachments/` and `sends/` directories.
- `.env` and `docker-compose.yml`.

### 5.3 Restore Drill (Verified Procedure)
1. Spin up a fresh LXC and install Docker.
2. Restore the `/opt/sovereign-homelab/stacks/vaultwarden` directory (including `./vw-data` and `.env`) from PBS or file-level backup.
3. If using `.bak`, rename `db.sqlite3.bak` to `db.sqlite3` and ensure `db.sqlite3-wal` and `db.sqlite3-shm` are deleted to prevent corruption.
4. Run `docker compose up -d`.
5. Access the Web Vault, verify password entries and attachments are intact.

### 5.4 Rollback Procedure
If an update to Vaultwarden causes issues or database corruption, use the following steps to perform a deterministic rollback:
1. Stop the running container: `docker compose down`
2. Revert `VAULTWARDEN_TAG` in `.env` to the previously known-good pinned version.
3. Restore the database from the backup made prior to the update:
   - Rename the corrupted or newer `db.sqlite3` file: `mv ./vw-data/db.sqlite3 ./vw-data/db.sqlite3.corrupt`
   - Delete temporary SQLite files to avoid corruption: `rm -f ./vw-data/db.sqlite3-wal ./vw-data/db.sqlite3-shm`
   - Copy the backup over: `cp ./vw-data/db.sqlite3.bak ./vw-data/db.sqlite3`
4. Start the container with the older image: `docker compose up -d`
5. Verify that the previous version is running and data is accessible.

Live baseline evidence: on 2026-06-23, LXC102 wrote `/root/sovereign-app-restore-drills/20260623T153506Z`, copied the Vaultwarden SQLite database, and `sqlite3 PRAGMA integrity_check` returned `ok`. Before storing irreplaceable passwords, repeat the drill after creating real test items, confirm login from a client, test an attachment, and keep an encrypted export outside the host.

## 6. Troubleshooting
- **Cannot log in / U2F fails**: Confirm you are accessing via HTTPS. Bitwarden clients strict-block HTTP for WebAuthn.
- **Attachments fail to upload**: Check the `DOMAIN` environment variable exactly matches your proxy address.
- **Live sync isn't working**: Ensure Websockets support is checked in Nginx Proxy Manager.
- **Admin token invalid**: Ensure the Argon2 hash is wrapped in single quotes in the `.env` file if it contains special characters (`$` signs).

## 7. Official Sources

- Vaultwarden wiki: <https://github.com/dani-garcia/vaultwarden/wiki>
- Vaultwarden Docker image: <https://hub.docker.com/r/vaultwarden/server>

---

**Previous:** [Application Service Index](00_APP_SERVICES_INDEX.md)

**Next:** [Immich](immich.md)
